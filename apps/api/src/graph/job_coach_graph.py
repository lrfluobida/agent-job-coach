from __future__ import annotations

import json
import logging
from typing import TypedDict

from src.core.output_coercion import (
    coerce_model_output,
    extract_citation_markers,
    shorten_quote,
    strip_citation_markers,
)
from src.core.settings import get_settings
from src.llm.zhipu import chat
from src.rag.service import retrieve
from src.tools.registry import call_tool, get_tool_specs

logger = logging.getLogger(__name__)

class GraphState(TypedDict, total=False):
    question: str
    top_k: int
    filter: dict | None
    where: dict | None
    used_context: list[dict]
    tool_plan: list[dict]
    tool_results: list[dict]
    answer: str
    citations: list[dict]


def _build_where(filter_dict: dict | None) -> dict | None:
    if not filter_dict:
        return None
    where: dict = {}
    source_type = filter_dict.get("source_type")
    source_id = filter_dict.get("source_id")
    if source_type:
        where["source_type"] = source_type
    if source_id:
        where["source_id"] = source_id
    return where or None


def _normalize_citations(
    citations: list[dict] | list[str] | None,
    candidate_map: dict[str, dict],
    max_citations: int,
) -> list[dict]:
    if not citations:
        return []
    normalized: list[dict] = []
    for item in citations:
        if isinstance(item, str):
            ctx = candidate_map.get(item, {})
            normalized.append({"id": item, "quote": shorten_quote(ctx.get("text", ""))})
        elif isinstance(item, dict):
            cid = item.get("id")
            if not cid:
                continue
            quote = item.get("quote")
            if not quote:
                ctx = candidate_map.get(cid, {})
                quote = ctx.get("text", "")
            normalized.append({"id": cid, "quote": shorten_quote(quote or "")})
        if len(normalized) >= max_citations:
            break
    return normalized


def normalize_input(state: GraphState) -> GraphState:
    top_k = state.get("top_k", 5)
    top_k = max(1, min(20, int(top_k)))
    return {
        **state,
        "top_k": top_k,
        "where": _build_where(state.get("filter")),
    }


def retrieve_evidence(state: GraphState) -> GraphState:
    top_k = min(8, int(state.get("top_k", 5)))
    results = retrieve(state.get("question", ""), top_k=top_k, where=state.get("where"))
    return {**state, "used_context": results}


def _plan_with_llm(question: str, tool_specs: list[dict]) -> list[dict]:
    prompt = {
        "role": "user",
        "content": (
            "你是工具规划器。只能从提供的工具列表中选择。\n"
            "输出严格 JSON，格式：{\"tool_plan\":[{\"name\":\"...\",\"args\":{...}}]}。\n"
            f"问题：{question}\n工具列表：{json.dumps(tool_specs, ensure_ascii=False)}"
        ),
    }
    content = chat([prompt])
    try:
        data = json.loads(content)
        plan = data.get("tool_plan", [])
        return plan if isinstance(plan, list) else []
    except Exception:
        return []


def plan_tools(state: GraphState) -> GraphState:
    question = state.get("question", "")
    tool_specs = [
        {
            "name": t.name,
            "description": t.description,
            "json_schema": t.json_schema,
        }
        for t in get_tool_specs()
    ]

    settings = get_settings()
    if settings.zhipu_api_key:
        plan = _plan_with_llm(question, tool_specs)
        allowed = {t["name"] for t in tool_specs}
        plan = [p for p in plan if isinstance(p, dict) and p.get("name") in allowed]
        return {**state, "tool_plan": plan}

    keywords = ["面试", "自我介绍", "项目", "如何回答", "怎么说"]
    if any(k in question for k in keywords):
        return {
            **state,
            "tool_plan": [
                {"name": "skill_interview_qa", "args": {"question": question, "top_k": state.get("top_k", 5), "filter": state.get("filter")}}
            ],
        }
    return {**state, "tool_plan": []}


def execute_tools(state: GraphState) -> GraphState:
    tool_plan = state.get("tool_plan", [])
    results = []
    for item in tool_plan:
        name = item.get("name")
        args = item.get("args") or {}
        if not name:
            continue
        results.append({"name": name, "result": call_tool(name, args, context={})})
    return {**state, "tool_results": results}


