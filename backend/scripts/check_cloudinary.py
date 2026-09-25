"""Read-only Cloudinary credential check. No media is uploaded or changed.

Run from backend/: python scripts/check_cloudinary.py
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cloudinary
import cloudinary.api

from app.config import settings


def main():
    secret = settings.CLOUDINARY_API_SECRET.get_secret_value()
    if not all((settings.CLOUDINARY_CLOUD_NAME, settings.CLOUDINARY_API_KEY, secret)):
        raise SystemExit('Cloudinary cloud name, API key, and API secret are required in credential.json or backend/.env')
    cloudinary.config(cloud_name=settings.CLOUDINARY_CLOUD_NAME,
                      api_key=settings.CLOUDINARY_API_KEY, api_secret=secret,
                      secure=True)
    try:
        result = cloudinary.api.ping()
    except Exception:
        raise SystemExit('Cloudinary ping failed. Check credentials and connectivity; secrets were not printed.') from None
    print(f'Cloudinary API reachable for cloud {settings.CLOUDINARY_CLOUD_NAME}: {result.get("status", "ok")}')


if __name__ == '__main__':
    main()
