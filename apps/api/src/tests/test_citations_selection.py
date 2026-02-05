from types import SimpleNamespace

from src.graph import job_coach_graph


def test_citations_selection_from_markers(monkeypatch):
    def fake_chat(messages):
        return "回答内容 [@resume_001:0] 其他内容"

    def fake_retrieve(*args, **kwargs):
        return [
            {"id": "resume_001:0", "text": "证据内容", "metadata": {}, "score": 0.1},
            {"id": "resume_001:1", "text": "无关内容", "metadata": {}, "score": 0.2},
        ]

    monkeypatch.setattr(job_coach_graph, "chat", fake_chat)
    monkeypatch.setattr(job_coach_graph, "retrieve", fake_retrieve)
    monkeypatch.setattr(job_coach_graph, "get_settings", lambda: SimpleNamespace(zhipu_api_key="x", max_citations=3))

    result = job_coach_graph.run_graph("测试问题", top_k=5, filter=None)
    assert result.get("answer") == "回答内容 其他内容"
    assert len(result.get("citations", [])) == 1
    assert result.get("citations")[0].get("id") == "resume_001:0"


def test_tool_citations_preserved(monkeypatch):
    state = {
        "tool_results": [
            {
                "name": "skill_interview_qa",
                "result": {
                    "answer": "答案",
                    "citations": ["resume_001:0"],
                    "used_context": [
                        {
                            "id": "resume_001:0",
                            "text": "证据内容",
                            "metadata": {},
                            "score": 0.1,
                        }
                    ],
                },
            }
        ]
    }

    monkeypatch.setattr(
        job_coach_graph,
        "get_settings",
        lambda: SimpleNamespace(zhipu_api_key="x", max_citations=3),
    )

    result = job_coach_graph.generate_final(state)
    assert len(result.get("citations", [])) == 1
    assert result.get("citations")[0].get("id") == "resume_001:0"
