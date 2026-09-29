"""Small persistent store for the reviewable cleanup demo."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
 id TEXT PRIMARY KEY, name TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
 metadata_json TEXT
);
CREATE TABLE IF NOT EXISTS sites (
 id TEXT PRIMARY KEY, name TEXT NOT NULL,
 location TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '',
 project_id TEXT REFERENCES projects(id),
 latitude REAL, longitude REAL,
 created_at TEXT,
 metadata_json TEXT
);
CREATE TABLE IF NOT EXISTS visits (
 id TEXT PRIMARY KEY, site_id TEXT NOT NULL REFERENCES sites(id),
 visited_on TEXT NOT NULL, label TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assets (
 asset_id TEXT PRIMARY KEY, visit_id TEXT NOT NULL REFERENCES visits(id),
 public_id TEXT NOT NULL, version INTEGER NOT NULL, secure_url TEXT NOT NULL,
 source TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL,
 format TEXT NOT NULL,
 permission_status TEXT NOT NULL DEFAULT 'granted',
 thumbnail_url TEXT,
 site_id TEXT REFERENCES sites(id),
 media_type TEXT NOT NULL DEFAULT 'image',
 processing_status TEXT NOT NULL DEFAULT 'ready',
 original_filename TEXT,
 duration REAL,
 preview_url TEXT,
 created_at TEXT,
 metadata_json TEXT,
 project_id TEXT REFERENCES projects(id),
 captured_at TEXT
);
CREATE TABLE IF NOT EXISTS observations (
 id TEXT PRIMARY KEY, site_id TEXT NOT NULL REFERENCES sites(id),
 before_asset_id TEXT NOT NULL REFERENCES assets(asset_id),
 after_asset_id TEXT NOT NULL REFERENCES assets(asset_id),
 ai_draft TEXT, working_text TEXT, approved_text TEXT,
 review_status TEXT NOT NULL CHECK(review_status IN ('pending','approved','rejected')),
 reliability_reason TEXT, reviewed_by TEXT, reviewed_at TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS observation_revisions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 observation_id TEXT NOT NULL REFERENCES observations(id),
 action TEXT NOT NULL, actor TEXT NOT NULL, text TEXT, at TEXT NOT NULL,
 before_asset_id TEXT NOT NULL, after_asset_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS measurements (
 id TEXT PRIMARY KEY, site_id TEXT NOT NULL REFERENCES sites(id),
 visit_id TEXT NOT NULL REFERENCES visits(id),
 label TEXT NOT NULL, quantity REAL NOT NULL CHECK(quantity > 0),
 unit TEXT NOT NULL CHECK(unit IN ('kg','bags','items')),
 source TEXT NOT NULL, recorded_by TEXT NOT NULL, recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS video_frames (
 frame_id TEXT PRIMARY KEY,
 asset_id TEXT NOT NULL REFERENCES assets(asset_id),
 frame_index INTEGER NOT NULL,
 timestamp_seconds REAL NOT NULL,
 frame_url TEXT NOT NULL,
 thumbnail_url TEXT,
 source_video_url TEXT NOT NULL,
 width INTEGER,
 height INTEGER,
 extraction_method TEXT NOT NULL DEFAULT 'cloudinary_offset_transform',
 created_at TEXT NOT NULL,
 metadata_json TEXT
);
CREATE TABLE IF NOT EXISTS frame_analyses (
 analysis_id TEXT PRIMARY KEY,
 asset_id TEXT NOT NULL REFERENCES assets(asset_id),
 frame_id TEXT NOT NULL REFERENCES video_frames(frame_id),
 skill_name TEXT NOT NULL,
 skill_version TEXT NOT NULL,
 status TEXT NOT NULL,
 observations_json TEXT,
 detected_signals_json TEXT,
 confidence REAL,
 warnings_json TEXT,
 latency_ms REAL,
 created_at TEXT NOT NULL,
 raw_result_json TEXT
);
CREATE TABLE IF NOT EXISTS media_intelligence (
 id TEXT PRIMARY KEY,
 asset_id TEXT NOT NULL REFERENCES assets(asset_id),
 frame_id TEXT REFERENCES video_frames(frame_id),
 status TEXT NOT NULL DEFAULT 'pending',
 description TEXT,
 observations TEXT,
 tags_json TEXT,
 signals_json TEXT,
 activity TEXT,
 warnings_json TEXT,
 uncertainty TEXT,
 evidence_json TEXT,
 model_provider TEXT,
 model_name TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS impact_stories (
 id TEXT PRIMARY KEY,
 project_id TEXT NOT NULL REFERENCES projects(id),
 title TEXT NOT NULL,
 description TEXT,
 status TEXT NOT NULL DEFAULT 'draft',
 summary_narrative TEXT,
 uncertainty_note TEXT,
 share_token TEXT UNIQUE,
 metadata_json TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS impact_story_events (
 id TEXT PRIMARY KEY,
 story_id TEXT NOT NULL REFERENCES impact_stories(id),
 event_order INTEGER NOT NULL DEFAULT 0,
 timestamp_date TEXT NOT NULL,
 event_type TEXT NOT NULL,
 title TEXT NOT NULL,
 description TEXT,
 site_id TEXT REFERENCES sites(id),
 site_name TEXT,
 asset_ids_json TEXT,
 primary_media_url TEXT,
 thumbnail_url TEXT,
 media_type TEXT,
 frame_id TEXT,
 observation_id TEXT REFERENCES observations(id),
 measurement_id TEXT REFERENCES measurements(id),
 intelligence_id TEXT REFERENCES media_intelligence(id),
 verification_status TEXT NOT NULL DEFAULT 'unverified',
 tags_json TEXT,
 signals_json TEXT,
 warnings_json TEXT,
 uncertainty TEXT,
 evidence_json TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS semantic_documents (
 doc_key TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 site_id TEXT, kind TEXT NOT NULL, entity_id TEXT NOT NULL,
 content TEXT NOT NULL, content_hash TEXT NOT NULL, model TEXT NOT NULL,
 embedding_json TEXT NOT NULL, evidence_json TEXT NOT NULL,
 review_status TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS campaign_drafts (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 channel TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
 sources_json TEXT NOT NULL, source_fingerprint TEXT NOT NULL,
 demo_only INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
 edited_at TEXT
);
"""

