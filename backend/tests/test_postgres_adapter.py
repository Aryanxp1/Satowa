from app.services.postgres_store import translate


def test_parameters_preserve_literals():
    assert translate("SELECT * FROM assets WHERE source LIKE '%?%' AND asset_id=?") == "SELECT * FROM assets WHERE source LIKE '%%?%%' AND asset_id=%s"


def test_conflict_and_lock_translation():
    assert translate('INSERT OR IGNORE INTO sites(id) VALUES(?)').endswith('VALUES(%s) ON CONFLICT DO NOTHING')
    assert translate('BEGIN IMMEDIATE') == 'LOCK TABLE observations IN EXCLUSIVE MODE'
    assert 'BIGSERIAL PRIMARY KEY' in translate('id INTEGER PRIMARY KEY AUTOINCREMENT')
