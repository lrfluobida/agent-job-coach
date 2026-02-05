from __future__ import annotations

import json
import urllib.request

from src.core.settings import get_settings

DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_MODEL = "glm-4-flash"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_TIMEOUT_S = 30


def chat(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float | None = None,
) -> str:
    settings = get_settings()
    api_key = settings.zhipu_api_key
    if not api_key:
        raise RuntimeError("ZHIPUAI_API_KEY is not set")

    base_url = (settings.zhipu_base_url or DEFAULT_BASE_URL).rstrip("/")
    model = model or (settings.zhipu_chat_model or DEFAULT_MODEL)
    if temperature is None:
        temperature = float(settings.zhipu_temperature)
    timeout = float(settings.zhipu_timeout_s)

    url = f"{base_url}/chat/completions"
    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
        data = json.loads(body)

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("ZhipuAI response missing choices")

    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        raise RuntimeError("ZhipuAI response missing message content")

    return content


def chat_completion(*, messages: list[dict]) -> str:
    return chat(messages)
