"""One-Command Cross-Platform Local Demo Runner for SETOWA.

Validates environment, ensures database migrations, seeds deterministic demo data,
and launches the FastAPI local server with a clear banner.
"""
from pathlib import Path
import os
import sys

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.services.env_validator import validate_environment
from setup_local_demo import ensure_local_env
from seed_demo import seed_demo_dataset, DEMO_SHARE_TOKEN


def start():
    print("=" * 60)
    print("   SETOWA — Marine & Land Environmental Evidence System")
    print("   Local Hackathon Showcase & Verification Runner")
    print("=" * 60)

    # 1. Ensure local reviewer token
    ensure_local_env()

    # 2. Audit environment safely
    env_info = validate_environment(settings)
    print(f"\n[Environment Status]")
    print(f"  Mode:        {env_info['mode']}")
    print(f"  Environment: {env_info['environment']}")
    print(f"  Cloudinary:  {'Configured' if env_info['cloudinary_ready'] else 'Unconfigured / Local Mock'}")
    print(f"  Gemini:      {'Configured' if env_info['gemini_ready'] else 'Unconfigured / Local Mock'}")

    # 3. Seed deterministic demo data
    print(f"\n[Seeding Demo Data]")
    seed_demo_dataset()

    # 4. Banner & Server launch
    host = settings.HOST if settings.HOST != "0.0.0.0" else "127.0.0.1"
    port = int(os.environ.get("PORT", settings.PORT))

    print("\n" + "=" * 60)
    print("  SETOWA SYSTEM IS READY")
    print(f"  Workspace UI:   http://{host}:{port}/demo/")
    print(f"  Public Story:   http://{host}:{port}/share/{DEMO_SHARE_TOKEN}")
    print(f"  API Docs:       http://{host}:{port}/docs")
    print(f"  Health Check:   http://{host}:{port}/api/v1/health")
    print(f"  Readiness:      http://{host}:{port}/api/v1/ready")
    print("=" * 60 + "\n")

    import uvicorn
    uvicorn.run("app.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    start()
