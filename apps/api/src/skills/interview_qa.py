import json
import re

from src.core.output_coercion import shorten_quote
from src.core.settings import get_settings
from src.llm.zhipu import chat
from src.rag.service import retrieve
from src.rag.store import count_collection


def _ensure_str(value) -> str:
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    return str(value)


def _normalize_results(matches: list[dict]) -> list[dict]:
    results: list[dict] = []
    for match in matches:
        results.append(
            {
                "id": match.get("id"),
                "text": _ensure_str(match.get("text", "")),
                "metadata": match.get("metadata", {}),
                "score": match.get("score", 0.0),
            }
        )
    return results


def _build_prompt(question: str, contexts: list[dict]) -> list[dict]:
    system = (
        "你是面试辅导助手，只能依据【证据块】回答，禁止编造。"
        "请输出 Markdown 形式的自然语言回答。"
        "如需引用证据，请在 citations 中返回，引用 chunk id。"
        "输出严格 JSON，格式：{\"answer\":\"...\",\"citations\":[{\"id\":\"...\",\"quote\":\"...\"}]}。"
    )

    evidence_lines = []
    for item in contexts:
        evidence_lines.append(f"[[{item['id']}]] {item['text']}")

    user = "\n".join(
        [
            f"问题：{question}",
            "\n【证据块】",
            "\n".join(evidence_lines),
            "\n请输出 JSON，格式：",
            '{"answer": "...", "citations": [{"id": "...", "quote": "..."}] }',
        ]
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None


def _shorten(text: str, limit: int = 600) -> str:
    return text if len(text) <= limit else text[:limit] + "..."


def retrieve_context(question: str, *, top_k: int = 5, where: dict | None = None) -> list[dict]:
    matches = retrieve(question, top_k=top_k, where=where)
    return _normalize_results(matches)


def run_interview_qa(
    question: str,
    top_k: int = 5,
    where: dict | None = None,
    used_context: list[dict] | None = None,
) -> dict:
    if count_collection() == 0:
        return {
            "ok": True,
            "answer": "当前没有可用资料，请先导入简历或岗位信息后再提问。",
            "citations": [],
            "used_context": [],
        }

    if used_context is None:
        used_context = retrieve_context(question, top_k=top_k, where=where)

    if not used_context:
        return {
            "ok": True,
            "answer": "未检索到相关资料，请补充导入更多内容后再提问。",
            "citations": [],
            "used_context": [],
        }

    messages = _build_prompt(question, used_context)

    try:
        content = chat(messages)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    data = _extract_json(content)
    if not data:
        return {
            "ok": False,
            "error": "模型输出非 JSON，无法解析。",
            "raw": _shorten(content),
            "used_context": used_context,
        }

    answer = _ensure_str(data.get("answer", ""))
    settings = get_settings()
    citations = data.get("citations", [])
    candidate_map = {c.get("id"): c for c in used_context if isinstance(c, dict)}
    normalized: list[dict] = []
    if isinstance(citations, list):
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
                normalized.append({"id": cid, "quote": shorten_quote(_ensure_str(quote or ""))})
            if len(normalized) >= settings.max_citations:
                break
    citations = normalized
    if not citations and used_context:
        top_ctx = used_context[0]
        if isinstance(top_ctx, dict) and top_ctx.get("id"):
            citations = [
                {
                    "id": top_ctx.get("id"),
                    "quote": shorten_quote(_ensure_str(top_ctx.get("text", ""))),
                }
            ]

    return {
        "ok": True,
        "answer": answer,
        "citations": citations,
        "used_context": used_context,
    }
