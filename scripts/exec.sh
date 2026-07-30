#!/usr/bin/env bash
# Executes Python code on the live bot. The `bot` object is available in scope.
# Last expression is auto-returned. See scripts/exec.py.
set -euo pipefail
exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/exec.py" "$@"
