from __future__ import annotations

import argparse
import sys
from pathlib import Path

import chromadb


DEFAULT_COLLECTION = "job_coach"
DEFAULT_CHROMA_DIR = Path(__file__).resolve().parents[1] / "data" / "chroma"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Delete all Chroma records by source_id."
    )
    parser.add_argument(
        "--source-id",
        required=True,
        help="source_id to delete (exact match).",
    )
    parser.add_argument(
        "--chroma-dir",
        default=str(DEFAULT_CHROMA_DIR),
        help=f"Chroma persist directory. Default: {DEFAULT_CHROMA_DIR}",
    )
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION,
        help=f"Collection name. Default: {DEFAULT_COLLECTION}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only show how many records would be deleted.",
    )
    return parser


def _count_ids_by_source(collection, source_id: str) -> tuple[int, list[str]]:
    result = collection.get(where={"source_id": source_id}, include=[])
    ids = result.get("ids") or []
    return len(ids), ids


def main() -> int:
    args = _build_parser().parse_args()
    source_id = args.source_id.strip()
    if not source_id:
        print("error: --source-id cannot be empty", file=sys.stderr)
        return 2

    chroma_dir = Path(args.chroma_dir).resolve()
    client = chromadb.PersistentClient(path=str(chroma_dir))
    collection = client.get_or_create_collection(name=args.collection)

    count, ids = _count_ids_by_source(collection, source_id)
    if count == 0:
        print(
            f"no records found for source_id='{source_id}' "
            f"in collection='{args.collection}'"
        )
        return 0

    if args.dry_run:
        print(
            f"dry-run: would delete {count} record(s) "
            f"for source_id='{source_id}'"
        )
        return 0

    collection.delete(ids=ids)
    print(
        f"deleted {count} record(s) "
        f"for source_id='{source_id}' "
        f"from collection='{args.collection}'"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
