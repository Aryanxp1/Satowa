#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/backend"
if [ ! -d .venv ] && [ ! -d venv ]; then
  python3 -m venv .venv 2>/dev/null || python -m venv .venv
fi
if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
elif [ -f .venv/Scripts/activate ]; then
  source .venv/Scripts/activate
elif [ -f venv/bin/activate ]; then
  source venv/bin/activate
elif [ -f venv/Scripts/activate ]; then
  source venv/Scripts/activate
fi
python -m pip install -q -r requirements.txt
python scripts/setup_local_demo.py
echo "Open http://127.0.0.1:${PORT:-8000}/ for the Setowa local workspace"
exec uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}"
