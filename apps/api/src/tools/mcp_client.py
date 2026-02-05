from __future__ import annotations

import json
import os
import urllib.request


DEFAULT_TIMEOUT_S = 15
MAX_TEXT_LEN = 2000


def _get_server_url() -> str | None:
    return os.getenv("MCP_SERVER_URL")


def _timeout() -> float:
    return float(os.getenv("MCP_TIMEOUT_S", str(DEFAULT_TIMEOUT_S)))


def _allowlist() -> set[str] | None:
    raw = os.getenv("MCP_ALLOWLIST")
    if not raw:
        return None
    return {item.strip() for item in raw.split(",") if item.strip()}


def _truncate(value):
    if isinstance(value, str) and len(value) > MAX_TEXT_LEN:
        return value[:MAX_TEXT_LEN] + "..."
    if isinstance(value, list):
        return [_truncate(v) for v in value]
    if isinstance(value, dict):
        return {k: _truncate(v) for k, v in value.items()}
    return value


def _request_json(url: str, payload: dict | None = None) -> dict:
    data = None
    method = "GET"
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=_timeout()) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return json.loads(body)


def mcp_list_tools() -> list[dict]:
    base = _get_server_url()
    if not base:
        return []

    for path, payload in [("/tools", None), ("/tools/list", {}), ("/tools/list", None)]:
        try:
            data = _request_json(base.rstrip("/") + path, payload)
            tools = data.get("tools") if isinstance(data, dict) else data
            if isinstance(tools, list):
                return tools
        except Exception:
            continue
    return []


def mcp_call_tool(name: str, args: dict) -> dict:
    base = _get_server_url()
    if not base:
        return {"ok": False, "error": "MCP not configured"}

    allowlist = _allowlist()
    if allowlist is not None and name not in allowlist:
        return {"ok": False, "error": "MCP tool not allowlisted"}

    for path in ["/tools/call", "/invoke"]:
        try:
            payload = {"name": name, "args": args}
            data = _request_json(base.rstrip("/") + path, payload)
            if isinstance(data, dict):
                return _truncate(data)
        except Exception as exc:
            last_exc = exc
            continue

    return {"ok": False, "error": "MCP call failed"}
