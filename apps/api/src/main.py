import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes_chat_stream import router as chat_stream_router
from src.api.routes_health import router as health_router
from src.api.routes_ingest import router as ingest_router
from src.api.routes_retrieve import router as retrieve_router
from src.api.routes_skills import router as skills_router
from src.api.routes_sources import router as sources_router
from src.api.routes_upload import router as upload_router
from src.core.settings import get_settings
from src.ingest.filesystem_sync import sync_filesystem_sources


app = FastAPI()

settings = get_settings()
allow_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
if settings.web_origin and settings.web_origin not in allow_origins:
    allow_origins.append(settings.web_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(upload_router)
app.include_router(retrieve_router)
app.include_router(skills_router)
app.include_router(sources_router)
app.include_router(chat_stream_router)


_sync_task: asyncio.Task | None = None


async def _filesystem_sync_loop(interval_s: float):
    while True:
        await asyncio.to_thread(sync_filesystem_sources)
        await asyncio.sleep(interval_s)


@app.on_event("startup")
async def _startup_sync():
    global _sync_task
    cfg = get_settings()
    if not cfg.filesystem_sync_enabled:
        return
    await asyncio.to_thread(sync_filesystem_sources)
    _sync_task = asyncio.create_task(_filesystem_sync_loop(cfg.filesystem_sync_interval_s))


@app.on_event("shutdown")
async def _shutdown_sync():
    global _sync_task
    if _sync_task is None:
        return
    _sync_task.cancel()
    try:
        await _sync_task
    except asyncio.CancelledError:
        pass
    _sync_task = None
