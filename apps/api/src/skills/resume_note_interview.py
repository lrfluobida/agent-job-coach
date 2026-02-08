from __future__ import annotations

import json
import random
import re
from typing import TypedDict

from langchain_core.tools import tool

from src.rag.service import retrieve


class InterviewState(TypedDict):
    source_id: str
    topic: str | None
    asked_question_ids: list[str]
    current_question_id: str | None
    current_question: str | None
    current_standard_answer: str | None
    current_key_points: list[str]
    current_context_id: str | None


_TOKEN_RE = re.compile(r"[a-z0-9_+#.]+|[\u4e00-\u9fff]{2,}", flags=re.IGNORECASE)


def _ensure_str(value) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def _normalize_text(text: str) -> str:
    value = _ensure_str(text).strip().lower()
    value = re.sub(r"\s+", "", value)
    return value


def _tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(_ensure_str(text))]


def _extract_topic_command(user_input: str) -> str | None:
    text = _ensure_str(user_input).strip()
    if not text:
        return None

    en = re.search(r"(?:ask me|question me)\s+about\s+([a-zA-Z0-9_+#\-/ ]{1,30})", text, flags=re.IGNORECASE)
    if en:
        topic = re.sub(r"\s+", " ", en.group(1)).strip()
        return topic or None

    cn_patterns = [
        r"(?:\u63d0\u95ee\u6211|\u95ee\u6211|\u8003\u6211)\u5173\u4e8e([a-zA-Z0-9\u4e00-\u9fff+#\-/ ]{1,30})(?:\u7684?\u95ee\u9898)?",
        r"(?:\u5173\u4e8e)([a-zA-Z0-9\u4e00-\u9fff+#\-/ ]{1,30})(?:\u63d0\u95ee|\u9762\u8bd5\u6211|\u95ee\u9898)",
    ]
    for pattern in cn_patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if not m:
            continue
        topic = re.sub(r"\s+", " ", m.group(1)).strip()
        if topic:
            return topic
    return None


def _is_question_request(user_input: str) -> bool:
    text = _ensure_str(user_input).strip().lower()
    if not text:
        return False
    keywords = [
        "\u63d0\u95ee\u6211",
        "\u95ee\u6211",
        "\u5f00\u59cb\u9762\u8bd5",
        "\u6765\u4e00\u9898",
        "\u51fa\u4e00\u9053",
        "\u4e0b\u4e00\u9898",
        "\u6362\u4e00\u9898",
        "\u7ee7\u7eed\u63d0\u95ee",
        "mock interview",
        "interview me",
        "ask me",
        "question me",
    ]
    return any(k in text for k in keywords)


def _is_skip_request(user_input: str) -> bool:
    text = _ensure_str(user_input).strip().lower()
    keywords = ["\u4e0b\u4e00\u9898", "\u6362\u4e00\u9898", "\u8df3\u8fc7", "skip", "pass"]
    return any(k in text for k in keywords)


def _parse_key_points_json(raw: str) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out: list[str] = []
    for item in data:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def _extract_key_points_from_answer(answer: str, limit: int = 6) -> list[str]:
    points: list[str] = []
    for line in _ensure_str(answer).splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        item = stripped.lstrip("-").strip()
        item = item.replace("**", "").replace("*", "").strip()
        if item:
            points.append(item)
        if len(points) >= limit:
            break
    return points


def _parse_card_from_document(doc: str) -> tuple[str, str]:
    text = _ensure_str(doc)
    q = ""
    a = ""
    m_q = re.search(r"(?im)^question:\s*(.+?)\s*$", text)
    if m_q:
        q = m_q.group(1).strip()
    m_a = re.search(r"(?is)standardanswer:\s*(.+?)(?:\n\s*topic:|\Z)", text)
    if m_a:
        a = m_a.group(1).strip()
    return q, a


def _default_state(source_id: str) -> InterviewState:
    return InterviewState(
        source_id=source_id,
        topic=None,
        asked_question_ids=[],
        current_question_id=None,
        current_question=None,
        current_standard_answer=None,
        current_key_points=[],
        current_context_id=None,
    )


