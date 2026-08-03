#!/usr/bin/env bash
# Rsyncs files to the VPS, preserving relative paths. Run from project root.
# Usage: scripts/sync.sh cogs/webserver.py [more files...]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_HOST="vps"
REMOTE_PATH="bots/lunabot"

if [ "$#" -eq 0 ]; then
    echo "Usage: $0 <files...>" >&2
    exit 1
fi

cd "$REPO_ROOT"
for f in "$@"; do
    rsync -av --relative "$f" "${REMOTE_HOST}:${REMOTE_PATH}/"
done
