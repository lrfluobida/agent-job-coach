from __future__ import annotations

import json
import re
import uuid
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from src.llm.zhipu import chat
from src.skills.interview_qa import run_interview_turn, run_resume_interview_turn

try:
    from langgraph.graph import END, START, StateGraph
    from langgraph.graph.message import add_messages
    from langgraph.prebuilt import ToolNode

    _LANGGRAPH_AVAILABLE = True
except Exception:
    END = "__end__"
    START = "__start__"

    def add_messages(x):  # type: ignore
        return x

    ToolNode = None  # type: ignore
    _LANGGRAPH_AVAILABLE = False

SESSION_MARKER = "__SESSION__:"
DEFAULT_SESSION = {
    "mode": "chat",
    "active_source_id": None,
    "active_source_type": None,
}


class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    session: dict


_TOOLS = [run_interview_turn, run_resume_interview_turn]
_TOOL_NODE = ToolNode(_TOOLS) if _LANGGRAPH_AVAILABLE else None


def _ensure_str(value) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def _extract_json(text: str) -> dict | None:
    raw = _ensure_str(text).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _parse_tool_payload(content: str) -> dict | None:
    data = _extract_json(content)
    if not isinstance(data, dict):
        return None
    if "answer" not in data:
        return None
    return data


def _history_to_lc_messages(history: list | None) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for item in history or []:
        if isinstance(item, dict):
            role = item.get("role")
            content = _ensure_str(item.get("content", ""))
            if role == "system":
                messages.append(SystemMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
            elif role == "tool":
                messages.append(ToolMessage(content=content, tool_call_id=item.get("tool_call_id", "history_tool")))
            else:
                messages.append(HumanMessage(content=content))
        else:
            messages.append(HumanMessage(content=_ensure_str(item)))
    return messages


def _to_openai_messages(messages: list[BaseMessage]) -> list[dict]:
    out: list[dict] = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            out.append({"role": "system", "content": _ensure_str(msg.content)})
        elif isinstance(msg, HumanMessage):
            out.append({"role": "user", "content": _ensure_str(msg.content)})
        elif isinstance(msg, AIMessage):
            out.append({"role": "assistant", "content": _ensure_str(msg.content)})
        elif isinstance(msg, ToolMessage):
            out.append({"role": "tool", "content": _ensure_str(msg.content)})
    return out


def _latest_user_input(messages: list[BaseMessage]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return _ensure_str(msg.content)
    return ""


def _history_for_tool(messages: list[BaseMessage]) -> list[dict]:
    history: list[dict] = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            history.append({"role": "user", "content": _ensure_str(msg.content)})
        elif isinstance(msg, AIMessage) and not msg.tool_calls:
            history.append({"role": "assistant", "content": _ensure_str(msg.content)})
    return history


def _extract_session_from_history(history: list | None) -> tuple[list, dict]:
    session = dict(DEFAULT_SESSION)
    cleaned: list = []
    for item in history or []:
        if isinstance(item, dict) and item.get("role") == "system":
            content = _ensure_str(item.get("content", ""))
            if content.startswith(SESSION_MARKER):
                payload = content[len(SESSION_MARKER) :].strip()
                data = _extract_json(payload)
                if isinstance(data, dict):
                    session.update(
                        {
                            "mode": data.get("mode", session["mode"]),
                            "active_source_id": data.get("active_source_id", session["active_source_id"]),
                            "active_source_type": data.get("active_source_type", session["active_source_type"]),
                        }
                    )
                continue
        cleaned.append(item)
    return cleaned, session


def _build_router_prompt(session: dict) -> str:
    return (
        "You are a senior AI job coach. Decide user intent intelligently.\n"
        "If the user wants mock interview, call interview tools; if casual chat, answer directly.\n"
        "Tools:\n"
        "1) run_interview_turn(user_input, history, topic)\n"
        "2) run_resume_interview_turn(user_input, history, source_id, top_k)\n\n"
        f"Current mode: {session.get('mode')}\n"
        f"Current bound source: source_type={session.get('active_source_type')}, "
        f"source_id={session.get('active_source_id')}\n\n"
        "Policy:\n"
        "- If user asks resume-focused mock interview and resume source is bound, use run_resume_interview_turn.\n"
        "- If user asks technical interview but resume is not bound, use run_interview_turn.\n"
        "- For casual chat, answer directly.\n"
        "Output JSON only:\n"
        'Tool: {"action":"tool","name":"run_resume_interview_turn","args":{...}}\n'
        'Direct: {"action":"final","answer":"..."}'
    )


def _normalize_tool_args(name: str, args: dict, messages: list[BaseMessage], session: dict) -> dict:
    normalized = dict(args)
    if not _ensure_str(normalized.get("user_input", "")).strip():
        normalized["user_input"] = _latest_user_input(messages)
    if "history" not in normalized:
        normalized["history"] = _history_for_tool(messages)
    if name == "run_resume_interview_turn":
        normalized.setdefault("source_id", session.get("active_source_id"))
        normalized.setdefault("top_k", 6)
    else:
        normalized.setdefault("topic", None)
    return normalized


def _infer_tool(decision: dict, session: dict, messages: list[BaseMessage]) -> tuple[str, dict] | None:
    name = _ensure_str(decision.get("name"))
    args = decision.get("args") if isinstance(decision.get("args"), dict) else {}
    latest = _latest_user_input(messages).lower()
    wants_resume_interview = any(
        key in latest for key in ["resume", "interview", "mock", "question", "ask me"]
    )

    if decision.get("action") == "tool" and name in {"run_interview_turn", "run_resume_interview_turn"}:
        if name == "run_resume_interview_turn" and not session.get("active_source_id"):
            return "run_interview_turn", _normalize_tool_args("run_interview_turn", args, messages, session)
        return name, _normalize_tool_args(name, args, messages, session)

    if (
        session.get("active_source_type") == "resume"
        and session.get("active_source_id")
        and (session.get("mode") == "resume_interview" or wants_resume_interview)
    ):
        return "run_resume_interview_turn", _normalize_tool_args(
            "run_resume_interview_turn",
            args,
            messages,
            session,
        )

    if wants_resume_interview:
        return "run_interview_turn", _normalize_tool_args("run_interview_turn", args, messages, session)

    return None


def agent_node(state: AgentState) -> AgentState:
    messages = state.get("messages", [])
    session = state.get("session") or dict(DEFAULT_SESSION)

    if messages and isinstance(messages[-1], ToolMessage):
        payload = _parse_tool_payload(_ensure_str(messages[-1].content))
        if payload:
            return {"messages": [AIMessage(content=_ensure_str(payload.get("answer", "")))]}
        return {"messages": [AIMessage(content=_ensure_str(messages[-1].content))]}

    # Deterministic routing for resume interview mode to reduce model routing drift.
    if (
        session.get("mode") == "resume_interview"
        and session.get("active_source_type") == "resume"
        and session.get("active_source_id")
    ):
        call_id = f"call_{uuid.uuid4().hex[:10]}"
        return {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": call_id,
                            "name": "run_resume_interview_turn",
                            "args": {
                                "user_input": _latest_user_input(messages),
                                "history": _history_for_tool(messages),
                                "source_id": _ensure_str(session.get("active_source_id")),
                                "top_k": 6,
                            },
                        }
                    ],
                )
            ]
        }

    router_prompt = _build_router_prompt(session)
    prompt_messages: list[BaseMessage] = [SystemMessage(content=router_prompt), *messages]
    raw = chat(_to_openai_messages(prompt_messages))
    decision = _extract_json(raw) or {}
    tool_plan = _infer_tool(decision, session, messages)

    if tool_plan:
        name, args = tool_plan
        call_id = f"call_{uuid.uuid4().hex[:10]}"
        return {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": call_id,
                            "name": name,
                            "args": args,
                        }
                    ],
                )
            ]
        }

    answer = _ensure_str(decision.get("answer") or raw).strip()
    return {"messages": [AIMessage(content=answer)]}