def _coerce_state(session: dict | None, source_id: str) -> InterviewState:
    state = _default_state(source_id)
    if not isinstance(session, dict):
        return state
    if _ensure_str(session.get("source_id")) and _ensure_str(session.get("source_id")) != source_id:
        return state

    asked_raw = session.get("asked_question_ids")
    asked = asked_raw if isinstance(asked_raw, list) else []
    state["asked_question_ids"] = [_ensure_str(item).strip() for item in asked if _ensure_str(item).strip()]
    state["topic"] = _ensure_str(session.get("topic")).strip() or None
    state["current_question_id"] = _ensure_str(session.get("current_question_id")).strip() or None
    state["current_question"] = _ensure_str(session.get("current_question")).strip() or None
    state["current_standard_answer"] = _ensure_str(session.get("current_standard_answer")).strip() or None
    key_points_raw = session.get("current_key_points")
    key_points = key_points_raw if isinstance(key_points_raw, list) else []
    state["current_key_points"] = [_ensure_str(item).strip() for item in key_points if _ensure_str(item).strip()]
    state["current_context_id"] = _ensure_str(session.get("current_context_id")).strip() or None
    return state


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a.intersection(b))
    union = len(a.union(b))
    return 0.0 if union == 0 else inter / union


def _point_hit(answer_norm: str, point: str) -> bool:
    p = _normalize_text(point)
    if not p:
        return False
    if len(p) >= 6 and p[:6] in answer_norm:
        return True
    tokens = [t for t in _tokenize(point) if len(t) >= 2]
    return any(token in answer_norm for token in tokens)


def _evaluate_answer(user_answer: str, standard_answer: str, key_points: list[str]) -> dict:
    answer_norm = _normalize_text(user_answer)
    hits: list[str] = []
    missing: list[str] = []
    for point in key_points:
        if _point_hit(answer_norm, point):
            hits.append(point)
        else:
            missing.append(point)

    coverage = (len(hits) / len(key_points)) if key_points else 0.0
    semantic = _jaccard_similarity(set(_tokenize(user_answer)), set(_tokenize(standard_answer)))
    score = (0.7 * coverage + 0.3 * semantic) if key_points else semantic
    score = max(0.0, min(1.0, score))

    if score >= 0.75:
        label = "\u6b63\u786e"
        feedback = "\u56de\u7b54\u8986\u76d6\u4e86\u4e3b\u8981\u8981\u70b9\uff0c\u548c\u6807\u51c6\u7b54\u6848\u57fa\u672c\u4e00\u81f4\u3002"
    elif score >= 0.40:
        label = "\u90e8\u5206\u6b63\u786e"
        feedback = "\u56de\u7b54\u6293\u4f4f\u4e86\u90e8\u5206\u5173\u952e\u70b9\uff0c\u4f46\u8fd8\u4e0d\u591f\u5b8c\u6574\u3002"
    else:
        label = "\u4e0d\u6b63\u786e"
        feedback = "\u56de\u7b54\u4e0e\u6807\u51c6\u7b54\u6848\u504f\u5dee\u8f83\u5927\uff0c\u5efa\u8bae\u6309\u53c2\u8003\u7b54\u6848\u91cd\u6784\u56de\u7b54\u6846\u67b6\u3002"

    return {
        "score": round(score, 3),
        "label": label,
        "feedback": feedback,
        "missing": missing[:4],
    }


def _overlap_ratio(a_tokens: set[str], b_tokens: set[str]) -> float:
    if not a_tokens or not b_tokens:
        return 0.0
    inter = len(a_tokens.intersection(b_tokens))
    return inter / max(1, len(a_tokens))


def _distance_to_similarity(distance: float | int | None) -> float:
    if distance is None:
        return 0.0
    d = float(distance)
    if d < 0:
        d = 0.0
    return 1.0 / (1.0 + d)


def _resume_profile(source_id: str, top_k: int) -> tuple[list[dict], list[str]]:
    where = {"source_type": "resume", "source_id": source_id}
    resume_ctx = retrieve(
        "\u5019\u9009\u4eba\u7b80\u5386 \u6280\u672f\u6808 \u9879\u76ee \u7ecf\u9a8c \u4ea7\u51fa",
        top_k=max(4, top_k),
        where=where,
    )
    merged = "\n".join(_ensure_str(item.get("text", "")) for item in resume_ctx if isinstance(item, dict))
    keywords: list[str] = []
    seen: set[str] = set()
    for token in _tokenize(merged):
        if len(token) < 2:
            continue
        if token in seen:
            continue
        seen.add(token)
        keywords.append(token)
        if len(keywords) >= 12:
            break
    return resume_ctx, keywords


def _collect_candidates(topic: str | None, resume_keywords: list[str], top_k: int) -> list[dict]:
    where = {"source_type": "note", "doc_kind": "qa_card"}
    queries: list[str] = []
    if topic:
        queries.append(f"{topic} interview questions")
        queries.append(f"{topic} \u9762\u8bd5\u9898")
    if resume_keywords:
        queries.append(f"{' '.join(resume_keywords[:6])} interview")
    queries.append("technical interview questions")

    merged: dict[str, dict] = {}
    for query in queries:
        for item in retrieve(query, top_k=max(top_k, 15), where=where):
            if not isinstance(item, dict):
                continue
            cid = _ensure_str(item.get("id")).strip()
            if not cid:
                continue
            existing = merged.get(cid)
            if existing is None or float(item.get("score", 0.0)) < float(existing.get("score", 0.0)):
                merged[cid] = item
    return list(merged.values())


