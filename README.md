## Dev

### Backend
cd apps/api
uv run uvicorn src.main:app --port 8000

### Frontend
cd apps/web
npm run dev

Open:
- http://localhost:3000
- http://127.0.0.1:8000/docs

### Filesystem Auto Sync

When backend is running, files under `data/jd`, `data/notes`, `data/resume` are auto-synced to Chroma:
- Add/modify files: auto upsert to vector DB
- Delete files: auto delete corresponding `source_id` from Chroma

Env:
- `FILESYSTEM_SYNC_ENABLED=true|false` (default `true`)
- `FILESYSTEM_SYNC_INTERVAL_S=5` (poll interval seconds)

Manual tools:
- Run once: `uv run python scripts/sync_filesystem_sources.py`
- Watch mode: `uv run python scripts/sync_filesystem_sources.py --watch --interval 5`
- List file -> source_id: `uv run python scripts/sync_filesystem_sources.py --list`
