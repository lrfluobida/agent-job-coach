from types import SimpleNamespace

from src.graph import job_coach_graph


def test_graph_coercion(monkeypatch):
    def fake_chat(messages):
        return '```json {"answer":"你好","citations":[{"id":"c1","quote":"引用内容"}]} ```'

    monkeypatch.setattr(job_coach_graph, "chat", fake_chat)
    monkeypatch.setattr(job_coach_graph, "get_settings", lambda: SimpleNamespace(zhipu_api_key="x"))

    result = job_coach_graph.run_graph("测试问题", top_k=1, filter=None)
    assert result.get("answer") == "你好"