def _normalize_candidate(item: dict) -> dict | None:
    meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    question_id = _ensure_str(meta.get("question_id") or item.get("id")).strip()
    question = _ensure_str(meta.get("question")).strip()
    answer = _ensure_str(meta.get("standard_answer")).strip()
    if not question or not answer:
        q2, a2 = _parse_card_from_document(_ensure_str(item.get("text", "")))
        question = question or q2
        answer = answer or a2
    if not question or not answer:
        return None

    key_points = _parse_key_points_json(_ensure_str(meta.get("key_points_json")))
    if not key_points:
        key_points = _extract_key_points_from_answer(answer)

    return {
        "id": _ensure_str(item.get("id")).strip(),
        "question_id": question_id,
        "question": question,
        "standard_answer": answer,
        "key_points": key_points,
        "topic": _ensure_str(meta.get("topic")).strip(),
        "topic_group": _ensure_str(meta.get("topic_group")).strip(),
        "tags": _ensure_str(meta.get("tags")).strip().lower(),
        "score": float(item.get("score", 0.0)),
        "raw": item,
    }


def _pick_question(
    *,
    asked_question_ids: set[str],
    topic: str | None,
    resume_keywords: list[str],
    top_k: int,
) -> dict | None:
    candidates = _collect_candidates(topic=topic, resume_keywords=resume_keywords, top_k=top_k)
    resume_token_set = set(t.lower() for t in resume_keywords)
    topic_norm = _ensure_str(topic).strip().lower()
    ranked: list[tuple[float, dict]] = []

    for item in candidates:
        card = _normalize_candidate(item)
        if not card:
            continue
        if card["question_id"] in asked_question_ids:
            continue

        question_tokens = set(_tokenize(card["question"]))
        resume_overlap = _overlap_ratio(question_tokens, resume_token_set)
        similarity = _distance_to_similarity(card["score"])
        haystack = " ".join(
            [
                _ensure_str(card.get("topic", "")),
                _ensure_str(card.get("topic_group", "")),
                _ensure_str(card.get("tags", "")),
                _ensure_str(card.get("question", "")),
            ]
        ).lower()
        topic_bonus = 1.0 if (topic_norm and topic_norm in haystack) else 0.0
        rank_score = 0.50 * similarity + 0.35 * resume_overlap + 0.15 * topic_bonus
        ranked.append((rank_score, card))

    if not ranked:
        return None
    ranked.sort(key=lambda x: x[0], reverse=True)
    top_n = min(5, len(ranked))
    candidates = ranked[:top_n]
    # Keep the best score dominant but allow diversity across new conversations.
    weights = [max(0.001, score) * (0.90**idx) for idx, (score, _card) in enumerate(candidates)]
    selected = random.choices(candidates, weights=weights, k=1)[0]
    return selected[1]


def _build_question_only_answer(question: str, topic: str | None) -> str:
    topic_line = f"\uff08\u4e3b\u9898\uff1a{topic}\uff09" if topic else ""
    return (
        f"\u9898\u76ee{topic_line}\uff1a{question}\n\n"
        "\u8bf7\u7ed3\u5408\u4f60\u7684\u7b80\u5386\u7ecf\u5386\u4f5c\u7b54\uff0c"
        "\u5c3d\u91cf\u8bf4\u6e05\u695a\uff1a\u573a\u666f\u3001\u65b9\u6848\u3001\u5173\u952e\u53d6\u820d\u548c\u7ed3\u679c\u3002"
    )


def _build_eval_answer(*, result: dict, reference_answer: str, next_question: str | None) -> str:
    lines: list[str] = [
        f"**\u8bc4\u5206**\uff1a{result['score']:.2f}\uff08{result['label']}\uff09",
        "",
        f"**\u53cd\u9988**\uff1a{result['feedback']}",
    ]
    missing = result.get("missing") if isinstance(result.get("missing"), list) else []
    if missing:
        lines.append("")
        lines.append("**\u7f3a\u5931\u8981\u70b9**\uff1a")
        for point in missing:
            lines.append(f"- {point}")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**\u53c2\u8003\u7b54\u6848**\uff1a")
    lines.append(reference_answer)
    lines.append("")
    if next_question:
        lines.append(f"**\u4e0b\u4e00\u9898**\uff1a{next_question}")
    else:
        lines.append(
            "**\u4e0b\u4e00\u9898**\uff1a\u9898\u5e93\u5df2\u62bd\u5b8c\uff0c"
            "\u53ef\u4e0a\u4f20\u66f4\u591a note \u6216\u8c03\u6574\u63d0\u95ee\u4e3b\u9898\u3002"
        )
    return "\n".join(lines)


