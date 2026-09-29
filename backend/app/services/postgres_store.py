"""PostgreSQL adapter for the application's parameterized repository queries.

Schema initialization is explicit/versioned; no user SQL enters this adapter.
SQLite remains the local default. Use a dedicated empty database for migration.
"""
from contextlib import contextmanager
import re


def translate(sql: str) -> str:
    """Translate the small audited SQLite dialect used by repository functions."""
    if sql.strip().upper() == 'BEGIN IMMEDIATE':
        # Serialize review/edit read-modify-write transactions, preserving optimistic versions.
        return 'LOCK TABLE observations IN EXCLUSIVE MODE'
    ignore = bool(re.match(r'\s*INSERT OR IGNORE\b', sql, re.I))
    sql = re.sub(r'\bINSERT OR IGNORE\b', 'INSERT', sql, flags=re.I)
    sql = sql.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'BIGSERIAL PRIMARY KEY')
    # Leave SQL string literals alone; LIKE patterns retain literal percent signs.
    parts = re.split(r"('(?:''|[^'])*')", sql)
    for i, part in enumerate(parts):
        parts[i] = part.replace('%', '%%')
        if i % 2 == 0:
            parts[i] = parts[i].replace('?', '%s')
            parts[i] = re.sub(r'(?<!:):([A-Za-z_][A-Za-z_0-9]*)', r'%(\1)s', parts[i])
    result = ''.join(parts)
    if ignore:
        result = result.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'
    return result


class Connection:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, args=()):
        return self.raw.execute(translate(sql), args)

    def executescript(self, sql):
        # Internal schema definitions contain no semicolons in literals.
        for statement in sql.split(';'):
            if statement.strip():
                self.execute(statement)

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()


@contextmanager
def connection(url: str):
    import psycopg
    from psycopg.rows import dict_row
    # Never log the connection string or raw connection exception.
    try:
        raw = psycopg.connect(url, row_factory=dict_row, connect_timeout=10)
    except psycopg.Error:
        raise RuntimeError('PostgreSQL connection unavailable') from None
    with raw:
        yield Connection(raw)


def migrate(url: str):
    """Initialize the first PostgreSQL schema; does not import local private data."""
    from app.services.evidence_store import SCHEMA, _POST_MIGRATION_INDEXES, timestamp
    from app.workflows.store import WORKFLOW_SCHEMA
    with connection(url) as db:
        db.execute('SELECT pg_advisory_xact_lock(739241)')
        db.execute('CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)')
        if not db.execute('SELECT version FROM schema_migrations WHERE version=1').fetchone():
            db.executescript(SCHEMA)
            db.executescript(WORKFLOW_SCHEMA)
            for statement in _POST_MIGRATION_INDEXES:
                db.execute(statement)
            db.execute('INSERT OR IGNORE INTO projects(id,name,description,created_at) VALUES(?,?,?,?)',
                       ('proj_default', 'Default Environmental Project', 'Workspace', timestamp()))
            db.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?)', (1, timestamp()))
        if not db.execute('SELECT version FROM schema_migrations WHERE version=2').fetchone():
            # Supabase's Data API must not bypass FastAPI reviewer authorization.
            # No public policies: anon/authenticated roles cannot read/write these tables.
            # The server uses the trusted owner connection, never a browser database key.
            names = re.findall(r'CREATE TABLE IF NOT EXISTS ([a-z_]+)', SCHEMA + WORKFLOW_SCHEMA)
            for name in [*names, 'schema_migrations']:
                db.execute('ALTER TABLE ' + name + ' ENABLE ROW LEVEL SECURITY')
            db.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?)', (2, timestamp()))
