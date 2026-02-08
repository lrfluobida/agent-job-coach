from pathlib import Path

from src.core import deps
from src.ingest.filesystem_sync import list_filesystem_source_ids, sync_filesystem_sources
from src.rag.store import get_collection


def test_sync_add_and_delete_by_filesystem(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    jd_dir = data_root / "jd"
    jd_dir.mkdir(parents=True, exist_ok=True)
    f = jd_dir / "sample.txt"
    f.write_text("Redis Lua 原子扣减库存", encoding="utf-8")

    chroma_dir = tmp_path / "chroma"
    monkeypatch.setenv("CHROMA_DIR", str(chroma_dir))
    deps._client = None

    add_result = sync_filesystem_sources(data_root=data_root)
    assert add_result["upserted"] == 1
    assert add_result["deleted"] == 0

    items = list_filesystem_source_ids(data_root=data_root)
    assert len(items) == 1
    source_id = items[0]["source_id"]

    collection = get_collection()
    got = collection.get(where={"source_id": source_id}, include=[])
    assert len(got.get("ids") or []) > 0

    f.unlink()
    del_result = sync_filesystem_sources(data_root=data_root)
    assert del_result["deleted"] == 1

    got_after = collection.get(where={"source_id": source_id}, include=[])
    assert len(got_after.get("ids") or []) == 0


def test_sync_note_file_ingests_structured_qa_cards(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    notes_dir = data_root / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    note_file = notes_dir / "java_note.md"
    note_file.write_text(
        """
## 5.1 语言基础
### 1）Integer 和 int 的区别？
- int 是基本类型
- Integer 是包装类型

### 2）HashMap 原理？
- 数组 + 链表/红黑树
- put/get 有 hash 和 equals
""",
        encoding="utf-8",
    )

    chroma_dir = tmp_path / "chroma"
    monkeypatch.setenv("CHROMA_DIR", str(chroma_dir))
    deps._client = None

    add_result = sync_filesystem_sources(data_root=data_root)
    assert add_result["upserted"] == 1
    items = list_filesystem_source_ids(data_root=data_root)
    assert len(items) == 1
    source_id = items[0]["source_id"]

    collection = get_collection()
    got = collection.get(where={"source_id": source_id}, include=["metadatas", "documents"])
    ids = got.get("ids") or []
    metadatas = got.get("metadatas") or []
    assert len(ids) == 2
    assert all(isinstance(meta, dict) and meta.get("doc_kind") == "qa_card" for meta in metadatas)
    assert all(isinstance(meta, dict) and meta.get("source_type") == "note" for meta in metadatas)

    note_file.unlink()
    del_result = sync_filesystem_sources(data_root=data_root)
    assert del_result["deleted"] == 1
    got_after = collection.get(where={"source_id": source_id}, include=[])
    assert len(got_after.get("ids") or []) == 0