# All indexes are applied post-migration to guarantee columns exist
_POST_MIGRATION_INDEXES = [
    # T011 indexes (permission_status, media_type columns are added by migration on legacy DBs)
    'CREATE INDEX IF NOT EXISTS idx_assets_created_at ON assets(created_at)',
    'CREATE INDEX IF NOT EXISTS idx_assets_media_type ON assets(media_type)',
    'CREATE INDEX IF NOT EXISTS idx_assets_permission ON assets(permission_status)',
    # T015 indexes
    'CREATE INDEX IF NOT EXISTS idx_assets_project_site ON assets(project_id, site_id)',
    'CREATE INDEX IF NOT EXISTS idx_assets_captured_at ON assets(captured_at)',
    'CREATE INDEX IF NOT EXISTS idx_sites_project_id ON sites(project_id)',
    # T016 indexes
    'CREATE INDEX IF NOT EXISTS idx_media_intel_asset ON media_intelligence(asset_id)',
    'CREATE INDEX IF NOT EXISTS idx_media_intel_status ON media_intelligence(status)',
    'CREATE INDEX IF NOT EXISTS idx_media_intel_frame ON media_intelligence(frame_id)',
    # T017 indexes
    'CREATE INDEX IF NOT EXISTS idx_impact_stories_project ON impact_stories(project_id)',
    'CREATE INDEX IF NOT EXISTS idx_impact_story_events_story ON impact_story_events(story_id, event_order)',
    'CREATE INDEX IF NOT EXISTS idx_impact_story_events_type ON impact_story_events(event_type)',
    # T018 indexes
    'CREATE UNIQUE INDEX IF NOT EXISTS idx_impact_stories_share_token ON impact_stories(share_token)',
    'CREATE INDEX IF NOT EXISTS idx_semantic_documents_project ON semantic_documents(project_id)',
    'CREATE INDEX IF NOT EXISTS idx_campaign_drafts_project ON campaign_drafts(project_id, created_at)',
]



