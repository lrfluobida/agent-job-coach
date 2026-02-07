from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import time

from src.ingest.pipeline import ingest_text
from src.rag.service import retrieve
from src.skills.interview_qa import run_interview_turn
from src.tools.mcp_client import mcp_call_tool, mcp_list_tools
import hashlib

logger = logging.getLogger(__name__)

_TOOL_SPECS_CACHE: list["ToolSpec"] | None = None
_TOOL_SPECS_CACHE_AT: float = 0.0


def _tool_specs_ttl_s() -> float:
    try:
        return float(os.getenv("TOOL_SPECS_CACHE_TTL_S", "30"))
    except Exception:
        return 30.0


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    json_schema: dict


def _builtin_tools() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="skill_interview_qa",
            description="模拟技术面试：评估候选人回答并发起下一轮深度追问",
            json_schema={
                "type": "object",
                "properties": {
                    "user_input": {"type": "string"},
                    "history": {"type": "array", "default": []},
                    "topic": {"type": ["string", "null"]},
                },
                "required": ["user_input"],
            },
        ),
        ToolSpec(
            name="rag_retrieve",
            description="向量检索：返回 top_k 相关内容",
            json_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "default": 5},
                    "filter": {"type": ["object", "null"]},
                },
                "required": ["query"],
            },
        ),
        ToolSpec(
            name="ingest_text",
            description="导入纯文本到知识库",
            json_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "source_type": {"type": "string", "default": "note"},
                    "source_id": {"type": ["string", "null"]},
                },
                "required": ["text"],
            },
        ),
    ]


def _mcp_tools() -> list[ToolSpec]:
    tools = []
    for item in mcp_list_tools():
        tools.append(
            ToolSpec(
                name=f"mcp:{item.get('name')}",
                description=item.get("description", ""),
                json_schema=item.get("input_schema", {}) or {},
            )
        )
    return tools


def get_tool_specs() -> list[ToolSpec]:
    global _TOOL_SPECS_CACHE, _TOOL_SPECS_CACHE_AT
    now = time.time()
    ttl = _tool_specs_ttl_s()
    if _TOOL_SPECS_CACHE is not None and (now - _TOOL_SPECS_CACHE_AT) < ttl:
        return _TOOL_SPECS_CACHE

    specs = _builtin_tools() + _mcp_tools()
    _TOOL_SPECS_CACHE = specs
    _TOOL_SPECS_CACHE_AT = now
    return specs


def call_tool(name: str, args: dict, *, context: dict | None = None) -> dict:
    context = context or {}
    logger.info("tool_call name=%s", name)
    if name == "skill_interview_qa":
        user_input = args.get("user_input") or args.get("question", "")
        history = args.get("history")
        if history is None:
            history = context.get("history", [])
        topic = args.get("topic")
        if topic is None:
            topic = context.get("topic")

        try:
            answer = run_interview_turn.func(
                user_input=user_input,
                history=history or [],
                topic=topic,
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        return {
            "ok": True,
            "answer": answer,
            "citations": [],
            "used_context": context.get("used_context", []),
        }
    if name == "rag_retrieve":
        where = None
        filter_obj = args.get("filter")
        if filter_obj:
            where = {}
            source_type = filter_obj.get("source_type")
            source_id = filter_obj.get("source_id")
            if source_type:
                where["source_type"] = source_type
            if source_id:
                where["source_id"] = source_id
        results = retrieve(args.get("query", ""), top_k=int(args.get("top_k", 5)), where=where)
        return {"results": results}
    if name == "ingest_text":
        source_type = args.get("source_type", "note")
        source_id = args.get("source_id") or context.get("source_id")
        if not source_id:
            text = args.get("text", "")
            digest8 = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
            source_id = f"note_{digest8}"
        return ingest_text(
            args.get("text", ""),
            source_type=source_type,
            source_id=source_id,
            metadata={},
        )
    if name.startswith("mcp:"):
        return mcp_call_tool(name.split(":", 1)[1], args)

    return {"ok": False, "error": f"Unknown tool: {name}"}

