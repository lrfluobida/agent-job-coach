Set-Location "$PSScriptRoot\..\apps\api"
uv run uvicorn src.main:app --port 8000
