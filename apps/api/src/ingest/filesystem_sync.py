from __future__ import annotations

import hashlib
import logging
import mimetypes
from dataclasses import dataclass
from pathlib import Path

from src.ingest.pipeline import ALLOWED_EXTENSIONS, extract_text_from_upload, ingest_text
from src.rag.store import delete_by_source, get_collection


logger = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[4]

# folder_name -> source_type
SOURCE_DIRS: dict[str, str] = {
    "jd": "jd",
    "notes": "note",
    "resume": "resume",
}


@dataclass(frozen=True)
class SourceFile:
    source_type: str
    rel_path: str
    abs_path: Path
    source_id: str
    sha256: str


def _build_source_id(source_type: str, rel_path: str) -> str:
    stable_key = f"{source_type}:{rel_path.lower()}".encode("utf-8")
    digest = hashlib.sha256(stable_key).hexdigest()[:12]
    return f"fs_{source_type}_{digest}"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _iter_source_files(data_root: Path) -> list[SourceFile]:
    files: list[SourceFile] = []
    for folder_name, source_type in SOURCE_DIRS.items():
        folder = data_root / folder_name
        if not folder.exists():
            continue

        for path in folder.rglob("*"):
            if not path.is_file():
                continue
            ext = path.suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue
            rel_path = path.relative_to(data_root).as_posix()
            data = path.read_bytes()
            files.append(
                SourceFile(
                    source_type=source_type,
                    rel_path=rel_path,
                    abs_path=path,
                    source_id=_build_source_id(source_type, rel_path),
                    sha256=_sha256_bytes(data),
                )
            )
    return files


def _existing_fs_sources() -> dict[str, dict]:
    collection = get_collection()
    raw = collection.get(where={"ingest_mode": "filesystem"}, include=["metadatas"])
    ids = raw.get("ids") or []
    metadatas = raw.get("metadatas") or []
    out: dict[str, dict] = {}
    for idx, chunk_id in enumerate(ids):
        if not isinstance(chunk_id, str):
            continue
        source_id = chunk_id.split(":")[0]
        if source_id in out:
            continue
        meta = metadatas[idx] if idx < len(metadatas) and isinstance(metadatas[idx], dict) else {}
        out[source_id] = meta
    return out


def list_filesystem_source_ids(data_root: Path | None = None) -> list[dict]:
    root = data_root or (REPO_ROOT / "data")
    items = _iter_source_files(root)
    return [
        {
            "source_id": item.source_id,
            "source_type": item.source_type,
            "path": item.rel_path,
            "sha256": item.sha256,
        }
        for item in items
    ]


def sync_filesystem_sources(data_root: Path | None = None) -> dict:
    root = data_root or (REPO_ROOT / "data")
    files = _iter_source_files(root)
    expected_ids = {item.source_id for item in files}
    existing = _existing_fs_sources()

    upserted = 0
    unchanged = 0
    failed = 0
    deleted = 0

    for item in files:
        old_meta = existing.get(item.source_id, {})
        if old_meta.get("file_sha256") == item.sha256 and old_meta.get("path") == item.rel_path:
            unchanged += 1
            continue
        try:
            data = item.abs_path.read_bytes()
            content_type = mimetypes.guess_type(item.abs_path.name)[0]
            text = extract_text_from_upload(item.abs_path.name, content_type, data)
            ingest_text(
                text,
                source_type=item.source_type,
                source_id=item.source_id,
                metadata={
                    "ingest_mode": "filesystem",
                    "path": item.rel_path,
                    "file_sha256": item.sha256,
                },
            )
            upserted += 1
        except Exception:
            failed += 1
            logger.exception("filesystem sync failed for %s", item.rel_path)

    stale_ids = set(existing.keys()) - expected_ids
    for source_id in stale_ids:
        delete_by_source(source_id)
        deleted += 1

    return {
        "ok": True,
        "root": str(root),
        "total_files": len(files),
        "upserted": upserted,
        "unchanged": unchanged,
        "deleted": deleted,
        "failed": failed,
        "source_ids": [
            {
                "source_id": item.source_id,
                "source_type": item.source_type,
                "path": item.rel_path,
            }
            for item in files
        ],
    }
