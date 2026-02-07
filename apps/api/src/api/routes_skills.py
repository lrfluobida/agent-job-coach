from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.skills.interview_qa import run_interview_turn


router = APIRouter()


class InterviewQARequest(BaseModel):
    user_input: str | None = None
    question: str | None = None
    history: list = Field(default_factory=list)
    topic: str | None = None


@router.post("/skills/interview_qa")
def interview_qa(payload: InterviewQARequest):
    user_input = payload.user_input or payload.question or ""
    if not user_input.strip():
        return {"ok": False, "error": "user_input is required"}

    try:
        answer = run_interview_turn.func(
            user_input=user_input,
            history=payload.history,
            topic=payload.topic,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    return {"ok": True, "answer": answer, "citations": [], "used_context": []}