def timestamp():
    return datetime.now(timezone.utc).isoformat()


def new_id():
    return uuid4().hex


@contextmanager
def connection():
    raw_path = Path(settings.LEX_DB_PATH).expanduser()
    if not raw_path.is_absolute():
        backend_dir = Path(__file__).resolve().parents[2]
        path = (backend_dir / raw_path).resolve()
    else:
        path = raw_path
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=10000')
    try:
        db.executescript(SCHEMA)
        # Existing local demo databases predate optimistic review versions.
        columns = {row['name'] for row in db.execute('PRAGMA table_info(observations)')}
        if 'version' not in columns:
            db.execute('ALTER TABLE observations ADD COLUMN version INTEGER NOT NULL DEFAULT 1')
        site_columns = {row['name'] for row in db.execute('PRAGMA table_info(sites)')}
        if 'location' not in site_columns:
            db.execute("ALTER TABLE sites ADD COLUMN location TEXT NOT NULL DEFAULT ''")
        if 'description' not in site_columns:
            db.execute("ALTER TABLE sites ADD COLUMN description TEXT NOT NULL DEFAULT ''")
        if 'project_id' not in site_columns:
            db.execute("ALTER TABLE sites ADD COLUMN project_id TEXT REFERENCES projects(id)")
        if 'latitude' not in site_columns:
            db.execute("ALTER TABLE sites ADD COLUMN latitude REAL")
        if 'longitude' not in site_columns:
            db.execute("ALTER TABLE sites ADD COLUMN longitude REAL")
        if 'created_at' not in site_columns:
            db.execute("ALTER TABLE sites ADD COLUMN created_at TEXT")
        if 'metadata_json' not in site_columns:
            db.execute("ALTER TABLE sites ADD COLUMN metadata_json TEXT")

        # Migrate assets table for permission_status and thumbnail_url
        asset_columns = {row['name'] for row in db.execute('PRAGMA table_info(assets)')}
        if 'permission_status' not in asset_columns:
            db.execute("ALTER TABLE assets ADD COLUMN permission_status TEXT NOT NULL DEFAULT 'granted'")
        if 'thumbnail_url' not in asset_columns:
            db.execute("ALTER TABLE assets ADD COLUMN thumbnail_url TEXT")
        # Migrate assets table for T011 media pipeline fields
        if 'site_id' not in asset_columns:
            db.execute("ALTER TABLE assets ADD COLUMN site_id TEXT REFERENCES sites(id)")
        if 'media_type' not in asset_columns:
            db.execute("ALTER TABLE assets ADD COLUMN media_type TEXT NOT NULL DEFAULT 'image'")
        if 'processing_status' not in asset_columns:
            db.execute("ALTER TABLE assets ADD COLUMN processing_status TEXT NOT NULL DEFAULT 'ready'")
        if 'original_filename' not in asset_columns:
            db.execute("ALTER TABLE assets ADD COLUMN original_filename TEXT")
        if 'duration' not in asset_columns:
            db.execute("ALTER TABLE assets ADD COLUMN duration REAL")
        if 'preview_url' not in asset_columns:
            db.execute("ALTER TABLE assets ADD COLUMN preview_url TEXT")
        if 'created_at' not in asset_columns:
            db.execute("ALTER TABLE assets ADD COLUMN created_at TEXT")
        if 'metadata_json' not in asset_columns:
            db.execute("ALTER TABLE assets ADD COLUMN metadata_json TEXT")
        if 'project_id' not in asset_columns:
            db.execute("ALTER TABLE assets ADD COLUMN project_id TEXT REFERENCES projects(id)")
        if 'captured_at' not in asset_columns:
            db.execute("ALTER TABLE assets ADD COLUMN captured_at TEXT")

        # Migrate impact_stories table for T018 share_token
        story_columns = {row['name'] for row in db.execute('PRAGMA table_info(impact_stories)')}
        if 'share_token' not in story_columns:
            db.execute("ALTER TABLE impact_stories ADD COLUMN share_token TEXT")

        campaign_columns = {row['name'] for row in db.execute('PRAGMA table_info(campaign_drafts)')}
        if 'edited_at' not in campaign_columns:
            db.execute("ALTER TABLE campaign_drafts ADD COLUMN edited_at TEXT")

        # All indexes applied after migration so columns are guaranteed to exist
        for idx_sql in _POST_MIGRATION_INDEXES:
            try:
                db.execute(idx_sql)
            except Exception:
                pass  # Index may already exist or column may not be present on very old DBs

        now_ts = timestamp()
        default_proj = db.execute("SELECT id FROM projects WHERE id='proj_default'").fetchone()
        if not default_proj:
            db.execute(
                "INSERT OR IGNORE INTO projects (id, name, description, created_at) VALUES (?, ?, ?, ?)",
                ('proj_default', 'Default Environmental Project', 'Default workspace project for field cleanup sites', now_ts)
            )

        # Backfill site_id for any existing assets tied to visits
        db.execute("UPDATE assets SET site_id = (SELECT site_id FROM visits WHERE visits.id = assets.visit_id) WHERE site_id IS NULL AND visit_id IS NOT NULL")
        # Backfill sites without project_id
        db.execute("UPDATE sites SET project_id = 'proj_default' WHERE project_id IS NULL OR project_id = ''")
        db.execute("UPDATE sites SET created_at = ? WHERE created_at IS NULL", (now_ts,))
        # Backfill assets without project_id
        db.execute("UPDATE assets SET project_id = (SELECT project_id FROM sites WHERE sites.id = assets.site_id) WHERE project_id IS NULL AND site_id IS NOT NULL")
        db.execute("UPDATE assets SET project_id = (SELECT s.project_id FROM visits v JOIN sites s ON s.id = v.site_id WHERE v.id = assets.visit_id) WHERE project_id IS NULL AND visit_id IS NOT NULL")
        db.execute("UPDATE assets SET project_id = 'proj_default' WHERE project_id IS NULL")

        # Create indexes
        db.execute("CREATE INDEX IF NOT EXISTS idx_assets_project_site ON assets(project_id, site_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_assets_created_at ON assets(created_at)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_assets_captured_at ON assets(captured_at)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_assets_media_type ON assets(media_type)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_assets_permission ON assets(permission_status)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_sites_project_id ON sites(project_id)")

        # Migrate any legacy 'unreliable' review status to 'pending'
        db.execute("UPDATE observations SET review_status = 'pending' WHERE review_status = 'unreliable'")
        db.commit()
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


