from __future__ import annotations

import json
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.core.output_coercion import coerce_model_output, shorten_quote
from src.graph.job_coach_graph import run_graph
from src.graph.redis_session_store import (
    acquire_conversation_lock,
    assert_redis_available,
    get_request_result,
    get_resume_interview_state,
    release_conversation_lock,
    set_request_result,
    set_resume_interview_state,
)
from src.rag.store import get_collection


router = APIRouter()


class ChatStreamRequest(BaseModel):
    question: str
    top_k: int = Field(default=5, ge=1, le=20)
    filter: dict | None = None
    history: list = Field(default_factory=list)
    topic: str | None = None
    mode: str | None = None
    active_source_id: str | None = None
    active_source_type: str | None = None
    conversation_id: str | None = None
    request_id: str | None = None


def _sse_event(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _chunk_text(text: str, size: int = 48) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


def _requires_redis_session(payload: ChatStreamRequest) -> bool:
    return (
        (payload.mode or "chat") == "resume_interview"
        and (payload.active_source_type or "") == "resume"
        and bool((payload.active_source_id or "").strip())
    )


def _invoke_graph(
    payload: ChatStreamRequest,
    *,
    conversation_id: str,
    resume_state: dict,
) -> dict:
    history = list(payload.history or [])
    session = {
        "mode": payload.mode or "chat",
        "active_source_id": payload.active_source_id,
        "active_source_type": payload.active_source_type,
        "conversation_id": conversation_id,
        "resume_interview_state": resume_state,
    }
    history.insert(0, {"role": "system", "content": f"__SESSION__:{json.dumps(session, ensure_ascii=False)}"})
    return run_graph(payload.question, history)


def _extract_citation_ids(citations: object) -> list[str]:
    if not isinstance(citations, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in citations:
        if isinstance(item, str):
            cid = item.strip()
        elif isinstance(item, dict):
            cid = str(item.get("id", "")).strip()
        else:
            cid = ""
        if not cid or cid in seen:
            continue
        seen.add(cid)
        out.append(cid)
    return out


def _compact_result_for_request_cache(result: dict) -> dict:
    return {
        "answer": str(result.get("answer", "")),
        "citation_ids": _extract_citation_ids(result.get("citations")),
    }


def _load_context_by_ids(citation_ids: list[str]) -> list[dict]:
    ids = [cid for cid in citation_ids if isinstance(cid, str) and cid.strip()]
    if not ids:
        return []
    collection = get_collection()
    raw = collection.get(ids=ids, include=["documents", "metadatas"])
    got_ids = raw.get("ids") or []
    docs = raw.get("documents") or []
    metas = raw.get("metadatas") or []

    by_id: dict[str, dict] = {}
    for idx, cid in enumerate(got_ids):
        if not isinstance(cid, str):
            continue
        by_id[cid] = {
            "id": cid,
            "text": str(docs[idx]) if idx < len(docs) else "",
            "metadata": metas[idx] if idx < len(metas) and isinstance(metas[idx], dict) else {},
            "score": 0.0,
        }

    return [by_id[cid] for cid in ids if cid in by_id]


def _result_from_cached_payload(cached: dict) -> dict:
    answer = str(cached.get("answer", ""))
    citation_ids = _extract_citation_ids(cached.get("citation_ids"))
    if not citation_ids:
        citation_ids = _extract_citation_ids(cached.get("citations"))

    used_context = cached.get("used_context")
    if not isinstance(used_context, list) or not used_context:
        used_context = _load_context_by_ids(citation_ids)

    return {
        "answer": answer,
        "citations": citation_ids,
        "used_context": used_context,
    }


@router.post("/chat/stream")
async def chat_stream(payload: ChatStreamRequest):
    async def event_generator():
        try:
            yield _sse_event("status", {"stage": "retrieve", "message": "检索中..."})
            yield _sse_event("status", {"stage": "generate", "message": "生成回答..."})

            conversation_id = (payload.conversation_id or "").strip() or f"conv_{uuid.uuid4().hex}"
            request_id = (payload.request_id or "").strip() or f"req_{uuid.uuid4().hex}"
            result: dict

            if _requires_redis_session(payload):
                assert_redis_available()
                lock_token = f"lock_{uuid.uuid4().hex}"
                if not acquire_conversation_lock(conversation_id, lock_token):
                    raise RuntimeError("会话正在处理中，请稍后重试。")
                try:
                    cached = get_request_result(conversation_id, request_id)
                    if isinstance(cached, dict):
                        result = _result_from_cached_payload(cached)
                    else:
                        resume_state = get_resume_interview_state(conversation_id)
                        result = _invoke_graph(
                            payload,
                            conversation_id=conversation_id,
                            resume_state=resume_state,
                        )
                        next_session = result.get("session") if isinstance(result.get("session"), dict) else {}
                        next_resume_state = (
                            next_session.get("resume_interview_state")
                            if isinstance(next_session.get("resume_interview_state"), dict)
                            else {}
                        )
                        set_resume_interview_state(conversation_id, next_resume_state)
                        set_request_result(
                            conversation_id,
                            request_id,
                            _compact_result_for_request_cache(result),
                        )
                finally:
                    release_conversation_lock(conversation_id, lock_token)
            else:
                result = _invoke_graph(payload, conversation_id=conversation_id, resume_state={})

            answer, _ = coerce_model_output(result.get("answer", ""))
            for chunk in _chunk_text(answer):
                yield _sse_event("token", {"delta": chunk})

            yield _sse_event("status", {"stage": "finalize", "message": "整理引用..."})
            candidate_map = {c.get("id"): c for c in (result.get("used_context", []) or []) if isinstance(c, dict)}
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
                    "conversation_id": conversation_id,
                    "request_id": request_id,
                },
            )
            yield _sse_event("done", {"ok": True, "conversation_id": conversation_id, "request_id": request_id})
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

