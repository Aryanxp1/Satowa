"""Read-only Gemini API credential check. No observations or media are modified.

Run from backend/: python scripts/check_gemini.py
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.config import settings


def main():
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise SystemExit('GEMINI_API_KEY is required in credential.json or backend/.env')

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_VISION_MODEL}?key={api_key}"
    try:
        resp = httpx.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            display_name = data.get('displayName', settings.GEMINI_VISION_MODEL)
            print(f'Gemini API reachable and key valid for model {settings.GEMINI_VISION_MODEL} ({display_name}).')
        else:
            raise SystemExit(f'Gemini API returned status {resp.status_code}. Key or model may be invalid; secrets were not printed.')
    except httpx.HTTPError:
        raise SystemExit('Gemini network check failed. Check connectivity and credentials; secrets were not printed.') from None


if __name__ == '__main__':
    main()
