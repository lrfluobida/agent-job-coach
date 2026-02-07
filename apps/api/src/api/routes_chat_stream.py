import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.core.output_coercion import coerce_model_output, shorten_quote
from src.graph.job_coach_graph import run_graph


router = APIRouter()


class ChatStreamRequest(BaseModel):
    question: str
    top_k: int = Field(default=5, ge=1, le=20)
    filter: dict | None = None


def _sse_event(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _chunk_text(text: str, size: int = 48) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


@router.post("/chat/stream")
async def chat_stream(payload: ChatStreamRequest):
    async def event_generator():
        try:
            yield _sse_event("status", {"stage": "retrieve", "message": "检索中..."})
            yield _sse_event("status", {"stage": "generate", "message": "生成回答..."})
            result = run_graph(payload.question, top_k=payload.top_k, filter=payload.filter)

            answer, _ = coerce_model_output(result.get("answer", ""))
            for chunk in _chunk_text(answer):
                yield _sse_event("token", {"delta": chunk})

            yield _sse_event("status", {"stage": "finalize", "message": "整理引用..."})
            candidate_map = {
                c.get("id"): c
                for c in (result.get("used_context", []) or [])
                if isinstance(c, dict)
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
            yield _sse_event(
                "context",
                {
                    "citations": citations,
                    "used_context": result.get("used_context", []),
                },
            )
            yield _sse_event("done", {"ok": True})
        except Exception as exc:
            yield _sse_event("error", {"ok": False, "error": str(exc)})

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers=headers,
    )

