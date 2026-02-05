import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.ingest.pipeline import ingest_text


router = APIRouter()


class IngestRequest(BaseModel):
    source_type: str
    text: str
    source_id: str | None = None


@router.post("/ingest")
def ingest(payload: IngestRequest):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="text is required")

    source_id = payload.source_id
    if not source_id:
        sha8 = hashlib.sha256(payload.text.encode("utf-8")).hexdigest()[:8]
        date_tag = datetime.now(timezone.utc).strftime("%Y%m%d")
        source_id = f"{payload.source_type}_{date_tag}_{sha8}"

    result = ingest_text(
        payload.text,
        source_type=payload.source_type,
        source_id=source_id,
        metadata={},
    )
    return {
        "ok": True,
        "collection": "job_coach",
        "added": result.get("chunks", 0),
        "source_id": source_id,
    }
