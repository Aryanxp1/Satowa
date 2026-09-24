"""Small persistent store for the reviewable cleanup demo."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS sites (
 id TEXT PRIMARY KEY, name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS visits (
 id TEXT PRIMARY KEY, site_id TEXT NOT NULL REFERENCES sites(id),
 visited_on TEXT NOT NULL, label TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assets (
 asset_id TEXT PRIMARY KEY, visit_id TEXT NOT NULL REFERENCES visits(id),
 public_id TEXT NOT NULL, version INTEGER NOT NULL, secure_url TEXT NOT NULL,
 source TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL,
 format TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
 id TEXT PRIMARY KEY, site_id TEXT NOT NULL REFERENCES sites(id),
 before_asset_id TEXT NOT NULL REFERENCES assets(asset_id),
 after_asset_id TEXT NOT NULL REFERENCES assets(asset_id),
 ai_draft TEXT, working_text TEXT, approved_text TEXT,
 review_status TEXT NOT NULL CHECK(review_status IN ('pending','approved','rejected','unreliable')),
 reliability_reason TEXT, reviewed_by TEXT, reviewed_at TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observation_revisions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 observation_id TEXT NOT NULL REFERENCES observations(id),
 action TEXT NOT NULL, actor TEXT NOT NULL, text TEXT, at TEXT NOT NULL,
 before_asset_id TEXT NOT NULL, after_asset_id TEXT NOT NULL
);
"""


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def new_id():
    return uuid4().hex


@contextmanager
def connection():
    path = Path(settings.LEX_DB_PATH).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=10000')
    try:
        db.executescript(SCHEMA)
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def one(db, sql, args=()):
    row = db.execute(sql, args).fetchone()
    return dict(row) if row else None


def rows(db, sql, args=()):
    return [dict(row) for row in db.execute(sql, args).fetchall()]


def revision(db, observation, action, actor, text):
    db.execute(
        'INSERT INTO observation_revisions '
        '(observation_id,action,actor,text,at,before_asset_id,after_asset_id) '
        'VALUES (?,?,?,?,?,?,?)',
        (observation['id'], action, actor, text, timestamp(),
         observation['before_asset_id'], observation['after_asset_id']),
    )
