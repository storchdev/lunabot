#!/usr/bin/env bash
# Reloads shared modules and/or cogs on the live bot via /api/reload. See scripts/reload.py.
set -euo pipefail
exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/reload.py" "$@"