def _build_payload(answer: str, used_context: list[dict], citations: list[dict], state: InterviewState) -> str:
    payload = {
        "answer": answer,
        "citations": citations,
        "used_context": used_context,
        "session": {"resume_interview_state": state},
    }
    return json.dumps(payload, ensure_ascii=False)


@tool
def run_resume_note_interview_turn(
    user_input: str,
    history: list,
    source_id: str,
    top_k: int = 12,
    session: dict | None = None,
) -> str:
    """Use note QA cards to run resume interview: ask non-repeating question, evaluate answer, and provide reference answer."""
    _ = history
    source_id = _ensure_str(source_id).strip()
    if not source_id:
        return json.dumps(
            {
                "answer": "\u672a\u7ed1\u5b9a\u7b80\u5386 source_id\uff0c\u65e0\u6cd5\u8fdb\u884c\u7b80\u5386\u5b9a\u5411\u63d0\u95ee\u3002",
                "citations": [],
                "used_context": [],
                "session": {"resume_interview_state": {}},
            },
            ensure_ascii=False,
        )

    state = _coerce_state(session, source_id=source_id)
    user_text = _ensure_str(user_input).strip()
    topic_cmd = _extract_topic_command(user_text)
    if topic_cmd:
        state["topic"] = topic_cmd
        state["current_question_id"] = None
        state["current_question"] = None
        state["current_standard_answer"] = None
        state["current_key_points"] = []
        state["current_context_id"] = None

    asked_set = set(state["asked_question_ids"])
    resume_ctx, resume_keywords = _resume_profile(source_id=source_id, top_k=top_k)
    command_mode = (state["current_question_id"] is None) or _is_question_request(user_text) or _is_skip_request(user_text)

    if command_mode:
        card = _pick_question(
            asked_question_ids=asked_set,
            topic=state.get("topic"),
            resume_keywords=resume_keywords,
            top_k=top_k,
        )
        if not card:
            msg = (
                "\u6ca1\u6709\u5339\u914d\u5230\u53ef\u7528\u9898\u76ee\u3002"
                "\u8bf7\u8865\u5145 note \u9898\u5e93\uff0c\u6216\u6362\u4e00\u4e2a\u66f4\u5177\u4f53\u7684\u4e3b\u9898\u3002"
            )
            return _build_payload(msg, resume_ctx[:2], [], state)

        asked_set.add(card["question_id"])
        state["asked_question_ids"] = list(asked_set)
        state["current_question_id"] = card["question_id"]
        state["current_question"] = card["question"]
        state["current_standard_answer"] = card["standard_answer"]
        state["current_key_points"] = card["key_points"]
        state["current_context_id"] = card["id"]

        answer = _build_question_only_answer(card["question"], state.get("topic"))
        used_context = [card["raw"], *resume_ctx[:2]]
        citations = [{"id": card["id"], "quote": card["question"]}]
        return _build_payload(answer, used_context, citations, state)

    evaluated_reference = _ensure_str(state.get("current_standard_answer"))
    eval_result = _evaluate_answer(
        user_answer=user_text,
        standard_answer=evaluated_reference,
        key_points=state.get("current_key_points") or [],
    )

    next_card = _pick_question(
        asked_question_ids=asked_set,
        topic=state.get("topic"),
        resume_keywords=resume_keywords,
        top_k=top_k,
    )

    citations: list[dict] = []
    if state.get("current_context_id"):
        citations.append(
            {
                "id": _ensure_str(state.get("current_context_id")),
                "quote": _ensure_str(state.get("current_question")),
            }
        )

    if next_card:
        asked_set.add(next_card["question_id"])
        state["asked_question_ids"] = list(asked_set)
        state["current_question_id"] = next_card["question_id"]
        state["current_question"] = next_card["question"]
        state["current_standard_answer"] = next_card["standard_answer"]
        state["current_key_points"] = next_card["key_points"]
        state["current_context_id"] = next_card["id"]
        citations.append({"id": next_card["id"], "quote": next_card["question"]})
        used_context = [next_card["raw"], *resume_ctx[:2]]
        answer = _build_eval_answer(
            result=eval_result,
            reference_answer=evaluated_reference,
            next_question=next_card["question"],
        )
        return _build_payload(answer, used_context, citations, state)

    state["current_question_id"] = None
    state["current_question"] = None
    state["current_standard_answer"] = None
    state["current_key_points"] = []
    state["current_context_id"] = None
    answer = _build_eval_answer(result=eval_result, reference_answer=evaluated_reference, next_question=None)
    return _build_payload(answer, resume_ctx[:2], citations, state)
