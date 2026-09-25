"""Local setup keeps provider secrets private and makes the sample usable."""
import json
import stat

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import settings
from app.main import app
from app.routes import local_setup
from app import config


def test_local_session_and_credential_update(tmp_path, monkeypatch):
    path = tmp_path / 'credential.json'
    monkeypatch.setattr(settings, 'ENVIRONMENT', 'test')
    monkeypatch.setattr(settings, 'LEX_DB_PATH', str(tmp_path / 'demo.sqlite3'))
    monkeypatch.setattr(settings, 'REVIEWER_TOKENS', SecretStr('{"Farhan":"test-reviewer-secret"}'))
    monkeypatch.setattr(settings, 'MEDIA_UPLOAD_TOKEN', SecretStr('different-upload-secret'))
    monkeypatch.setattr(settings, 'CLOUDINARY_CLOUD_NAME', '')
    monkeypatch.setattr(settings, 'CLOUDINARY_API_KEY', '')
    monkeypatch.setattr(settings, 'CLOUDINARY_API_SECRET', SecretStr(''))
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', '')
    monkeypatch.setattr(config, 'credential_path', lambda: path)
    monkeypatch.setattr(local_setup, 'credential_path', lambda: path)
    origin = {'Origin': 'http://testserver'}

    with TestClient(app) as client:
        assert client.get('/api/v1/sites').status_code == 401
        initial = client.get('/api/v1/local/status').json()
        assert initial['reviewer'] is None and not initial['cloudinary_ready']
        wrong_origin = client.post('/api/v1/local/session', headers={'Origin': 'http://evil.example'})
        assert wrong_origin.status_code == 403
        session = client.post('/api/v1/local/session', headers=origin)
        assert session.status_code == 200
        assert session.json() == {'reviewer': 'Farhan'}
        assert 'httponly' in session.headers['set-cookie'].lower()
        assert 'test-reviewer-secret' not in session.text + session.headers['set-cookie']
        assert client.get('/api/v1/sites').status_code == 200
        blocked = client.post('/api/v1/sites', json={'id': 'blocked', 'name': 'No origin'})
        assert blocked.status_code == 401
        site = client.post('/api/v1/sites', headers=origin,
                           json={'id': 'new-site', 'name': 'New site', 'location': 'Delhi',
                                 'description': 'Cleanup visit evidence'})
        assert site.status_code == 201
        edited = client.patch('/api/v1/sites/new-site', headers=origin,
                              json={'name': 'River bend', 'location': 'Delhi NCR',
                                    'description': 'Two dated visits'})
        assert edited.status_code == 200
        assert edited.json()['location'] == 'Delhi NCR'

        payload = {'cloudinary': {'cloud_name': 'example-cloud', 'api_key': 'api-key-secret',
                                  'api_secret': 'cloud-secret'},
                   'gemini': {'api_key': 'gemini-secret'}}
        bad = client.put('/api/v1/local/credentials', headers={'Origin': 'http://evil.example'}, json=payload)
        assert bad.status_code == 403 and not path.exists()
        saved = client.put('/api/v1/local/credentials', headers=origin, json=payload)
        assert saved.status_code == 200
        assert saved.json()['cloudinary_ready'] and saved.json()['gemini_ready']
        for secret in ('api-key-secret', 'cloud-secret', 'gemini-secret'):
            assert secret not in saved.text
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert json.loads(path.read_text()) == payload
        changed = client.put('/api/v1/local/credentials', headers=origin,
                             json={'cloudinary': {}, 'gemini': {'api_key': 'new-gemini-secret'}})
        assert changed.status_code == 200
        stored = json.loads(path.read_text())
        assert stored['cloudinary'] == payload['cloudinary']
        assert stored['gemini']['api_key'] == 'new-gemini-secret'
        logout = client.post('/api/v1/local/session/logout', headers=origin)
        assert logout.status_code == 200
        assert client.get('/api/v1/sites').status_code == 401
