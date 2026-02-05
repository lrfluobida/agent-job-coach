from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes_chat import router as chat_router
from src.api.routes_chat_stream import router as chat_stream_router
from src.api.routes_health import router as health_router
from src.api.routes_ingest import router as ingest_router
from src.api.routes_retrieve import router as retrieve_router
from src.api.routes_skills import router as skills_router
from src.api.routes_upload import router as upload_router
from src.core.settings import get_settings


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
app.include_router(chat_router)
app.include_router(retrieve_router)
app.include_router(skills_router)
app.include_router(chat_stream_router)
