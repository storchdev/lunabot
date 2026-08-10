#!/usr/bin/env python3
"""Runs a shell command on the prod server via /api/sh.

Usage: scripts/sh.sh '<command>'
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _remote import call  # noqa: E402


def main():
    if len(sys.argv) != 2:
        print("Usage: sh.sh '<command>'", file=sys.stderr)
        sys.exit(1)

    result = call("/api/sh", {"command": sys.argv[1]})

    if "error" in result:
        print(result["error"], file=sys.stderr)
        sys.exit(1)

    if result.get("stdout"):
        print(result["stdout"], end="")
    if result.get("stderr"):
        print(result["stderr"], end="", file=sys.stderr)

    sys.exit(result.get("return_code") or 0)


if __name__ == "__main__":
    main()
