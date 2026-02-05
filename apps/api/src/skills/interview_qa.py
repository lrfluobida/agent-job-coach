import json
import re

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
        "你是面试辅导助手，只能依据【证据块】回答，禁止编造。必须给出引用 chunk id。"
        "输出必须是严格 JSON。"
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
) -> dict:
    if count_collection() == 0:
        return {
            "ok": True,
            "answer": "当前没有可用资料，请先导入简历或岗位信息后再提问。",
            "citations": [],
            "used_context": [],
        }

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
    citations = data.get("citations", [])
    if isinstance(citations, list):
        for item in citations:
            if isinstance(item, dict) and "quote" in item:
                item["quote"] = _ensure_str(item["quote"])

    if not citations and used_context:
        citations = [
            {
                "id": used_context[0].get("id", ""),
                "quote": used_context[0].get("text", "")[:120],
            }
        ]

    return {
        "ok": True,
        "answer": answer,
        "citations": citations,
        "used_context": used_context,
    }
