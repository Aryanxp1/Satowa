#!/usr/bin/env bash
set -e
(set -o pipefail 2>/dev/null) && set -o pipefail || true

cd "$(dirname "$0")/backend"
export ENVIRONMENT=development
export LOCAL_DEMO=true

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
exec "$PYTHON_CMD" scripts/start_demo.py
