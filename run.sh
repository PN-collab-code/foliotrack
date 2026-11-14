#!/usr/bin/env bash
# Start FolioTrack on http://127.0.0.1:${PORT:-8200}
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
. .venv/bin/activate
python -m pip install -q -r requirements.txt
exec python -m uvicorn main:app --host 127.0.0.1 --port "${PORT:-8200}"
