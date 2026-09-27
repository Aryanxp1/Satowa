#!/usr/bin/env python3
"""SETOWA CLI Entrypoint."""
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.cli import main

if __name__ == "__main__":
    sys.exit(main())
