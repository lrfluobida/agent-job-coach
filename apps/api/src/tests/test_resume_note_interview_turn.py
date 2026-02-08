import json

from src.skills import resume_note_interview


def test_resume_note_interview_no_repeat_and_eval(monkeypatch):
    def fake_retrieve(query: str, top_k: int, where: dict | None):
        if isinstance(where, dict) and where.get("source_type") == "resume":
            return [
                {
                    "id": "resume:0",
                    "text": "项目里做过 Redis 缓存和 Lua 脚本扣减库存。",
                    "metadata": {"source_type": "resume", "source_id": "resume_1"},
                    "score": 0.05,
                }
            ]
        if isinstance(where, dict) and where.get("source_type") == "note":
            return [
                {
                    "id": "note:qa:1",
                    "text": "Question: HashMap 原理？\nStandardAnswer:\n数组+链表/红黑树，put/get 过程会用 hash 定位和 equals 判等。\nTopic: collections",
                    "metadata": {
                        "question_id": "q_hashmap",
                        "question": "HashMap 原理？",
                        "standard_answer": "数组+链表/红黑树，put/get 过程会用 hash 定位和 equals 判等。",
                        "topic": "collections",
                        "tags": "hashmap,collection",
                        "key_points_json": json.dumps(
                            ["数组+链表/红黑树", "put/get 流程", "hash 和 equals 判等"],
                            ensure_ascii=False,
                        ),
                    },
                    "score": 0.01,
                },
                {
                    "id": "note:qa:2",
                    "text": "Question: ConcurrentHashMap 原理？\nStandardAnswer:\nJDK8 使用 CAS + synchronized 桶头锁，并发读基本无锁。\nTopic: collections",
                    "metadata": {
                        "question_id": "q_chm",
                        "question": "ConcurrentHashMap 原理？",
                        "standard_answer": "JDK8 使用 CAS + synchronized 桶头锁，并发读基本无锁。",
                        "topic": "collections",
                        "tags": "concurrenthashmap,collection",
                        "key_points_json": json.dumps(
                            ["JDK8", "CAS + synchronized", "读基本无锁"],
                            ensure_ascii=False,
                        ),
                    },
                    "score": 0.02,
                },
            ]
        return []

    monkeypatch.setattr(resume_note_interview, "retrieve", fake_retrieve)

    first_raw = resume_note_interview.run_resume_note_interview_turn.func(
        user_input="开始面试",
        history=[],
        source_id="resume_1",
        top_k=10,
        session={},
    )
    first = json.loads(first_raw)
    first_state = first["session"]["resume_interview_state"]
    assert "题目" in first["answer"]
    assert len(first_state["asked_question_ids"]) == 1
    first_qid = first_state["current_question_id"]

    second_raw = resume_note_interview.run_resume_note_interview_turn.func(
        user_input="HashMap 底层是数组和链表，查找会先 hash 再 equals。",
        history=[],
        source_id="resume_1",
        top_k=10,
        session=first_state,
    )
    second = json.loads(second_raw)
    second_state = second["session"]["resume_interview_state"]
    assert "参考答案" in second["answer"]
    assert len(second_state["asked_question_ids"]) == 2
    assert second_state["current_question_id"] != first_qid

