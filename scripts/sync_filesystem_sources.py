from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
API_SRC = REPO_ROOT / "apps" / "api"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from src.ingest.filesystem_sync import list_filesystem_source_ids, sync_filesystem_sources  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Sync data/jd|notes|resume to Chroma.")
    p.add_argument("--list", action="store_true", help="Only list file -> source_id mapping.")
    p.add_argument("--watch", action="store_true", help="Run sync in polling loop.")
    p.add_argument("--interval", type=float, default=5.0, help="Watch interval seconds.")
    return p


def _print_items(items: list[dict]):
    for item in items:
        print(f"{item['source_id']}\t{item['source_type']}\t{item['path']}")


def main() -> int:
    args = _parser().parse_args()
    if args.list:
        _print_items(list_filesystem_source_ids())
        return 0

    if not args.watch:
        result = sync_filesystem_sources()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    try:
        while True:
            result = sync_filesystem_sources()
            print(
                f"[sync] upserted={result['upserted']} unchanged={result['unchanged']} "
                f"deleted={result['deleted']} failed={result['failed']}"
            )
            time.sleep(max(0.5, args.interval))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
