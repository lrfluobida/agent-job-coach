from src.graph import job_coach_graph
from src.skills import interview_qa


def test_graph_calls_interview_tool(monkeypatch):
    def fake_router_chat(messages):
        return (
            '{"action":"tool","name":"run_interview_turn",'
            '"args":{"user_input":"Redis 是单线程的。","history":[],"topic":"Redis"}}'
        )

    def fake_interview_chat(messages):
        return "**基本正确。** Redis 6.0 引入了多线程 I/O，你能解释它解决了什么问题吗？"

    monkeypatch.setattr(job_coach_graph, "chat", fake_router_chat)
    monkeypatch.setattr(interview_qa, "chat", fake_interview_chat)

    result = job_coach_graph.run_graph("Redis 是单线程的。", history=[])
    assert "Redis 6.0" in result.get("answer", "")
    assert len(result.get("tool_results", [])) == 1
    assert result.get("tool_results", [])[0].get("name") == "run_interview_turn"
