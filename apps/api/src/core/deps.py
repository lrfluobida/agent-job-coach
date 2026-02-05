import chromadb
from src.core.settings import get_settings

_client = None

def get_chroma_client():
    global _client
    if _client is None:
        settings = get_settings()
        _client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    return _client
