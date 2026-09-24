#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install -q -r requirements.txt
python scripts/setup_local_demo.py
echo "Open http://127.0.0.1:${PORT:-8000}/showcase/ or http://127.0.0.1:${PORT:-8000}/demo/"
exec uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}"
