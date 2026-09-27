import io
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr

from app.main import app
from app.config import settings
from app.services import media

client = TestClient(app)


@pytest.fixture(autouse=True)
def provider(monkeypatch):
    monkeypatch.setattr(settings, 'MEDIA_UPLOAD_TOKEN', SecretStr('test-token'))
    monkeypatch.setattr(settings, 'REVIEWER_TOKENS', SecretStr(''))
    monkeypatch.setattr(settings, 'CLOUDINARY_CLOUD_NAME', 'test-cloud')
    monkeypatch.setattr(settings, 'CLOUDINARY_API_KEY', 'test-key')
    monkeypatch.setattr(settings, 'CLOUDINARY_API_SECRET', SecretStr('test-secret'))
    mock = Mock(return_value=dict(asset_id='asset-1', public_id='lex/river/image-1',
                version=123, resource_type='image', format='png', width=16, height=12,
                secure_url='https://res.cloudinary.com/test-cloud/image/upload/v123/lex/river/image-1.png'))
    monkeypatch.setattr(media.cloudinary.uploader, 'upload', mock)
    return mock


def picture(fmt='PNG'):
    output = io.BytesIO()
    Image.new('RGB', (16, 12)).save(output, format=fmt)
    return output.getvalue()


def post(data=None, mime='image/png', token='test-token', **fields):
    return client.post('/api/v1/media/images',
        headers={'Authorization': f'Bearer {token}'},
        files={'file': ('sample.png', picture() if data is None else data, mime)},
        data={'project_id': 'river', 'source': 'Permissioned team photo',
              'visit_date': '2026-09-23', **fields})


@pytest.mark.parametrize('fmt,mime', [('PNG','image/png'), ('JPEG','image/jpeg'), ('WEBP','image/webp')])
def test_upload_preserves_identity(provider, fmt, mime):
    response = post(picture(fmt), mime)
    assert response.status_code == 201
    result = response.json()
    assert result['asset_id'] == 'asset-1'
    assert result['permission_status'] == 'granted'
    assert '/v123/lex/river/image-1.png' in result['thumbnail_url']
    assert result['context']['visit_date'] == '2026-09-23'
    assert len(result['context']['sha256']) == 64
    options = provider.call_args.kwargs
    assert options['overwrite'] is False
    assert options['context'] == result['context']
    assert options['tags'] == ['lex', 'project_river']
    assert options['public_id'].startswith('lex/river/')
    assert 'test-secret' not in response.text



@pytest.mark.parametrize('data,mime,status', [
    (b'', 'image/png', 422), (b'not an image', 'image/png', 422),
    (picture(), 'image/jpeg', 415), (picture('GIF'), 'image/gif', 415),
    (b'x' * (media.MAX_BYTES + 1), 'image/png', 413),
    (picture()[:40], 'image/png', 422),
], ids=['empty', 'not_image', 'wrong_mime', 'gif', 'oversized', 'truncated'])
def test_invalid_files_never_reach_provider(provider, data, mime, status):
    assert post(data, mime).status_code == status
    provider.assert_not_called()


@pytest.mark.parametrize('fields', [{'source':'   '}, {'project_id':'../escape'}, {'visit_date':'yesterday'}])
def test_invalid_metadata(provider, fields):
    assert post(**fields).status_code == 422
    provider.assert_not_called()


def test_pixel_limit(provider, monkeypatch):
    monkeypatch.setattr(media, 'MAX_PIXELS', 100)
    assert post().status_code == 422
    provider.assert_not_called()


def test_auth(provider, monkeypatch):
    assert post(token='wrong').status_code == 401
    monkeypatch.setattr(settings, 'MEDIA_UPLOAD_TOKEN', SecretStr(''))
    assert post().status_code == 503
    provider.assert_not_called()


def test_missing_configuration(provider, monkeypatch):
    monkeypatch.setattr(settings, 'CLOUDINARY_API_SECRET', SecretStr(''))
    assert post().status_code == 503
    provider.assert_not_called()


def test_provider_error_is_redacted(provider):
    provider.side_effect = RuntimeError('test-secret sensitive-provider-details')
    response = post()
    assert response.status_code == 502
    assert 'test-secret' not in response.text
    assert 'sensitive-provider-details' not in response.text


def test_incomplete_provider_response(provider):
    provider.return_value = {}
    assert post().status_code == 502


def test_upload_permission_status_validation():
    valid = post(permission_status='pending_verification')
    assert valid.status_code == 201
    assert valid.json()['permission_status'] == 'pending_verification'

    revoked = post(permission_status='revoked')
    assert revoked.status_code == 201
    assert revoked.json()['permission_status'] == 'revoked'

    invalid = post(permission_status='invalid_status')
    assert invalid.status_code == 422
    assert 'permission_status must be one of' in invalid.text

