"""Run against DATABASE_URL from the environment. Never pass credentials as arguments."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.services.postgres_store import migrate

if __name__ == '__main__':
    if not settings.DATABASE_URL.get_secret_value():
        raise SystemExit('DATABASE_URL is required')
    try:
        migrate(settings.DATABASE_URL.get_secret_value())
    except Exception:
        raise SystemExit('Migration failed. Check database access and schema; credentials were not logged.') from None
    print('PostgreSQL schema migration complete.')