def _route_next(state: AgentState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return END
    last = messages[-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


def _build_graph():
    if not _LANGGRAPH_AVAILABLE or _TOOL_NODE is None:
        return None
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", _TOOL_NODE)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", _route_next, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile()


_GRAPH = _build_graph()


def run_graph(question: str, history: list | None = None) -> dict:
    clean_history, session = _extract_session_from_history(history)
    input_messages: list[BaseMessage] = [
        *_history_to_lc_messages(clean_history),
        HumanMessage(content=_ensure_str(question)),
    ]

    if _GRAPH is None:
        router_prompt = _build_router_prompt(session)
        raw = chat(_to_openai_messages([SystemMessage(content=router_prompt), *input_messages]))
        decision = _extract_json(raw) or {}
        tool_plan = _infer_tool(decision, session, input_messages)
        if tool_plan:
            name, args = tool_plan
            if name == "run_resume_interview_turn":
                tool_answer = run_resume_interview_turn.func(
                    user_input=_ensure_str(args.get("user_input", "")),
                    history=args.get("history") or [],
                    source_id=_ensure_str(args.get("source_id", "")),
                    top_k=int(args.get("top_k", 6)),
                )
            else:
                tool_answer = run_interview_turn.func(
                    user_input=_ensure_str(args.get("user_input", "")),
                    history=args.get("history") or [],
                    topic=args.get("topic"),
                )
            parsed_tool = _parse_tool_payload(_ensure_str(tool_answer))
            return {
                "answer": _ensure_str(parsed_tool.get("answer", tool_answer)) if parsed_tool else _ensure_str(tool_answer),
                "tool_results": [{"name": name, "result": _ensure_str(tool_answer)}],
                "citations": parsed_tool.get("citations", []) if parsed_tool else [],
                "used_context": parsed_tool.get("used_context", []) if parsed_tool else [],
            }
        return {
            "answer": _ensure_str(decision.get("answer") or raw),
            "tool_results": [],
            "citations": [],
            "used_context": [],
        }

    try:
        result = _GRAPH.invoke({"messages": input_messages, "session": session})
        messages = result.get("messages", [])
    except Exception as exc:
        # Safety fallback: keep the chat alive even if graph/tool execution fails.
        latest = _ensure_str(question)
        prior = _history_for_tool(input_messages)
        try:
            if session.get("active_source_type") == "resume" and session.get("active_source_id"):
                tool_answer = run_resume_interview_turn.func(
                    user_input=latest,
                    history=prior,
                    source_id=_ensure_str(session.get("active_source_id")),
                    top_k=6,
                )
                parsed_tool = _parse_tool_payload(_ensure_str(tool_answer))
                return {
                    "answer": _ensure_str(parsed_tool.get("answer", tool_answer)) if parsed_tool else _ensure_str(tool_answer),
                    "tool_results": [
                        {"name": "run_resume_interview_turn", "result": _ensure_str(tool_answer)}
                    ],
                    "citations": parsed_tool.get("citations", []) if parsed_tool else [],
                    "used_context": parsed_tool.get("used_context", []) if parsed_tool else [],
                }
            tool_answer = run_interview_turn.func(
                user_input=latest,
                history=prior,
                topic="technical interview",
            )
            return {
                "answer": _ensure_str(tool_answer),
                "tool_results": [{"name": "run_interview_turn", "result": _ensure_str(tool_answer)}],
                "citations": [],
                "used_context": [],
            }
        except Exception as inner_exc:
            return {
                "answer": f"Agent execution failed: {inner_exc}",
                "tool_results": [{"name": "error", "result": str(exc)}],
                "citations": [],
                "used_context": [],
            }

    answer = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            answer = _ensure_str(msg.content)
            break

    tool_results: list[dict] = []
    citations: list[dict] = []
    used_context: list[dict] = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            parsed = _parse_tool_payload(_ensure_str(msg.content))
            if parsed:
                if not citations and isinstance(parsed.get("citations"), list):
                    citations = parsed.get("citations", [])
                if not used_context and isinstance(parsed.get("used_context"), list):
                    used_context = parsed.get("used_context", [])
            tool_results.append(
                {
                    "name": getattr(msg, "name", "") or "tool",
                    "result": _ensure_str(msg.content),
                }
            )

    return {
        "answer": answer,
        "tool_results": tool_results,
        "citations": citations,
        "used_context": used_context,
    }
