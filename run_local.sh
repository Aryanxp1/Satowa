#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/backend"

if [ ! -d .venv ] && [ ! -d venv ]; then
  if command -v python3 >/dev/null 2>&1; then
    python3 -m venv .venv
  elif command -v python >/dev/null 2>&1; then
    python -m venv .venv
  fi
fi

PYTHON_CMD=""
if [ -f .venv/bin/python ]; then
  PYTHON_CMD=".venv/bin/python"
elif [ -f .venv/Scripts/python.exe ]; then
  PYTHON_CMD=".venv/Scripts/python.exe"
elif [ -f venv/bin/python ]; then
  PYTHON_CMD="venv/bin/python"
elif [ -f venv/Scripts/python.exe ]; then
  PYTHON_CMD="venv/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD="python"
else
  echo "Error: Python was not found." >&2
  exit 1
fi

"$PYTHON_CMD" -m pip install -q -r requirements.txt
"$PYTHON_CMD" scripts/setup_local_demo.py
echo "Open http://127.0.0.1:${PORT:-8000}/ for the Setowa local workspace"
exec "$PYTHON_CMD" -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}"
