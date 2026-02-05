import json
import re
from typing import Any, Tuple


def strip_code_fence(text: str) -> str:
    if not text:
        return ""
    trimmed = text.strip()
    match = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", trimmed, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return trimmed


def _strip_leading_json_token(text: str) -> str:
    trimmed = text.lstrip()
    lower = trimmed.lower()
    if lower.startswith('"json'):
        trimmed = trimmed[5:]
    elif lower.startswith("json"):
        trimmed = trimmed[4:]
    return trimmed.lstrip(" \t\r\n:\"")


def coerce_model_output(text: str | None) -> Tuple[str, list[dict]]:
    if not text:
        return "", []

    cleaned = strip_code_fence(text)
    cleaned = _strip_leading_json_token(cleaned)

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and isinstance(data.get("answer"), str):
            citations = data.get("citations") if isinstance(data.get("citations"), list) else []
            return data.get("answer", ""), citations
    except Exception:
        pass

    return cleaned.strip(), []


def shorten_quote(text: str, n: int = 120) -> str:
    if not text:
        return ""
    if len(text) <= n:
        return text
    return text[:n] + "..."