def _generate_with_llm(state: GraphState) -> GraphState:
    used_context = state.get("used_context", [])
    evidence = "\n".join([f"[[{c['id']}]] {c.get('text', '')}" for c in used_context])
    prompt = (
        "你是面试辅导助手，只能依据【证据块】回答，禁止编造。"
        "输出必须是 Markdown 自然语言文本，不要输出 JSON，不要使用 ``` 代码块。"
        "如果需要引用，请使用 [@chunk_id] 形式的标记（例如 [@resume_001:0]）。"
        "不要在答案里输出 citations 或 used_context。\n"
        f"问题：{state.get('question','')}\n【证据块】\n{evidence}"
    )
    content = chat([{"role": "user", "content": prompt}])
    answer, extra_citations = coerce_model_output(content)
    citations = state.get("citations", []) or []
    if not citations and extra_citations:
        citations = extra_citations
    return {**state, "answer": answer, "citations": citations}


def generate_final(state: GraphState) -> GraphState:
    for item in state.get("tool_results", []):
        if item.get("name") == "skill_interview_qa":
            result = item.get("result", {})
            answer_text = coerce_model_output(result.get("answer", ""))[0]
            tool_citations = _normalize_citations(
                result.get("citations", []),
                {c.get("id"): c for c in result.get("used_context", []) if isinstance(c, dict)},
                get_settings().max_citations,
            )
            logger.info("graph tool citations used: %s", len(tool_citations))
            return {
                **state,
                "answer": answer_text,
                "citations": tool_citations,
                "used_context": result.get("used_context", state.get("used_context", [])),
            }

    settings = get_settings()
    if settings.zhipu_api_key:
        state = _generate_with_llm(state)
        # Use inline citation markers to build actual citations
        markers = extract_citation_markers(state.get("answer", ""))
        if markers:
            logger.info("graph markers found: %s", len(markers))
        max_citations = settings.max_citations
        candidate_map = {c.get("id"): c for c in state.get("used_context", [])}
        marker_citations = []
        for marker in markers:
            if marker in candidate_map:
                ctx = candidate_map[marker]
                marker_citations.append(
                    {"id": marker, "quote": shorten_quote(ctx.get("text", ""))}
                )
            if len(marker_citations) >= max_citations:
                break

        citations = state.get("citations", []) or []
        if not citations and marker_citations:
            citations = marker_citations
        if not citations and state.get("used_context"):
            top_ctx = state["used_context"][0]
            if isinstance(top_ctx, dict) and top_ctx.get("id"):
                citations = [
                    {
                        "id": top_ctx.get("id"),
                        "quote": shorten_quote(top_ctx.get("text", "")),
                    }
                ]

        # Strip markers from final answer for display
        answer_clean = strip_citation_markers(state.get("answer", ""))
        citations = _normalize_citations(citations, candidate_map, max_citations)

        logger.info(
            "graph citations: tool=%s markers=%s final=%s",
            bool(state.get("citations")),
            len(marker_citations),
            len(citations),
        )

        return {**state, "answer": answer_clean, "citations": citations}

    # fallback without LLM
    used_context = state.get("used_context", [])
    if used_context:
        return {
            **state,
            "answer": used_context[0].get("text", "")[:200],
            "citations": [{"id": used_context[0].get("id", ""), "quote": used_context[0].get("text", "")[:120]}],
        }
    return {**state, "answer": "暂无可用证据，请先导入资料后再提问。", "citations": []}


try:
    from langgraph.graph import StateGraph

    _LANGGRAPH_AVAILABLE = True
except Exception:
    _LANGGRAPH_AVAILABLE = False


def _build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("normalize_input", normalize_input)
    graph.add_node("retrieve_evidence", retrieve_evidence)
    graph.add_node("plan_tools", plan_tools)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("generate_final", generate_final)

    graph.set_entry_point("normalize_input")
    graph.add_edge("normalize_input", "retrieve_evidence")
    graph.add_edge("retrieve_evidence", "plan_tools")

    def _route_tools(state: GraphState):
        return "execute_tools" if state.get("tool_plan") else "generate_final"

    graph.add_conditional_edges("plan_tools", _route_tools)
    graph.add_edge("execute_tools", "generate_final")
    graph.set_finish_point("generate_final")
    return graph.compile()


_GRAPH = _build_graph() if _LANGGRAPH_AVAILABLE else None


def run_graph(question: str, top_k: int = 5, filter: dict | None = None) -> dict:
    state: GraphState = {"question": question, "top_k": top_k, "filter": filter}
    if _GRAPH is not None:
        result = _GRAPH.invoke(state)
    else:
        state = normalize_input(state)
        state = retrieve_evidence(state)
        state = plan_tools(state)
        if state.get("tool_plan"):
            state = execute_tools(state)
        state = generate_final(state)
        result = state

    return {
        "answer": result.get("answer", ""),
        "citations": result.get("citations", []),
        "used_context": result.get("used_context", result.get("used_context", [])),
        "tool_results": result.get("tool_results", []),
    }
