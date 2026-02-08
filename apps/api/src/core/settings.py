from __future__ import annotations

from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(REPO_ROOT / ".env")

# settings.py 位于: repo/apps/api/src/core/settings.py
# 往上 4 层到 repo 根目录
REPO_ROOT = Path(__file__).resolve().parents[4]

class Settings(BaseModel):
    web_origin: str = "http://localhost:3000"
    chroma_dir: Path = REPO_ROOT / "data" / "chroma"
    zhipu_api_key: str | None = None
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    zhipu_chat_model: str = "glm-4-flash"
    zhipu_temperature: float = 0.2
    zhipu_timeout_s: float = 30.0
    zhipu_embed_model: str = "embedding-3"
    max_upload_mb: int = 10
    max_citations: int = 3
    filesystem_sync_enabled: bool = True
    filesystem_sync_interval_s: float = 5.0
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 1
    redis_password: str | None = None
    redis_username: str | None = None
    redis_ssl: bool = False
    redis_lock_ttl_ms: int = 15000
    redis_lock_wait_ms: int = 3000

def get_settings() -> Settings:
    import os

    web_origin = os.getenv("WEB_ORIGIN", "http://localhost:3000")

    chroma_dir_raw = os.getenv("CHROMA_DIR", "")
    if chroma_dir_raw:
        p = Path(chroma_dir_raw)
        chroma_dir = p if p.is_absolute() else (REPO_ROOT / p)
    else:
        chroma_dir = REPO_ROOT / "data" / "chroma"

    chroma_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        web_origin=web_origin,
        chroma_dir=chroma_dir,
        zhipu_api_key=os.getenv("ZHIPUAI_API_KEY"),
        zhipu_base_url=os.getenv("ZHIPUAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
        zhipu_chat_model=os.getenv("ZHIPUAI_CHAT_MODEL", "glm-4-flash"),
        zhipu_temperature=float(os.getenv("ZHIPUAI_TEMPERATURE", "0.2")),
        zhipu_timeout_s=float(os.getenv("ZHIPUAI_TIMEOUT_S", "30")),
        zhipu_embed_model=os.getenv("ZHIPUAI_EMBED_MODEL", "embedding-3"),
        max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "10")),
        max_citations=int(os.getenv("MAX_CITATIONS", "3")),
        filesystem_sync_enabled=os.getenv("FILESYSTEM_SYNC_ENABLED", "true").lower() in {"1", "true", "yes", "on"},
        filesystem_sync_interval_s=float(os.getenv("FILESYSTEM_SYNC_INTERVAL_S", "5")),
        redis_host=os.getenv("REDIS_HOST", "localhost"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
        redis_db=int(os.getenv("REDIS_DB", "1")),
        redis_password=os.getenv("REDIS_PASSWORD"),
        redis_username=os.getenv("REDIS_USERNAME"),
        redis_ssl=os.getenv("REDIS_SSL", "false").lower() in {"1", "true", "yes", "on"},
        redis_lock_ttl_ms=int(os.getenv("REDIS_LOCK_TTL_MS", "15000")),
        redis_lock_wait_ms=int(os.getenv("REDIS_LOCK_WAIT_MS", "3000")),
    )
