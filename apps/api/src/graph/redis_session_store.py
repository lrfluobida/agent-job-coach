from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone

from redis.exceptions import RedisError

from src.core.redis_client import get_redis_client
from src.core.settings import get_settings


_LOCK_RELEASE_LUA = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
  return redis.call("DEL", KEYS[1])
else
  return 0
end
"""


def _safe_conversation_id(conversation_id: str) -> str:
    cid = (conversation_id or "").strip()
    cid = re.sub(r"[^a-zA-Z0-9:_-]", "_", cid)
    return cid


def _state_key(conversation_id: str) -> str:
    cid = _safe_conversation_id(conversation_id)
    return f"jc:{{{cid}}}:state"


def _asked_key(conversation_id: str) -> str:
    cid = _safe_conversation_id(conversation_id)
    return f"jc:{{{cid}}}:asked"


def _request_key(conversation_id: str) -> str:
    cid = _safe_conversation_id(conversation_id)
    return f"jc:{{{cid}}}:req"


def _lock_key(conversation_id: str) -> str:
    cid = _safe_conversation_id(conversation_id)
    return f"jc:{{{cid}}}:lock"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def assert_redis_available() -> None:
    client = get_redis_client()
    try:
        client.ping()
    except RedisError as exc:
        raise RuntimeError(f"Redis unavailable: {exc}") from exc


def get_resume_interview_state(conversation_id: str) -> dict:
    cid = _safe_conversation_id(conversation_id)
    if not cid:
        return {}
    client = get_redis_client()
    try:
        raw = client.hget(_state_key(cid), "resume_interview_state")
        state = json.loads(raw) if raw else {}
        if not isinstance(state, dict):
            state = {}
        asked_ids = list(client.smembers(_asked_key(cid)))
        if asked_ids:
            state["asked_question_ids"] = asked_ids
        return state
    except RedisError as exc:
        raise RuntimeError(f"Redis read session failed: {exc}") from exc


def set_resume_interview_state(conversation_id: str, state: dict) -> None:
    cid = _safe_conversation_id(conversation_id)
    if not cid:
        return
    if not isinstance(state, dict):
        return
    client = get_redis_client()
    asked_ids = state.get("asked_question_ids")
    asked = asked_ids if isinstance(asked_ids, list) else []
    cleaned_asked = [str(item).strip() for item in asked if str(item).strip()]

    state_body = dict(state)
    state_body.pop("asked_question_ids", None)

    try:
        pipe = client.pipeline()
        pipe.hset(
            _state_key(cid),
            mapping={
                "resume_interview_state": json.dumps(state_body, ensure_ascii=False),
                "updated_at": _now_iso(),
            },
        )
        if cleaned_asked:
            pipe.sadd(_asked_key(cid), *cleaned_asked)
        pipe.execute()
    except RedisError as exc:
        raise RuntimeError(f"Redis write session failed: {exc}") from exc


def get_request_result(conversation_id: str, request_id: str) -> dict | None:
    cid = _safe_conversation_id(conversation_id)
    rid = (request_id or "").strip()
    if not cid or not rid:
        return None
    client = get_redis_client()
    try:
        raw = client.hget(_request_key(cid), rid)
    except RedisError as exc:
        raise RuntimeError(f"Redis read request result failed: {exc}") from exc
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def set_request_result(conversation_id: str, request_id: str, result: dict) -> None:
    cid = _safe_conversation_id(conversation_id)
    rid = (request_id or "").strip()
    if not cid or not rid:
        return
    if not isinstance(result, dict):
        return
    client = get_redis_client()
    payload = json.dumps(result, ensure_ascii=False)
    try:
        client.hset(_request_key(cid), rid, payload)
    except RedisError as exc:
        raise RuntimeError(f"Redis write request result failed: {exc}") from exc


def acquire_conversation_lock(conversation_id: str, owner_token: str) -> bool:
    cid = _safe_conversation_id(conversation_id)
    owner = (owner_token or "").strip()
    if not cid or not owner:
        return False
    cfg = get_settings()
    wait_ms = max(0, int(cfg.redis_lock_wait_ms))
    ttl_ms = max(1000, int(cfg.redis_lock_ttl_ms))
    client = get_redis_client()
    deadline = time.monotonic() + (wait_ms / 1000.0)
    try:
        while True:
            locked = client.set(_lock_key(cid), owner, nx=True, px=ttl_ms)
            if locked:
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)
    except RedisError as exc:
        raise RuntimeError(f"Redis acquire lock failed: {exc}") from exc


def release_conversation_lock(conversation_id: str, owner_token: str) -> None:
    cid = _safe_conversation_id(conversation_id)
    owner = (owner_token or "").strip()
    if not cid or not owner:
        return
    client = get_redis_client()
    try:
        client.eval(_LOCK_RELEASE_LUA, 1, _lock_key(cid), owner)
    except RedisError as exc:
        raise RuntimeError(f"Redis release lock failed: {exc}") from exc

