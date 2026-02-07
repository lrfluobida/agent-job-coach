from fastapi.testclient import TestClient

from src.main import app


def test_chat_graph_smoke():
    client = TestClient(app)
    ingest = {
        "source_id": "resume_test",
        "source_type": "resume",
        "text": "黑马点评项目：Redis Lua 原子扣减库存，一人一单，分布式锁。",
    }
    resp = client.post("/ingest", json=ingest)
    assert resp.status_code == 200

    chat = {"question": "黑马点评如何防止超卖？", "top_k": 3, "filter": {"source_type": "resume"}}
    resp = client.post("/chat/stream", json=chat)
    assert resp.status_code == 200
    text = resp.text
    assert "event: done" in text
    assert "event: token" in text
