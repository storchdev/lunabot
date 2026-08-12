"""Shared helper for talking to the live bot's webserver API (cogs/webserver.py).

Not a CLI itself -- imported by exec.py, layout.py, etc. Uses only the stdlib
so these scripts run with a bare `python3`, no venv needed.
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from config import JSK_KEY, WEBSERVER_BASE_URL as BASE_URL  # noqa: E402


def call(endpoint: str, payload: dict, timeout: int = 35) -> dict:
    req = urllib.request.Request(
        f"{BASE_URL}{endpoint}",
        data=json.dumps(payload).encode(),
        headers={"Authorization": JSK_KEY, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"error": f"HTTP {e.code}: {body}"}


def exec_code(code: str) -> dict:
    """Runs Python code on the live bot. `bot` is in scope; last expression is auto-returned."""
    return call("/api/exec", {"code": code})


def exec_code_or_die(code: str) -> str:
    """Like exec_code, but exits the process on error and returns the first result (or '')."""
    result = exec_code(code)
    if result.get("stdout"):
        print(result["stdout"], end="", file=sys.stderr)
    if "error" in result:
        print(result["error"], file=sys.stderr)
        sys.exit(1)
    results = result.get("results", [])
    return results[0] if results else ""
