from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from src.rag.chunking import chunk_text
from src.rag.embeddings import embed_texts
from src.rag.store import delete_by_source, upsert_chunks


ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}
logger = logging.getLogger(__name__)


def normalize_text_for_hash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def content_sha256(text: str) -> str:
    normalized = normalize_text_for_hash(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_upload_source_id(source_type: str, content_hash: str) -> str:
    prefix = "".join(ch for ch in source_type if ch.isalnum() or ch in {"-", "_"}).lower() or "doc"
    return f"{prefix}_{content_hash[:16]}"


def extract_text_from_upload(filename: str, content_type: str | None, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file type")

    if ext in {".txt", ".md"}:
        return data.decode("utf-8", errors="replace")

    if ext == ".docx":
        try:
            from docx import Document
        except Exception as exc:  # pragma: no cover - optional dependency
            raise ValueError("docx support requires python-docx") from exc
        from io import BytesIO

        doc = Document(BytesIO(data))
        if hasattr(doc, "paragraphs"):
            return "\n".join(p.text for p in doc.paragraphs if p.text)
        return ""

    if ext == ".pdf":
        reader_cls = None
        try:
            from pypdf import PdfReader

            reader_cls = PdfReader
        except Exception:
            try:
                from PyPDF2 import PdfReader

                reader_cls = PdfReader
            except Exception as exc:  # pragma: no cover - optional dependency
                raise ValueError("pdf support requires pypdf or PyPDF2") from exc

        from io import BytesIO

        reader = reader_cls(BytesIO(data))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages.append(text)
        return "\n".join(pages)

    return ""


def ingest_text(
    text: str,
    *,
    source_type: str,
    source_id: str,
    metadata: dict | None = None,
) -> dict:
    chunks = chunk_text(text)
    delete_by_source(source_id)

    if not chunks:
        return {"ok": True, "source_id": source_id, "source_type": source_type, "chunks": 0}

    embeddings = embed_texts(chunks)

    ids: list[str] = []
    metadatas: list[dict] = []
    base_meta = metadata.copy() if metadata else {}
    base_meta.update({"source_id": source_id, "source_type": source_type})

    uploaded_at = datetime.now(timezone.utc).isoformat()

    for index, _chunk in enumerate(chunks):
        ids.append(f"{source_id}:{index}")
        chunk_meta = dict(base_meta)
        chunk_meta.update({"chunk_index": index, "uploaded_at": uploaded_at})
        metadatas.append(chunk_meta)

    upsert_chunks(ids=ids, chunks=chunks, embeddings=embeddings, metadatas=metadatas)

    logger.info("ingest_text source_id=%s chunks=%s", source_id, len(chunks))

    return {"ok": True, "source_id": source_id, "source_type": source_type, "chunks": len(chunks)}
