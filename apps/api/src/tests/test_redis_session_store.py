from types import SimpleNamespace

from src.graph import redis_session_store


class _FakePipeline:
    def __init__(self, redis_obj):
        self._r = redis_obj
        self._ops: list[tuple] = []

    def hset(self, key, mapping=None):
        self._ops.append(("hset", key, mapping or {}))
        return self

    def sadd(self, key, *values):
        self._ops.append(("sadd", key, values))
        return self

    def execute(self):
        for op, key, payload in self._ops:
            if op == "hset":
                self._r.hset(key, mapping=payload)
            elif op == "sadd":
                self._r.sadd(key, *payload)
        self._ops.clear()


class _FakeRedis:
    def __init__(self):
        self.h: dict[str, dict[str, str]] = {}
        self.s: dict[str, set[str]] = {}
        self.kv: dict[str, str] = {}

    def ping(self):
        return True

    def hget(self, key, field):
        return self.h.get(key, {}).get(field)

    def hset(self, key, field=None, value=None, mapping=None):
        if key not in self.h:
            self.h[key] = {}
        if mapping is not None:
            for k, v in mapping.items():
                self.h[key][str(k)] = str(v)
            return
        self.h[key][str(field)] = str(value)

    def smembers(self, key):
        return set(self.s.get(key, set()))

    def sadd(self, key, *values):
        if key not in self.s:
            self.s[key] = set()
        for v in values:
            self.s[key].add(str(v))

    def set(self, key, value, nx=False, px=None):
        _ = px
        if nx and key in self.kv:
            return False
        self.kv[key] = str(value)
        return True

    def eval(self, script, numkeys, key, owner):
        _ = script, numkeys
        if self.kv.get(key) == owner:
            del self.kv[key]
            return 1
        return 0

    def pipeline(self):
        return _FakePipeline(self)


def test_state_roundtrip_and_permanent_asked(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(redis_session_store, "get_redis_client", lambda: fake)

    state = {
        "source_id": "resume_1",
        "topic": "ai",
        "asked_question_ids": ["q1", "q2"],
        "current_question_id": "q2",
    }
    redis_session_store.set_resume_interview_state("conv_1", state)
    loaded = redis_session_store.get_resume_interview_state("conv_1")
    assert loaded.get("source_id") == "resume_1"
    assert set(loaded.get("asked_question_ids", [])) == {"q1", "q2"}

    redis_session_store.set_resume_interview_state(
        "conv_1",
        {"source_id": "resume_1", "asked_question_ids": ["q3"]},
    )
    loaded2 = redis_session_store.get_resume_interview_state("conv_1")
    assert set(loaded2.get("asked_question_ids", [])) == {"q1", "q2", "q3"}


def test_request_result_roundtrip(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(redis_session_store, "get_redis_client", lambda: fake)
    redis_session_store.set_request_result("conv_2", "req_1", {"answer": "ok"})
    cached = redis_session_store.get_request_result("conv_2", "req_1")
    assert cached == {"answer": "ok"}


def test_lock_acquire_release(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(redis_session_store, "get_redis_client", lambda: fake)
    monkeypatch.setattr(
        redis_session_store,
        "get_settings",
        lambda: SimpleNamespace(redis_lock_wait_ms=10, redis_lock_ttl_ms=1000),
    )
    assert redis_session_store.acquire_conversation_lock("conv_3", "owner_a") is True
    assert redis_session_store.acquire_conversation_lock("conv_3", "owner_b") is False
    redis_session_store.release_conversation_lock("conv_3", "owner_a")
    assert redis_session_store.acquire_conversation_lock("conv_3", "owner_b") is True

