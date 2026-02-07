from pathlib import Path

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
