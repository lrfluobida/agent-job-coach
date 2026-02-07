from __future__ import annotations

from typing import Iterable

from src.core.deps import get_chroma_client


COLLECTION_NAME = "job_coach"


def get_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(name=COLLECTION_NAME)


def delete_by_source(source_id: str) -> None:
    collection = get_collection()
    collection.delete(where={"source_id": source_id})


def upsert_chunks(
    *,
    ids: list[str],
    chunks: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict],
) -> None:
    collection = get_collection()
    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def count_collection() -> int:
    collection = get_collection()
    return collection.count()


def query_collection(
    *,
    embedding: list[float],
    top_k: int,
    where: dict | None,
) -> dict:
    collection = get_collection()
    return collection.query(
        query_embeddings=[embedding],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )


def find_source_id_by_content_hash(*, source_type: str, content_sha256: str) -> str | None:
    collection = get_collection()
    raw = collection.get(
        where={"content_sha256": content_sha256},
        include=["metadatas"],
    )
    metadatas = raw.get("metadatas") or []
    for meta in metadatas:
        if not isinstance(meta, dict):
            continue
        if meta.get("source_type") != source_type:
            continue
        source_id = meta.get("source_id")
        if isinstance(source_id, str) and source_id:
            return source_id
    return None
