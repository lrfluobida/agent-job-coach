from src.graph import job_coach_graph


def test_graph_direct_answer(monkeypatch):
    def fake_chat(messages):
        return '{"action":"final","answer":"你好"}'

    monkeypatch.setattr(job_coach_graph, "chat", fake_chat)

    result = job_coach_graph.run_graph("测试问题", history=[])
    assert result.get("answer") == "你好"
    assert result.get("tool_results") == []
