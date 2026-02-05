from src.tools.registry import call_tool


def test_tools_registry_retrieve():
    call_tool(
        "ingest_text",
        {"text": "工具测试：分布式锁与异步下单", "source_type": "note", "source_id": "tool_note"},
        context={},
    )
    result = call_tool(
        "rag_retrieve",
        {"query": "分布式锁", "top_k": 1, "filter": {"source_type": "note"}},
        context={},
    )
    assert isinstance(result.get("results"), list)
