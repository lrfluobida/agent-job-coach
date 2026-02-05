from fastapi import APIRouter

from src.core.settings import get_settings


router = APIRouter()


@router.get("/health")
def health():
    settings = get_settings()
    return {"ok": True, "chroma_path": str(settings.chroma_dir)}
