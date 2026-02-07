from fastapi.testclient import TestClient

from src.main import app


def test_upload_ingest_txt():
    client = TestClient(app)
    files = {
        "file": ("sample.txt", "hello world", "text/plain"),
    }
    data = {"source_type": "note"}
    resp = client.post("/ingest/file", files=files, data=data)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("ok") is True
    assert body.get("chunks", 0) >= 1
    assert body.get("reused") is False


def test_upload_ingest_txt_reuse_same_source():
    client = TestClient(app)
    files = {"file": ("sample.txt", "same text for dedupe", "text/plain")}
    data = {"source_type": "resume"}

    first = client.post("/ingest/file", files=files, data=data)
    assert first.status_code == 200
    b1 = first.json()
    assert b1.get("ok") is True
    assert isinstance(b1.get("source_id"), str) and b1.get("source_id")

    second = client.post("/ingest/file", files=files, data=data)
    assert second.status_code == 200
    b2 = second.json()
    assert b2.get("ok") is True
    assert b2.get("reused") is True
    assert b2.get("source_id") == b1.get("source_id")
