from src.api import routes_chat_stream


class _FakeCollection:
    def get(self, ids, include):
        _ = include
        return {
            "ids": ids,
            "documents": [f"doc::{cid}" for cid in ids],
            "metadatas": [{"source_id": "s1", "source_type": "note"} for _ in ids],
        }


def test_compact_result_only_stores_answer_and_citation_ids():
    result = {
        "answer": "hello",
        "citations": [{"id": "c1", "quote": "q1"}, "c2"],
        "used_context": [{"id": "c1", "text": "long text"}],
    }
    compact = routes_chat_stream._compact_result_for_request_cache(result)
    assert compact == {"answer": "hello", "citation_ids": ["c1", "c2"]}


def test_cached_payload_hydrates_used_context_by_citation_ids(monkeypatch):
    monkeypatch.setattr(routes_chat_stream, "get_collection", lambda: _FakeCollection())
    parsed = routes_chat_stream._result_from_cached_payload(
        {"answer": "ok", "citation_ids": ["c1", "c2"]}
    )
    assert parsed["answer"] == "ok"
    assert parsed["citations"] == ["c1", "c2"]
    assert len(parsed["used_context"]) == 2
    assert parsed["used_context"][0]["id"] == "c1"
    assert parsed["used_context"][0]["text"] == "doc::c1"

