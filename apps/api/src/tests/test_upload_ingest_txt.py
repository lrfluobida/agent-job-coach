from fastapi.testclient import TestClient

from src.main import app


def test_upload_ingest_txt():
    client = TestClient(app)
    files = {
        "file": ("sample.txt", "hello world", "text/plain"),
    }
    data = {"source_type": "upload"}
    resp = client.post("/ingest/file", files=files, data=data)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("ok") is True
    assert body.get("chunks", 0) >= 1
