from __future__ import annotations

import json
import re

from langchain_core.tools import tool

from src.llm.zhipu import chat
from src.rag.service import retrieve


def _ensure_str(value) -> str:
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    return str(value)


def _history_to_messages(history: list) -> list[dict]:
    messages: list[dict] = []
    for item in history or []:
        if isinstance(item, dict):
            role = item.get("role")
            content = item.get("content")
            if role in {"system", "user", "assistant"} and content is not None:
                messages.append({"role": role, "content": _ensure_str(content)})
        else:
            messages.append({"role": "user", "content": _ensure_str(item)})
    return messages


def _build_interviewer_prompt(user_input: str, history: list, topic: str | None = None) -> list[dict]:
    system = (
        "你是一名严格但有帮助的技术面试官。\n"
        "每轮按顺序完成：\n"
        "1) 先判断候选人回答属于：正确 / 模糊 / 错误；\n"
        "2) 给出1-2句简短反馈，指出关键点和缺失点；\n"
        "3) 提出一个更深入的下一步问题。\n"
        "必须使用以下中文结构输出：\n"
        "分类：<正确|模糊|错误>\n"
        "反馈：<简短反馈>\n"
        "下一步问题：<一个追问>\n"
        "只输出 Markdown 自然语言，不要 JSON，不要输出推理过程。"
    )
    messages: list[dict] = [{"role": "system", "content": system}]
    if topic:
        messages.append({"role": "system", "content": f"Interview topic: {_ensure_str(topic)}"})
    messages.extend(_history_to_messages(history))
    messages.append({"role": "user", "content": _ensure_str(user_input)})
    return messages


@tool
def run_interview_turn(user_input: str, history: list, topic: str | None = None) -> str:
    """Use for mock technical interview turns: evaluate answer briefly and ask one deeper follow-up."""
    messages = _build_interviewer_prompt(user_input=user_input, history=history, topic=topic)
    return _ensure_str(chat(messages))


def _build_resume_interviewer_prompt(user_input: str, history: list, contexts: list[dict]) -> list[dict]:
    evidence = "\n".join(
        f"[[{item.get('id', '')}]] {_ensure_str(item.get('text', ''))}" for item in contexts
    )
    system = (
        "你是一名严格但有帮助的技术面试官。\n"
        "你必须基于简历证据进行反馈和追问，不得臆造。\n"
        "每轮按顺序完成：\n"
        "1) 分类候选人回答：正确 / 模糊 / 错误；\n"
        "2) 给出简短反馈；\n"
        "3) 提出一个更深入的下一步问题。\n"
        "必须使用以下中文结构输出：\n"
        "分类：<正确|模糊|错误>\n"
        "反馈：<简短反馈>\n"
        "下一步问题：<一个追问>\n"
        "只输出 Markdown 自然语言，不要 JSON，不要输出推理过程。"
    )
    user = (
        f"候选人最新回答：{_ensure_str(user_input)}\n\n"
        "以下是相关简历证据片段，请优先据此追问：\n"
        f"{evidence or '（未检索到简历证据）'}"
    )
    return [
        {"role": "system", "content": system},
        *_history_to_messages(history),
        {"role": "user", "content": user},
    ]


def _has_assistant_turn(history: list) -> bool:
    for item in history or []:
        if isinstance(item, dict) and item.get("role") == "assistant" and _ensure_str(item.get("content", "")).strip():
            return True
    return False


def _has_interview_started(history: list) -> bool:
    for item in history or []:
        if not isinstance(item, dict) or item.get("role") != "assistant":
            continue
        content = _ensure_str(item.get("content", "")).lower()
        # Any of these markers indicates interview flow has already started.
        if (
            "下一步问题" in content
            or "follow-up question" in content
            or content.strip().startswith("问题：")
            or content.strip().startswith("question:")
            or "分类：" in content
            or "answer classification" in content
        ):
            return True
    return False


def _is_interview_kickoff(user_input: str, history: list) -> bool:
    text = _ensure_str(user_input).strip().lower()
    if not text:
        return False
    kickoff_patterns = [
        r"针对.*简历.*提问",
        r"根据.*简历.*提问",
        r"简历.*面试",
        r"mock\s*interview",
        r"interview\s*me",
        r"ask\s*me\s*questions",
    ]
    explicit_kickoff = any(re.search(p, text, flags=re.IGNORECASE) for p in kickoff_patterns)
    # Cover broader Chinese phrasing like "提几个问题/问我几个问题".
    contains_resume = "简历" in text
    asks_questions = any(k in text for k in ["提问", "问题", "问我", "问几个", "问一", "问一下", "面试"])
    explicit_kickoff = explicit_kickoff or (contains_resume and asks_questions)
    if not explicit_kickoff:
        return False
    # If interview has not started yet (even in the middle of a casual chat), treat as kickoff.
    # This prevents "first interview question" from being misinterpreted as an answer turn.
    return not _has_interview_started(history)