def ensure_ingestion_visit(db, site_id: str, visit_date: str) -> str:
    """Ensure site exists and return an existing or newly created visit ID for this site and date."""
    site = one(db, 'SELECT id FROM sites WHERE id=?', (site_id,))
    if not site:
        now_ts = timestamp()
        db.execute(
            'INSERT INTO sites (id, name, location, description, project_id, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            (site_id, site_id.replace('-', ' ').title(), '', 'Collection project', 'proj_default', now_ts)
        )
    visit = one(db, 'SELECT id FROM visits WHERE site_id=? AND visited_on=? ORDER BY id LIMIT 1', (site_id, visit_date))
    if visit:
        return visit['id']
    v_id = new_id()
    db.execute(
        'INSERT INTO visits (id, site_id, visited_on, label) VALUES (?, ?, ?, ?)',
        (v_id, site_id, visit_date, f'Collection — {visit_date}')
    )
    return v_id


def save_asset(db, asset_data: dict) -> dict:
    """Persist an asset record to the assets table."""
    now = timestamp()
    # Resolve project_id if not present
    project_id = asset_data.get('project_id')
    if not project_id:
        if asset_data.get('site_id'):
            s = one(db, 'SELECT project_id FROM sites WHERE id=?', (asset_data['site_id'],))
            if s and s.get('project_id'):
                project_id = s['project_id']
        if not project_id and asset_data.get('visit_id'):
            v = one(db, 'SELECT s.project_id FROM visits v JOIN sites s ON s.id = v.site_id WHERE v.id=?', (asset_data['visit_id'],))
            if v and v.get('project_id'):
                project_id = v['project_id']
    if not project_id:
        project_id = 'proj_default'
    asset_data['project_id'] = project_id

    db.execute(
        """INSERT OR IGNORE INTO assets (
            asset_id, visit_id, public_id, version, secure_url, source,
            width, height, format, permission_status, thumbnail_url,
            site_id, media_type, processing_status, original_filename,
            duration, preview_url, created_at, metadata_json,
            project_id, captured_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            asset_data['asset_id'],
            asset_data['visit_id'],
            asset_data['public_id'],
            asset_data['version'],
            asset_data['secure_url'],
            asset_data['source'],
            asset_data['width'],
            asset_data['height'],
            asset_data['format'],
            asset_data.get('permission_status', 'granted'),
            asset_data.get('thumbnail_url'),
            asset_data.get('site_id'),
            asset_data.get('media_type', 'image'),
            asset_data.get('processing_status', 'ready'),
            asset_data.get('original_filename'),
            asset_data.get('duration'),
            asset_data.get('preview_url'),
            asset_data.get('created_at') or now,
            asset_data.get('metadata_json'),
            project_id,
            asset_data.get('captured_at'),
        )
    )
    return asset_data


def get_media_item(db, asset_id: str) -> dict | None:
    """Retrieve full media asset record by asset_id."""
    return one(db, 'SELECT * FROM assets WHERE asset_id=?', (asset_id,))


get_asset = get_media_item



def list_media(db, project_id: str | None = None, site_id: str | None = None, media_type: str | None = None,
               permission_status: str | None = None, tag: str | None = None,
               signal: str | None = None, ai_status: str | None = None,
               limit: int = 50, offset: int = 0) -> list[dict]:
    """Query assets with optional filters."""
    query = 'SELECT * FROM assets WHERE 1=1'
    params = []
    if project_id:
        query += ' AND project_id=?'
        params.append(project_id)
    if site_id:
        query += ' AND (site_id=? OR visit_id IN (SELECT id FROM visits WHERE site_id=?))'
        params.extend([site_id, site_id])
    if media_type:
        query += ' AND media_type=?'
        params.append(media_type.lower())
    if permission_status:
        query += ' AND permission_status=?'
        params.append(permission_status.lower())
    if tag:
        clean_tag = tag.strip().lower().replace("-", "_").replace(" ", "_")
        query += ' AND asset_id IN (SELECT asset_id FROM media_intelligence WHERE tags_json LIKE ?)'
        params.append(f'%"{clean_tag}"%')
    if signal:
        clean_signal = signal.strip().lower().replace("-", "_").replace(" ", "_")
        query += ' AND asset_id IN (SELECT asset_id FROM media_intelligence WHERE signals_json LIKE ?)'
        params.append(f'%"{clean_signal}"%')
    if ai_status:
        query += ' AND asset_id IN (SELECT asset_id FROM media_intelligence WHERE status=?)'
        params.append(ai_status.strip().lower())
    query += ' ORDER BY created_at DESC, asset_id DESC LIMIT ? OFFSET ?'
    params.extend([limit, offset])
    return rows(db, query, tuple(params))



def create_project(db, project_data: dict) -> dict:
    """Create a new project record."""
    now = timestamp()
    created_at = project_data.get('created_at') or now
    db.execute(
        'INSERT INTO projects (id, name, description, created_at, metadata_json) VALUES (?, ?, ?, ?, ?)',
        (
            project_data['id'],
            project_data['name'],
            project_data.get('description', ''),
            created_at,
            project_data.get('metadata_json'),
        )
    )
    return {
        'id': project_data['id'],
        'name': project_data['name'],
        'description': project_data.get('description', ''),
        'created_at': created_at,
        'metadata_json': project_data.get('metadata_json'),
    }


def get_project(db, project_id: str) -> dict | None:
    """Retrieve project record by ID."""
    return one(db, 'SELECT * FROM projects WHERE id=?', (project_id,))


def list_projects(db) -> list[dict]:
    """Retrieve all projects ordered by name, id."""
    return rows(db, 'SELECT * FROM projects ORDER BY name, id')


def get_site(db, site_id: str) -> dict | None:
    """Retrieve site record by ID."""
    return one(db, 'SELECT * FROM sites WHERE id=?', (site_id,))


def save_video_frame(db, frame_data: dict) -> dict:
    """Insert or update a video frame record."""
    now = timestamp()
    db.execute(
        '''
        INSERT INTO video_frames (
            frame_id, asset_id, frame_index, timestamp_seconds,
            frame_url, thumbnail_url, source_video_url,
            width, height, extraction_method, created_at, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(frame_id) DO UPDATE SET
            timestamp_seconds=excluded.timestamp_seconds,
            frame_url=excluded.frame_url,
            thumbnail_url=excluded.thumbnail_url,
            width=excluded.width,
            height=excluded.height,
            metadata_json=excluded.metadata_json
        ''',
        (
            frame_data['frame_id'],
            frame_data['asset_id'],
            frame_data['frame_index'],
            float(frame_data['timestamp_seconds']),
            frame_data['frame_url'],
            frame_data.get('thumbnail_url'),
            frame_data['source_video_url'],
            frame_data.get('width'),
            frame_data.get('height'),
            frame_data.get('extraction_method', 'cloudinary_offset_transform'),
            frame_data.get('created_at') or now,
            frame_data.get('metadata_json'),
        )
    )
    return frame_data


def get_video_frames_by_asset(db, asset_id: str) -> list[dict]:
    """Retrieve all extracted frames for a video asset ordered by timestamp."""
    return rows(db, 'SELECT * FROM video_frames WHERE asset_id=? ORDER BY timestamp_seconds ASC, frame_index ASC', (asset_id,))


def get_video_frame(db, frame_id: str) -> dict | None:
    """Retrieve a single video frame by frame_id."""
    return one(db, 'SELECT * FROM video_frames WHERE frame_id=?', (frame_id,))


def delete_video_frames_by_asset(db, asset_id: str) -> int:
    """Delete all extracted frames for an asset."""
    cursor = db.execute('DELETE FROM video_frames WHERE asset_id=?', (asset_id,))
    return cursor.rowcount


def save_frame_analysis(db, analysis_data: dict) -> dict:
    """Insert or update a frame analysis result."""
    now = timestamp()
    db.execute(
        '''
        INSERT INTO frame_analyses (
            analysis_id, asset_id, frame_id, skill_name, skill_version,
            status, observations_json, detected_signals_json, confidence,
            warnings_json, latency_ms, created_at, raw_result_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(analysis_id) DO UPDATE SET
            status=excluded.status,
            observations_json=excluded.observations_json,
            detected_signals_json=excluded.detected_signals_json,
            confidence=excluded.confidence,
            warnings_json=excluded.warnings_json,
            latency_ms=excluded.latency_ms,
            raw_result_json=excluded.raw_result_json
        ''',
        (
            analysis_data['analysis_id'],
            analysis_data['asset_id'],
            analysis_data['frame_id'],
            analysis_data['skill_name'],
            analysis_data['skill_version'],
            analysis_data['status'],
            analysis_data.get('observations_json'),
            analysis_data.get('detected_signals_json'),
            analysis_data.get('confidence'),
            analysis_data.get('warnings_json'),
            analysis_data.get('latency_ms', 0.0),
            analysis_data.get('created_at') or now,
            analysis_data.get('raw_result_json'),
        )
    )
    return analysis_data


def get_frame_analyses_by_asset(db, asset_id: str) -> list[dict]:
    """Retrieve all frame analyses for a video asset ordered by created_at DESC."""
    return rows(db, 'SELECT * FROM frame_analyses WHERE asset_id=? ORDER BY created_at DESC', (asset_id,))


def get_frame_analysis_by_frame(db, frame_id: str) -> dict | None:
    """Retrieve the latest frame analysis for a specific frame."""
    return one(db, 'SELECT * FROM frame_analyses WHERE frame_id=? ORDER BY created_at DESC LIMIT 1', (frame_id,))


def save_media_intelligence(db, data: dict) -> dict:
    """Insert or update a media intelligence record."""
    now = timestamp()
    record_id = data.get('id') or new_id()
    created_at = data.get('created_at') or now
    updated_at = data.get('updated_at') or now

    db.execute(
        '''
        INSERT INTO media_intelligence (
            id, asset_id, frame_id, status, description, observations,
            tags_json, signals_json, activity, warnings_json, uncertainty,
            evidence_json, model_provider, model_name, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            status=excluded.status,
            description=excluded.description,
            observations=excluded.observations,
            tags_json=excluded.tags_json,
            signals_json=excluded.signals_json,
            activity=excluded.activity,
            warnings_json=excluded.warnings_json,
            uncertainty=excluded.uncertainty,
            evidence_json=excluded.evidence_json,
            model_provider=excluded.model_provider,
            model_name=excluded.model_name,
            updated_at=excluded.updated_at
        ''',
        (
            record_id,
            data['asset_id'],
            data.get('frame_id'),
            data.get('status', 'pending'),
            data.get('description'),
            data.get('observations'),
            data.get('tags_json'),
            data.get('signals_json'),
            data.get('activity'),
            data.get('warnings_json'),
            data.get('uncertainty'),
            data.get('evidence_json'),
            data.get('model_provider'),
            data.get('model_name'),
            created_at,
            updated_at,
        )
    )
    data['id'] = record_id
    data['created_at'] = created_at
    data['updated_at'] = updated_at
    return data


def get_media_intelligence(db, asset_id: str, frame_id: str | None = None) -> dict | None:
    """Retrieve the latest media intelligence record for an asset (and optional frame)."""
    if frame_id is not None:
        return one(
            db,
            'SELECT * FROM media_intelligence WHERE asset_id=? AND frame_id=? ORDER BY created_at DESC LIMIT 1',
            (asset_id, frame_id)
        )
    else:
        return one(
            db,
            'SELECT * FROM media_intelligence WHERE asset_id=? AND frame_id IS NULL ORDER BY created_at DESC LIMIT 1',
            (asset_id,)
        )


def get_media_intelligence_history(db, asset_id: str, frame_id: str | None = None) -> list[dict]:
    """Retrieve full intelligence revision history for an asset (and optional frame)."""
    if frame_id is not None:
        return rows(
            db,
            'SELECT * FROM media_intelligence WHERE asset_id=? AND frame_id=? ORDER BY created_at DESC',
            (asset_id, frame_id)
        )
    else:
        return rows(
            db,
            'SELECT * FROM media_intelligence WHERE asset_id=? AND frame_id IS NULL ORDER BY created_at DESC',
            (asset_id,)
        )


def save_impact_story(db, data: dict) -> dict:
    """Insert or update an impact story record."""
    now = timestamp()
    story_id = data.get('id') or f"story_{data['project_id']}"
    created_at = data.get('created_at') or now
    updated_at = now
    db.execute(
        '''
        INSERT INTO impact_stories (
            id, project_id, title, description, status,
            summary_narrative, uncertainty_note, share_token, metadata_json,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            description=excluded.description,
            status=excluded.status,
            summary_narrative=excluded.summary_narrative,
            uncertainty_note=excluded.uncertainty_note,
            share_token=COALESCE(excluded.share_token, impact_stories.share_token),
            metadata_json=excluded.metadata_json,
            updated_at=excluded.updated_at
        ''',
        (
            story_id,
            data['project_id'],
            data['title'],
            data.get('description'),
            data.get('status', 'draft'),
            data.get('summary_narrative'),
            data.get('uncertainty_note'),
            data.get('share_token'),
            data.get('metadata_json'),
            created_at,
            updated_at,
        )
    )
    data['id'] = story_id
    data['created_at'] = created_at
    data['updated_at'] = updated_at
    return get_impact_story(db, story_id)


def get_impact_story(db, story_id: str) -> dict | None:
    """Retrieve impact story by ID."""
    return one(db, 'SELECT * FROM impact_stories WHERE id=?', (story_id,))


def get_project_impact_story(db, project_id: str) -> dict | None:
    """Retrieve the latest impact story for a project."""
    return one(db, 'SELECT * FROM impact_stories WHERE project_id=? ORDER BY updated_at DESC LIMIT 1', (project_id,))


def get_impact_story_by_share_token(db, share_token: str) -> dict | None:
    """Retrieve an impact story by its public share token."""
    if not share_token:
        return None
    return one(db, 'SELECT * FROM impact_stories WHERE share_token=?', (share_token,))


def set_impact_story_share_token(db, story_id: str, share_token: str | None) -> dict | None:
    """Update or revoke the public share token for an impact story."""
    db.execute(
        'UPDATE impact_stories SET share_token=?, updated_at=? WHERE id=?',
        (share_token, timestamp(), story_id)
    )
    return get_impact_story(db, story_id)


def update_impact_story(db, story_id: str, updates: dict) -> dict | None:
    """Update fields on an existing impact story."""
    existing = get_impact_story(db, story_id)
    if not existing:
        return None
    allowed = {'title', 'description', 'status', 'summary_narrative', 'uncertainty_note', 'metadata_json', 'share_token'}
    fields = []
    values = []
    for k, v in updates.items():
        if k in allowed:
            fields.append(f"{k}=?")
            values.append(v)
    if not fields:
        return existing
    fields.append("updated_at=?")
    values.append(timestamp())
    values.append(story_id)
    sql = f"UPDATE impact_stories SET {', '.join(fields)} WHERE id=?"
    db.execute(sql, tuple(values))
    return get_impact_story(db, story_id)


def delete_impact_story_events(db, story_id: str):
    """Delete all timeline events for a story."""
    db.execute('DELETE FROM impact_story_events WHERE story_id=?', (story_id,))


def save_impact_story_events(db, story_id: str, events: list[dict]) -> list[dict]:
    """Replace all timeline events for a story atomically."""
    delete_impact_story_events(db, story_id)
    now = timestamp()
    saved = []
    for idx, evt in enumerate(events):
        evt_id = evt.get('id') or f"evt_{uuid4().hex[:12]}"
        created_at = evt.get('created_at') or now
        updated_at = now
        db.execute(
            '''
            INSERT INTO impact_story_events (
                id, story_id, event_order, timestamp_date, event_type,
                title, description, site_id, site_name, asset_ids_json,
                primary_media_url, thumbnail_url, media_type, frame_id,
                observation_id, measurement_id, intelligence_id,
                verification_status, tags_json, signals_json, warnings_json,
                uncertainty, evidence_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                evt_id,
                story_id,
                evt.get('event_order', idx),
                evt['timestamp_date'],
                evt['event_type'],
                evt['title'],
                evt.get('description'),
                evt.get('site_id'),
                evt.get('site_name'),
                evt.get('asset_ids_json'),
                evt.get('primary_media_url'),
                evt.get('thumbnail_url'),
                evt.get('media_type'),
                evt.get('frame_id'),
                evt.get('observation_id'),
                evt.get('measurement_id'),
                evt.get('intelligence_id'),
                evt.get('verification_status', 'unverified'),
                evt.get('tags_json'),
                evt.get('signals_json'),
                evt.get('warnings_json'),
                evt.get('uncertainty'),
                evt.get('evidence_json'),
                created_at,
                updated_at,
            )
        )
        evt['id'] = evt_id
        evt['story_id'] = story_id
        evt['event_order'] = evt.get('event_order', idx)
        evt['created_at'] = created_at
        evt['updated_at'] = updated_at
        saved.append(evt)
    return saved


def get_impact_story_events(db, story_id: str) -> list[dict]:
    """Retrieve chronological events for an impact story."""
    return rows(
        db,
        'SELECT * FROM impact_story_events WHERE story_id=? ORDER BY event_order ASC, timestamp_date ASC',
        (story_id,)
    )
