"""Consistent SQLite backup plus restore verification; never overwrites source data."""
import argparse
from pathlib import Path
import sqlite3
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path)
parser.add_argument('destination', type=Path)
args = parser.parse_args()
if not args.source.is_file() or args.destination.exists():
    raise SystemExit('Source must exist and destination must be new')
args.destination.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(args.source.resolve().as_uri() + '?mode=ro', uri=True) as src:
    with sqlite3.connect(args.destination) as backup:
        src.backup(backup)
        if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise SystemExit('Backup integrity check failed')
    with tempfile.TemporaryDirectory() as directory:
        with sqlite3.connect(args.destination) as backup, sqlite3.connect(Path(directory) / 'restore.sqlite3') as restored:
            backup.backup(restored)
            assert restored.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            tables = [r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            for table in tables:
                quoted = '"' + table.replace('"', '""') + '"'
                assert src.execute('SELECT COUNT(*) FROM ' + quoted).fetchone() == restored.execute('SELECT COUNT(*) FROM ' + quoted).fetchone()
print('Backup and disposable restore verified; source database unchanged.')
