import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.core.settings import get_settings
from src.ingest.pipeline import (
    ALLOWED_EXTENSIONS,
    extract_text_from_upload,
    generate_upload_source_id,
    ingest_text,
)


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ingest/file")
async def ingest_file(
    file: UploadFile = File(...),
    source_type: str = Form(default="upload"),
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

    try:
        text = extract_text_from_upload(filename, file.content_type, data)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc

    if not source_id:
        source_id = generate_upload_source_id(filename, data)

    sha256 = hashlib.sha256(data).hexdigest()
    metadata = {
        "source_type": source_type,
        "source_id": source_id,
        "filename": filename,
        "content_type": file.content_type,
        "sha256": sha256,
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
    }
