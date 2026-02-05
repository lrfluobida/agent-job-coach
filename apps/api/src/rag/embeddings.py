from __future__ import annotations

import hashlib
import json
import os
import random
import urllib.request
from typing import Iterable


DEFAULT_MODEL = "embedding-3"
DEFAULT_DIM = 1536
DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"


def _dummy_embedding(text: str, dim: int = DEFAULT_DIM) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    seed = int(digest[:16], 16)
    rng = random.Random(seed)
    return [rng.uniform(-1.0, 1.0) for _ in range(dim)]


def _dummy_embeddings(texts: Iterable[str]) -> list[list[float]]:
    return [_dummy_embedding(t) for t in texts]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    api_key = os.getenv("ZHIPUAI_API_KEY")
    if not api_key:
        return _dummy_embeddings(texts)

    model = os.getenv("ZHIPUAI_EMBED_MODEL", DEFAULT_MODEL)
    base_url = os.getenv("ZHIPUAI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")

    url = f"{base_url}/embeddings"
    payload = json.dumps({"model": model, "input": texts}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
        data = json.loads(body)

    embeddings = data.get("data", [])
    return [item.get("embedding", []) for item in embeddings]
