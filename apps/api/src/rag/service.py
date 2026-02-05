from __future__ import annotations

from src.rag.embeddings import embed_texts
from src.rag.store import count_collection, query_collection


def _ensure_str(value) -> str:
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    return str(value)


def retrieve(query: str, top_k: int, where: dict | None) -> list[dict]:
    if count_collection() == 0:
        return []

    embedding = embed_texts([query])[0]
    raw = query_collection(embedding=embedding, top_k=top_k, where=where)

    ids = (raw.get("ids") or [[]])[0]
    documents = (raw.get("documents") or [[]])[0]
    metadatas = (raw.get("metadatas") or [[]])[0]
    distances = (raw.get("distances") or [[]])[0]

    results: list[dict] = []
    for idx, doc_id in enumerate(ids):
        score = distances[idx] if idx < len(distances) else None
        score = float(score) if score is not None else 0.0
        results.append(
            {
                "id": doc_id,
                "text": _ensure_str(documents[idx]) if idx < len(documents) else "",
                "metadata": metadatas[idx] if idx < len(metadatas) else {},
                "score": score,
            }
        )
    return results
