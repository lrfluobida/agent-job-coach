from fastapi import APIRouter
from pydantic import BaseModel

from src.ingest.pipeline import ingest_text


router = APIRouter()


class IngestRequest(BaseModel):
    source_id: str
    source_type: str
    text: str


@router.post("/ingest")
def ingest(payload: IngestRequest):
    result = ingest_text(
        payload.text,
        source_type=payload.source_type,
        source_id=payload.source_id,
        metadata={},
    )
    return {"ok": True, "collection": "job_coach", "added": result.get("chunks", 0)}
