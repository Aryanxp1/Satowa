"""Opt-in disposable-schema PostgreSQL integration; never touches pilot records."""
import os
import uuid

import pytest
from pydantic import SecretStr

from app.config import settings
from app.services import evidence_store as store
from app.services.postgres_store import migrate


@pytest.mark.skipif(not os.environ.get('SETOWA_POSTGRES_TEST_URL'), reason='Opt-in PostgreSQL connection not supplied')
def test_postgres_migration_named_parameters_and_persistence(monkeypatch):
    import psycopg
    from psycopg.conninfo import make_conninfo
    from psycopg import sql
    base = os.environ['SETOWA_POSTGRES_TEST_URL']
    schema = 'setowa_test_' + uuid.uuid4().hex
    with psycopg.connect(base, autocommit=True) as control:
        control.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    scoped = make_conninfo(base, options='-c search_path=' + schema)
    try:
        migrate(scoped)
        migrate(scoped)  # idempotence
        monkeypatch.setattr(settings, 'DATABASE_URL', SecretStr(scoped))
        with store.connection() as db:
            db.execute('INSERT INTO sites(id,name,project_id) VALUES(?,?,?)', ('test-site', 'Synthetic test', 'proj_default'))
            db.execute('INSERT INTO visits(id,site_id,visited_on,label) VALUES(:id,:site,:day,:label)',
                       {'id': 'test-visit', 'site': 'test-site', 'day': '2026-09-01', 'label': 'Synthetic'})
        with store.connection() as db:
            assert store.one(db, 'SELECT label FROM visits WHERE id=?', ('test-visit',))['label'] == 'Synthetic'
            db.execute('BEGIN IMMEDIATE')
            assert store.one(db, 'SELECT COUNT(*) AS n FROM schema_migrations')['n'] == 1
        with pytest.raises(RuntimeError, match='rollback-check'):
            with store.connection() as db:
                db.execute('DELETE FROM visits WHERE id=?', ('test-visit',))
                raise RuntimeError('rollback-check')
        with store.connection() as db:
            assert store.one(db, 'SELECT id FROM visits WHERE id=?', ('test-visit',))
        from fastapi.testclient import TestClient
        from app.main import app
        monkeypatch.setattr(settings, 'ENVIRONMENT', 'test')
        monkeypatch.setattr(settings, 'AI_PROVIDER', 'nvidia')
        monkeypatch.setattr(settings, 'REVIEWER_TOKENS', SecretStr('{"Tester":"postgres-test-reviewer"}'))
        monkeypatch.setattr(settings, 'MEDIA_UPLOAD_TOKEN', SecretStr(''))
        client = TestClient(app)
        headers = {'Authorization': 'Bearer postgres-test-reviewer'}
        visit = client.post('/api/v1/sites/test-site/visits', headers=headers,
                            json={'visited_on': '2026-09-02', 'label': 'Synthetic after'})
        assert visit.status_code == 201
        with store.connection() as db:
            for asset_id, visit_id in [('before', 'test-visit'), ('after', visit.json()['id'])]:
                store.save_asset(db, {'asset_id': asset_id, 'visit_id': visit_id,
                    'public_id': 'synthetic/' + asset_id, 'version': 1,
                    'secure_url': '/demo/sample-media/river-' + asset_id + '-synthetic.png',
                    'source': 'Synthetic test only', 'width': 10, 'height': 10,
                    'format': 'png', 'permission_status': 'granted', 'site_id': 'test-site'})
        pair = client.post('/api/v1/pairs', headers=headers,
                           json={'before_asset_id': 'before', 'after_asset_id': 'after'})
        assert pair.status_code == 201
        observation = pair.json()
        approved = client.post('/api/v1/observations/' + observation['id'] + '/review', headers=headers,
            json={'decision': 'approve', 'expected_version': observation['version'],
                  'text': 'Synthetic demonstration: less visible litter.'})
        assert approved.status_code == 200
        report = client.get('/api/v1/sites/test-site/report', headers=headers)
        assert report.status_code == 200
        assert 'Synthetic demonstration' in report.text
        campaign = client.post('/api/v1/projects/proj_default/campaign-drafts', headers=headers, json={'channel': 'social'})
        assert campaign.status_code == 201
        assert campaign.json()['demo_only'] is True
        with store.connection() as db:
            db.execute("UPDATE assets SET permission_status='revoked' WHERE asset_id='before'")
        drafts = client.get('/api/v1/projects/proj_default/campaign-drafts', headers=headers)
        assert drafts.json()[0]['stale'] is True
        assert drafts.json()[0]['sources'] == []
    finally:
        with psycopg.connect(base, autocommit=True) as control:
            control.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
