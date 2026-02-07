import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.core.settings import get_settings
from src.ingest.pipeline import (
    ALLOWED_EXTENSIONS,
    content_sha256,
    extract_text_from_upload,
    generate_upload_source_id,
    ingest_text,
)
from src.rag.store import find_source_id_by_content_hash


router = APIRouter()
logger = logging.getLogger(__name__)
ALLOWED_SOURCE_TYPES = {"resume", "jd", "note"}


@router.post("/ingest/file")
async def ingest_file(
    file: UploadFile = File(...),
    source_type: str = Form(default="note"),
    source_id: str | None = Form(default=None),
):
    settings = get_settings()
    data = await file.read()

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail="File too large")

    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported file type")
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise HTTPException(status_code=400, detail="source_type must be one of: resume, jd, note")

    try:
        text = extract_text_from_upload(filename, file.content_type, data)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    if not text.strip():
        raise HTTPException(status_code=422, detail="No extractable text found in file")

    text_hash = content_sha256(text)
    if not source_id:
        existing_source_id = find_source_id_by_content_hash(
            source_type=source_type,
            content_sha256=text_hash,
        )
        if existing_source_id:
            logger.info("ingest_file reused source_id=%s", existing_source_id)
            return {
                "ok": True,
                "source_type": source_type,
                "source_id": existing_source_id,
                "chunks": 0,
                "reused": True,
            }
        source_id = generate_upload_source_id(source_type, text_hash)

    file_sha256 = hashlib.sha256(data).hexdigest()
    metadata = {
        "source_type": source_type,
        "source_id": source_id,
        "filename": filename,
        "content_type": file.content_type,
        "file_sha256": file_sha256,
        "content_sha256": text_hash,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }

    result = ingest_text(
        text,
        source_type=source_type,
        source_id=source_id,
        metadata=metadata,
    )

    logger.info("ingest_file source_id=%s chunks=%s", source_id, result.get("chunks", 0))

    return {
        "ok": True,
        "source_type": source_type,
        "source_id": source_id,
        "chunks": result.get("chunks", 0),
        "reused": False,
    }