def _build_resume_kickoff_prompt(history: list, contexts: list[dict]) -> list[dict]:
    evidence = "\n".join(
        f"[[{item.get('id', '')}]] {_ensure_str(item.get('text', ''))}" for item in contexts
    )
    system = (
        "你是一名严格但有帮助的技术面试官。\n"
        "现在是简历面试的首轮启动。\n"
        "只做一件事：基于简历证据提出一个聚焦技术问题。\n"
        "不要做分类，不要给反馈。\n"
        "输出格式：问题：<你的问题>"
    )
    user = (
        "请基于以下简历证据发起首轮提问：\n"
        f"{evidence or '(no resume evidence found)'}"
    )
    return [
        {"role": "system", "content": system},
        *_history_to_messages(history),
        {"role": "user", "content": user},
    ]


def _shorten(text: str, limit: int = 180) -> str:
    raw = _ensure_str(text)
    return raw if len(raw) <= limit else f"{raw[:limit]}..."


def _build_evidence_payload(answer: str, contexts: list[dict]) -> str:
    citations: list[dict] = []
    normalized_ctx: list[dict] = []
    for item in contexts:
        if not isinstance(item, dict):
            continue
        cid = _ensure_str(item.get("id", "")).strip()
        if not cid:
            continue
        text = _ensure_str(item.get("text", ""))
        normalized_ctx.append(
            {
                "id": cid,
                "text": text,
                "metadata": item.get("metadata", {}),
                "score": item.get("score", 0.0),
            }
        )
        citations.append({"id": cid, "quote": _shorten(text)})
        if len(citations) >= 3:
            break

    payload = {
        "answer": _ensure_str(answer),
        "citations": citations,
        "used_context": normalized_ctx,
    }
    return json.dumps(payload, ensure_ascii=False)


def _enforce_kickoff_output(answer: str) -> str:
    text = _ensure_str(answer).strip()
    # If model still returns multi-section template, keep only the first question line/paragraph.
    markers = ["answer classification", "feedback", "follow-up question", "分类", "反馈", "下一步问题"]
    lower = text.lower()
    cut_index = -1
    for marker in markers:
        idx = lower.find(marker)
        if idx > 0 and (cut_index == -1 or idx < cut_index):
            cut_index = idx
    if cut_index > 0:
        text = text[:cut_index].strip()
    if not text.startswith("问题："):
        text = f"问题：{text}"
    return text


def _normalize_structured_output(answer: str) -> str:
    text = _ensure_str(answer).strip()
    # Normalize common English labels to Chinese labels.
    text = re.sub(r"(?i)answer\s*classification\s*[:：]", "分类：", text)
    text = re.sub(r"(?i)feedback\s*[:：]", "反馈：", text)
    text = re.sub(r"(?i)follow-?\s*up\s*question\s*[:：]", "下一步问题：", text)

    # Split into three explicit sections and enforce markdown paragraph breaks.
    cls = ""
    fb = ""
    nxt = ""
    m1 = re.search(r"分类[:：]\s*(.*?)(?=\n?\s*反馈[:：]|\n?\s*下一步问题[:：]|$)", text, flags=re.S)
    if m1:
        cls = m1.group(1).strip()
    m2 = re.search(r"反馈[:：]\s*(.*?)(?=\n?\s*下一步问题[:：]|$)", text, flags=re.S)
    if m2:
        fb = m2.group(1).strip()
    m3 = re.search(r"下一步问题[:：]\s*(.*)$", text, flags=re.S)
    if m3:
        nxt = m3.group(1).strip()

    if cls or fb or nxt:
        parts = []
        if cls:
            parts.append(f"分类：{cls}")
        if fb:
            parts.append(f"反馈：{fb}")
        if nxt:
            parts.append(f"下一步问题：{nxt}")
        return "\n\n".join(parts)

    return text


@tool
def run_resume_interview_turn(user_input: str, history: list, source_id: str, top_k: int = 6) -> str:
    """Use for resume-focused mock interview. Always retrieves resume chunks before generating feedback and follow-up."""
    if not _ensure_str(source_id).strip():
        return run_interview_turn.func(user_input=user_input, history=history, topic="resume interview")
    where = {"source_type": "resume", "source_id": _ensure_str(source_id)}
    contexts = retrieve(_ensure_str(user_input), top_k=max(1, int(top_k)), where=where)
    # Reliable kickoff rule:
    # First resume-interview turn should only ask one question, regardless of wording.
    kickoff = not _has_interview_started(history)
    if kickoff:
        messages = _build_resume_kickoff_prompt(history=history, contexts=contexts)
    else:
        messages = _build_resume_interviewer_prompt(
            user_input=_ensure_str(user_input),
            history=history,
            contexts=contexts,
        )
    answer = _ensure_str(chat(messages))
    if kickoff:
        answer = _enforce_kickoff_output(answer)
    else:
        answer = _normalize_structured_output(answer)
    return _build_evidence_payload(answer, contexts)


def run_interview_qa(
    question: str,
    top_k: int = 5,
    where: dict | None = None,
    used_context: list[dict] | None = None,
) -> dict:
    _ = top_k
    topic = None
    if isinstance(where, dict):
        topic = _ensure_str(where.get("topic") or "") or None

    try:
        answer = run_interview_turn.func(
            user_input=question,
            history=used_context or [],
            topic=topic,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    return {
        "ok": True,
        "answer": answer,
        "citations": [],
        "used_context": used_context or [],
    }
