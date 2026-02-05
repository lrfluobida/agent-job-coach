from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.graph.job_coach_graph import run_graph


router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    top_k: int = Field(default=5, ge=1, le=20)
    filter: dict | None = None


@router.get("/chat/ping")
def chat_ping():
    return {"ok": True}


@router.post("/chat")
def chat(payload: ChatRequest):
    result = run_graph(payload.question, top_k=payload.top_k, filter=payload.filter)
    return {
        "ok": True,
        "answer": result.get("answer", ""),
        "citations": result.get("citations", []),
        "used_context": result.get("used_context", []),
    }
