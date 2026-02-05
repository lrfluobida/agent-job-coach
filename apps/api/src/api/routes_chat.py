from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.core.output_coercion import coerce_model_output, shorten_quote
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
    answer, _ = coerce_model_output(result.get("answer", ""))
    candidate_map = {
        c.get("id"): c for c in (result.get("used_context", []) or []) if isinstance(c, dict)
    }
    citations: list[dict] = []
    for item in (result.get("citations", []) or []):
        if isinstance(item, str):
            ctx = candidate_map.get(item, {})
            citations.append({"id": item, "quote": shorten_quote(ctx.get("text", ""))})
        elif isinstance(item, dict):
            cid = item.get("id")
            if not cid:
                continue
            quote = item.get("quote") or candidate_map.get(cid, {}).get("text", "")
            citations.append({"id": cid, "quote": shorten_quote(quote)})
    return {
        "ok": True,
        "answer": answer,
        "citations": citations,
        "used_context": result.get("used_context", []),
    }
