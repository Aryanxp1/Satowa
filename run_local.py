"""Universal Cross-Platform Local Demo Runner for SETOWA.

Works identically on Windows (PowerShell, CMD), macOS, and Linux:
    python run_local.py

Features:
- Auto-detects virtual environment in backend/venv or backend/.venv
- Creates virtual environment and installs dependencies if missing
- Automatically configures PYTHONPATH and working directory
- Runs environment validation, reviewer credentials setup, and data seeding
- Launches the FastAPI local server with the full interactive banner
"""
import os
from pathlib import Path
import subprocess
import sys


def find_or_create_venv(root_dir: Path) -> Path:
    backend_dir = root_dir / "backend"
    candidate_paths = [
        backend_dir / "venv" / "Scripts" / "python.exe",
        backend_dir / ".venv" / "Scripts" / "python.exe",
        backend_dir / "venv" / "bin" / "python",
        backend_dir / ".venv" / "bin" / "python",
        root_dir / "venv" / "Scripts" / "python.exe",
        root_dir / ".venv" / "Scripts" / "python.exe",
        root_dir / "venv" / "bin" / "python",
        root_dir / ".venv" / "bin" / "python",
    ]

    for cand in candidate_paths:
        if cand.exists():
            return cand

    # Check if current interpreter is already a venv
    if sys.prefix != sys.base_prefix:
        return Path(sys.executable)

    # Create virtual environment inside backend/venv
    target_venv = backend_dir / "venv"
    print(f"[Setowa] Creating virtual environment at {target_venv}...")
    subprocess.run([sys.executable, "-m", "venv", str(target_venv)], check=True)

    venv_python = (
        target_venv / "Scripts" / "python.exe"
        if os.name == "nt"
        else target_venv / "bin" / "python"
    )

    req_file = backend_dir / "requirements.txt"
    if req_file.exists():
        print("[Setowa] Installing backend requirements...")
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "-q", "-r", str(req_file)],
            check=True,
        )

    return venv_python


def main():
    root_dir = Path(__file__).resolve().parent
    backend_dir = root_dir / "backend"
    start_script = backend_dir / "scripts" / "start_demo.py"

    os.environ["ENVIRONMENT"] = os.environ.get("ENVIRONMENT", "development")
    os.environ["LOCAL_DEMO"] = os.environ.get("LOCAL_DEMO", "true")

    venv_python = find_or_create_venv(root_dir)

    # Forward all CLI arguments to start_demo.py
    cmd = [str(venv_python), str(start_script)] + sys.argv[1:]

    try:
        result = subprocess.run(cmd, cwd=backend_dir)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n[Setowa] Server stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
