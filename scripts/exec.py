#!/usr/bin/env python3
"""Executes Python code on the live bot. `bot` is in scope; last expression is auto-returned.

Usage: scripts/exec.sh '<python code>'
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _remote import exec_code  # noqa: E402


def main():
    if len(sys.argv) != 2:
        print("Usage: exec.sh '<python code>'", file=sys.stderr)
        sys.exit(1)

    result = exec_code(sys.argv[1])

    if result.get("stdout"):
        print(result["stdout"], end="")

    if "error" in result:
        print(result["error"], file=sys.stderr)
        sys.exit(1)

    for r in result.get("results", []):
        print(r)


if __name__ == "__main__":
    main()
