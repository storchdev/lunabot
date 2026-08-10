#!/usr/bin/env bash
# Runs a shell command on the prod server via /api/sh. See scripts/sh.py.
set -euo pipefail
exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/sh.py" "$@"
