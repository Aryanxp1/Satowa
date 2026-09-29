"""Remote pilot must not expose older API routes outside the reviewer gate."""

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import settings
from app.main import app


def test_remote_pilot_gates_entire_api_and_uses_named_reviewer(monkeypatch):
    monkeypatch.setattr(settings, 'ENVIRONMENT', 'pilot')
    token = 'pilot-test-token-with-at-least-32-characters'
    monkeypatch.setattr(settings, 'REVIEWER_TOKENS', SecretStr('{"Farhan":"' + token + '"}'))
    client = TestClient(app)
    assert client.get('/api/v1/health').status_code == 200
    for path in ('/api/v1/projects', '/api/v1/skills', '/api/v1/workflows',
                 '/api/v1/pilot/session'):
        assert client.get(path).status_code == 401
    headers = {'Authorization': 'Bearer ' + token}
    session = client.get('/api/v1/pilot/session', headers=headers)
    assert session.status_code == 200
    assert session.json()['reviewer'] == 'Farhan'
    assert token not in session.text
    assert client.get('/api/v1/projects', headers=headers).status_code == 200
    assert client.get('/api/v1/local/status', headers=headers).status_code == 403


def test_pilot_readiness_reports_missing_and_malformed_auth_without_secrets(monkeypatch):
    monkeypatch.setattr(settings, 'ENVIRONMENT', 'pilot')
    monkeypatch.setattr(settings, 'REVIEWER_TOKENS', SecretStr(''))
    client = TestClient(app)
    assert client.get('/api/v1/health').status_code == 200
    missing = client.get('/api/v1/ready')
    assert missing.status_code == 503
    assert missing.json()['reviewer_auth'] == 'missing'
    assert missing.json()['status'] == 'degraded'
    monkeypatch.setattr(settings, 'REVIEWER_TOKENS', SecretStr('{broken-secret-json'))
    malformed = client.get('/api/v1/ready')
    assert malformed.status_code == 503
    assert malformed.json()['reviewer_auth'] == 'misconfigured'
    assert 'broken-secret-json' not in malformed.text


def test_pilot_readiness_reports_configured_services_without_values(monkeypatch):
    monkeypatch.setattr(settings, 'ENVIRONMENT', 'pilot')
    monkeypatch.setattr(settings, 'USE_MOCK', False)
    monkeypatch.setattr(settings, 'REVIEWER_TOKENS', SecretStr('{"Farhan":"a-long-random-demo-token-with-32-chars"}'))
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', 'gemini-test-secret')
    monkeypatch.setattr(settings, 'CLOUDINARY_CLOUD_NAME', 'test-cloud')
    monkeypatch.setattr(settings, 'CLOUDINARY_API_KEY', 'cloudinary-test-secret')
    monkeypatch.setattr(settings, 'CLOUDINARY_API_SECRET', SecretStr('cloudinary-secret'))
    response = TestClient(app).get('/api/v1/ready')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.json()['status'] == 'ready'
    assert response.json()['reviewer_auth'] == 'configured'
    assert response.json()['mode'] == 'manual'
    assert response.json()['nvidia'] == 'missing'
    assert 'secret' not in response.text
