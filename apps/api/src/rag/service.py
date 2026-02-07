from __future__ import annotations

from src.rag.embeddings import embed_texts
from src.rag.store import count_collection, query_collection


def _ensure_str(value) -> str:
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    return str(value)


def _normalize_where(where: dict | None) -> dict | None:
    if not where:
        return None
    # Chroma expects exactly one top-level operator when composing multiple clauses.
    # Convert plain multi-field equality filters into {"$and": [{"k": {"$eq": v}}, ...]}.
    if any(str(k).startswith("$") for k in where.keys()):
        return where
    items = [(k, v) for k, v in where.items() if v is not None]
    if not items:
        return None
    if len(items) == 1:
        k, v = items[0]
        return {k: v}
    return {"$and": [{k: {"$eq": v}} for k, v in items]}


def retrieve(query: str, top_k: int, where: dict | None) -> list[dict]:
    if count_collection() == 0:
        return []

    embedding = embed_texts([query])[0]
    raw = query_collection(embedding=embedding, top_k=top_k, where=_normalize_where(where))

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
