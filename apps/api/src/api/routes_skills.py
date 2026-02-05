from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.skills.interview_qa import run_interview_qa


router = APIRouter()


class InterviewQARequest(BaseModel):
    question: str
    top_k: int = Field(default=5, ge=1, le=20)
    filter: dict | None = None


@router.post("/skills/interview_qa")
def interview_qa(payload: InterviewQARequest):
    where = None
    if payload.filter:
        where = {}
        source_type = payload.filter.get("source_type")
        source_id = payload.filter.get("source_id")
        if source_type:
            where["source_type"] = source_type
        if source_id:
            where["source_id"] = source_id

    return run_interview_qa(
        payload.question,
        top_k=payload.top_k,
        where=where,
    )
