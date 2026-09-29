"""Remote pilot must not expose older API routes outside the reviewer gate."""

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import settings
from app.main import app


def test_remote_pilot_gates_entire_api_and_uses_named_reviewer(monkeypatch):
    monkeypatch.setattr(settings, 'ENVIRONMENT', 'pilot')
    monkeypatch.setattr(settings, 'REVIEWER_TOKENS', SecretStr('{"Farhan":"pilot-test-token"}'))
    client = TestClient(app)
    assert client.get('/api/v1/health').status_code == 200
    for path in ('/api/v1/projects', '/api/v1/skills', '/api/v1/workflows',
                 '/api/v1/pilot/session'):
        assert client.get(path).status_code == 401
    headers = {'Authorization': 'Bearer pilot-test-token'}
    session = client.get('/api/v1/pilot/session', headers=headers)
    assert session.status_code == 200
    assert session.json()['reviewer'] == 'Farhan'
    assert 'pilot-test-token' not in session.text
    assert client.get('/api/v1/projects', headers=headers).status_code == 200
    assert client.get('/api/v1/local/status', headers=headers).status_code == 403
