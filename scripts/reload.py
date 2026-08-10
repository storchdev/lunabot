#!/usr/bin/env python3
"""Reloads shared modules and/or cogs on the live bot via /api/reload.

Modules (e.g. `utils`) are reloaded via importlib against everything already
in sys.modules -- for `utils` specifically this also reloads
cogs.layouts.layout and cogs.embeds.editor, which cogs/utils/__init__.py
re-exports from (see cogs/utils/helpers.py:reload_module). Cogs are reloaded
via bot.reload_extension, which re-runs their setup() and picks up the
already-reloaded module code.

Usage:
    scripts/reload.sh -m <modules> -c <cogs>

Comma-separated for multiples.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _remote import call  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-m", "--modules", default="", help="comma-separated shared modules to reload (e.g. utils)")
    parser.add_argument("-c", "--cogs", default="", help="comma-separated cogs to reload (e.g. levels,economy)")
    args = parser.parse_args()

    modules = [m.strip() for m in args.modules.split(",") if m.strip()]
    cogs = [c.strip() for c in args.cogs.split(",") if c.strip()]

    if not modules and not cogs:
        parser.error("must specify -m and/or -c")

    result = call("/api/reload", {"modules": modules, "cogs": cogs})

    if "error" in result:
        print(result["error"], file=sys.stderr)
        sys.exit(1)

    for line in result.get("info", []):
        print(line)

    if any("Error" in line for line in result.get("info", [])):
        sys.exit(1)


if __name__ == "__main__":
    main()
