from fastapi import APIRouter

from src.ingest.filesystem_sync import list_filesystem_source_ids, sync_filesystem_sources


router = APIRouter()


@router.get("/sources/filesystem")
def list_filesystem_sources():
    return {
        "ok": True,
        "items": list_filesystem_source_ids(),
    }


@router.post("/sources/filesystem/sync")
def sync_filesystem_now():
    return sync_filesystem_sources()
