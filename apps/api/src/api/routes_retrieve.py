from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.rag.service import retrieve as rag_retrieve


router = APIRouter()


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    filter: dict | None = None


@router.post("/retrieve")
def retrieve_route(payload: RetrieveRequest):
    where: dict | None = None
    if payload.filter:
        where = {}
        source_type = payload.filter.get("source_type")
        source_id = payload.filter.get("source_id")
        if source_type:
            where["source_type"] = source_type
        if source_id:
            where["source_id"] = source_id

    matches = rag_retrieve(payload.query, top_k=payload.top_k, where=where)

    results = []
    for match in matches:
        results.append(
            {
                "id": match.get("id"),
                "text": match.get("text", ""),
                "metadata": match.get("metadata", {}),
                "score": match.get("score", 0.0),
            }
        )

    return {"ok": True, "results": results}
