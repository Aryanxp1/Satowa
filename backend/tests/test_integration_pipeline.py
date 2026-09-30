"""End-to-End Integration and Error Matrix Tests for Cloudinary and Gemini Pipeline.

Tests:
1. Error Matrix (A through J) with isolated, deterministic mocks.
2. Complete end-to-end evidence lifecycle (Site -> Visits -> Assets -> Pair -> Comparison -> Review -> Report).
3. Optional Live Integration Test (only executes when RUN_LIVE_INTEGRATION=1).
"""
import io
import json
import os
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr

from app.config import settings
from app.main import app
from app.services import image_comparison, media
from app.services.image_comparison import ComparisonStatus, UncertaintyReason

client = TestClient(app)
AUTH_HEADERS = {'Authorization': 'Bearer reviewer-token'}


def create_test_image_bytes(color='red', width=16, height=12, fmt='PNG') -> bytes:
    out = io.BytesIO()
    Image.new('RGB', (width, height), color=color).save(out, fmt)
    return out.getvalue()


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path, monkeypatch):
    """Ensure tests run against an isolated SQLite database and deterministic tokens."""
    monkeypatch.setattr(settings, 'LEX_DB_PATH', str(tmp_path / 'integration.sqlite3'))
    monkeypatch.setattr(settings, 'MEDIA_UPLOAD_TOKEN', SecretStr('upload-token'))
    monkeypatch.setattr(settings, 'REVIEWER_TOKENS', SecretStr('{"Aryan":"reviewer-token"}'))
    if os.getenv('RUN_LIVE_INTEGRATION') != '1':
        monkeypatch.setattr(settings, 'CLOUDINARY_CLOUD_NAME', 'test-cloud')
        monkeypatch.setattr(settings, 'CLOUDINARY_API_KEY', 'test-key')
        monkeypatch.setattr(settings, 'CLOUDINARY_API_SECRET', SecretStr('test-secret'))
        monkeypatch.setattr(settings, 'GEMINI_API_KEY', 'test-gemini-key')


# ==============================================================================
# ERROR MATRIX TESTS (A through J)
# ==============================================================================

class TestErrorMatrix:
    """Deterministic failure matrix verifying safety, error states, and review integrity."""

    def test_matrix_a_missing_cloudinary_credentials(self, monkeypatch):
        """A. Missing Cloudinary credentials -> 503 error, no fake asset stored."""
        monkeypatch.setattr(settings, 'CLOUDINARY_CLOUD_NAME', '')
        resp = client.post(
            '/api/v1/media/images',
            headers=AUTH_HEADERS,
            data={'project_id': 'river', 'source': 'Field Team', 'visit_date': '2026-09-23'},
            files={'file': ('img.png', create_test_image_bytes(), 'image/png')}
        )
        assert resp.status_code == 503
        assert 'Cloudinary is not configured' in resp.text

    def test_matrix_b_cloudinary_upload_failure(self, monkeypatch):
        """B. Cloudinary upload network/SDK failure -> 502 error, credentials redacted."""
        def failing_upload(*args, **kwargs):
            raise RuntimeError('Cloudinary connection aborted: sensitive-token-secret-123')
        monkeypatch.setattr(media.cloudinary.uploader, 'upload', Mock(side_effect=failing_upload))

        resp = client.post(
            '/api/v1/media/images',
            headers=AUTH_HEADERS,
            data={'project_id': 'river', 'source': 'Field Team', 'visit_date': '2026-09-23'},
            files={'file': ('img.png', create_test_image_bytes(), 'image/png')}
        )
        assert resp.status_code == 502
        assert 'sensitive-token-secret' not in resp.text
        assert 'Cloudinary upload failed; no success was recorded' in resp.text

    def test_matrix_c_invalid_cloudinary_response(self, monkeypatch):
        """C. Incomplete or invalid Cloudinary provider response -> 502 error."""
        monkeypatch.setattr(media.cloudinary.uploader, 'upload', Mock(return_value={}))
        resp = client.post(
            '/api/v1/media/images',
            headers=AUTH_HEADERS,
            data={'project_id': 'river', 'source': 'Field Team', 'visit_date': '2026-09-23'},
            files={'file': ('img.png', create_test_image_bytes(), 'image/png')}
        )
        assert resp.status_code == 502

    def test_matrix_d_missing_gemini_credentials(self, monkeypatch):
        """D. Missing Gemini credentials -> safe fallback, pending review status preserved."""
        monkeypatch.setattr(settings, 'GEMINI_API_KEY', '')

        # Setup site and assets with mock upload
        client.post('/api/v1/sites', json={'id': 'site-d', 'name': 'Site D'}, headers=AUTH_HEADERS)
        v1 = client.post('/api/v1/sites/site-d/visits', json={'visited_on': '2026-09-01', 'label': 'V1'}, headers=AUTH_HEADERS).json()
        v2 = client.post('/api/v1/sites/site-d/visits', json={'visited_on': '2026-09-15', 'label': 'V2'}, headers=AUTH_HEADERS).json()

        counter = iter(range(10))
        def fake_upload(*args, **kwargs):
            n = next(counter)
            return {'asset_id': f'd-asset-{n}', 'public_id': f'lex/site-d/img-{n}', 'version': n+1,
                    'resource_type': 'image', 'format': 'png', 'width': 16, 'height': 12,
                    'secure_url': f'https://res.cloudinary.com/test-cloud/image/upload/v{n+1}/lex/site-d/img-{n}.png'}
        monkeypatch.setattr(media.cloudinary.uploader, 'upload', Mock(side_effect=fake_upload))

        a1 = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                         data={'project_id': 'site-d', 'visit_date': '2026-09-01', 'visit_id': v1['id'], 'source': 'Photo'},
                         files={'file': ('1.png', create_test_image_bytes(), 'image/png')}).json()['asset_id']
        a2 = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                         data={'project_id': 'site-d', 'visit_date': '2026-09-15', 'visit_id': v2['id'], 'source': 'Photo'},
                         files={'file': ('2.png', create_test_image_bytes(), 'image/png')}).json()['asset_id']

        resp = client.post('/api/v1/pairs', json={'before_asset_id': a1, 'after_asset_id': a2}, headers=AUTH_HEADERS)
        assert resp.status_code == 201
        obs = resp.json()
        assert obs['review_status'] == 'pending'
        assert obs['approved_text'] is None
        assert obs['ai_draft'] is None
        assert 'GEMINI_API_KEY' in (obs['reliability_reason'] or '')

    def test_matrix_e_gemini_timeout_provider_failure(self, monkeypatch):
        """E. Gemini timeout / provider failure -> safe uncertain result, observation stays pending."""
        def failing_gemini(request):
            if request.url.host == 'res.cloudinary.com':
                return httpx.Response(200, content=create_test_image_bytes())
            return httpx.Response(504, text="Gateway Timeout")
        transport = httpx.MockTransport(failing_gemini)
        orig = httpx.AsyncClient
        monkeypatch.setattr(image_comparison.httpx, 'AsyncClient', lambda **kw: orig(transport=transport, **kw))

        client.post('/api/v1/sites', json={'id': 'site-e', 'name': 'Site E'}, headers=AUTH_HEADERS)
        v1 = client.post('/api/v1/sites/site-e/visits', json={'visited_on': '2026-09-01', 'label': 'V1'}, headers=AUTH_HEADERS).json()
        v2 = client.post('/api/v1/sites/site-e/visits', json={'visited_on': '2026-09-15', 'label': 'V2'}, headers=AUTH_HEADERS).json()

        counter = iter(range(10))
        def fake_upload(*args, **kwargs):
            n = next(counter)
            return {'asset_id': f'e-asset-{n}', 'public_id': f'lex/site-e/img-{n}', 'version': n+1,
                    'resource_type': 'image', 'format': 'png', 'width': 16, 'height': 12,
                    'secure_url': f'https://res.cloudinary.com/test-cloud/image/upload/v{n+1}/lex/site-e/img-{n}.png'}
        monkeypatch.setattr(media.cloudinary.uploader, 'upload', Mock(side_effect=fake_upload))

        a1 = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                         data={'project_id': 'site-e', 'visit_date': '2026-09-01', 'visit_id': v1['id'], 'source': 'Photo'},
                         files={'file': ('1.png', create_test_image_bytes(), 'image/png')}).json()['asset_id']
        a2 = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                         data={'project_id': 'site-e', 'visit_date': '2026-09-15', 'visit_id': v2['id'], 'source': 'Photo'},
                         files={'file': ('2.png', create_test_image_bytes(), 'image/png')}).json()['asset_id']

        resp = client.post('/api/v1/pairs', json={'before_asset_id': a1, 'after_asset_id': a2}, headers=AUTH_HEADERS)
        assert resp.status_code == 201
        obs = resp.json()
        assert obs['review_status'] == 'pending'
        assert obs['approved_text'] is None
        assert obs['ai_draft'] is None
        assert 'invalid result' in (obs['reliability_reason'] or '').lower() or 'failed' in (obs['reliability_reason'] or '').lower()

    def test_matrix_f_malformed_gemini_response(self, monkeypatch):
        """F. Malformed non-JSON Gemini response -> safe fallback without crash."""
        def malformed_gemini(request):
            if request.url.host == 'res.cloudinary.com':
                return httpx.Response(200, content=create_test_image_bytes())
            return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': '<<<broken json>>'}]}}]})
        transport = httpx.MockTransport(malformed_gemini)
        orig = httpx.AsyncClient
        monkeypatch.setattr(image_comparison.httpx, 'AsyncClient', lambda **kw: orig(transport=transport, **kw))

        client.post('/api/v1/sites', json={'id': 'site-f', 'name': 'Site F'}, headers=AUTH_HEADERS)
        v1 = client.post('/api/v1/sites/site-f/visits', json={'visited_on': '2026-09-01', 'label': 'V1'}, headers=AUTH_HEADERS).json()
        v2 = client.post('/api/v1/sites/site-f/visits', json={'visited_on': '2026-09-15', 'label': 'V2'}, headers=AUTH_HEADERS).json()

        counter = iter(range(10))
        def fake_upload(*args, **kwargs):
            n = next(counter)
            return {'asset_id': f'f-asset-{n}', 'public_id': f'lex/site-f/img-{n}', 'version': n+1,
                    'resource_type': 'image', 'format': 'png', 'width': 16, 'height': 12,
                    'secure_url': f'https://res.cloudinary.com/test-cloud/image/upload/v{n+1}/lex/site-f/img-{n}.png'}
        monkeypatch.setattr(media.cloudinary.uploader, 'upload', Mock(side_effect=fake_upload))

        a1 = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                         data={'project_id': 'site-f', 'visit_date': '2026-09-01', 'visit_id': v1['id'], 'source': 'Photo'},
                         files={'file': ('1.png', create_test_image_bytes(), 'image/png')}).json()['asset_id']
        a2 = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                         data={'project_id': 'site-f', 'visit_date': '2026-09-15', 'visit_id': v2['id'], 'source': 'Photo'},
                         files={'file': ('2.png', create_test_image_bytes(), 'image/png')}).json()['asset_id']

        resp = client.post('/api/v1/pairs', json={'before_asset_id': a1, 'after_asset_id': a2}, headers=AUTH_HEADERS)
        assert resp.status_code == 201
        obs = resp.json()
        assert obs['review_status'] == 'pending'
        assert obs['ai_draft'] is None

    def test_matrix_g_invalid_structured_gemini_response(self, monkeypatch):
        """G. Gemini returns invalid schema values (e.g. invalid status or confidence > 1.0)."""
        invalid_body = {'status': 'nonexistent_status', 'confidence': 1.5, 'summary': 'Cleaned up'}
        def invalid_gemini(request):
            if request.url.host == 'res.cloudinary.com':
                return httpx.Response(200, content=create_test_image_bytes())
            return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': json.dumps(invalid_body)}]}}]})
        transport = httpx.MockTransport(invalid_gemini)
        orig = httpx.AsyncClient
        monkeypatch.setattr(image_comparison.httpx, 'AsyncClient', lambda **kw: orig(transport=transport, **kw))

        client.post('/api/v1/sites', json={'id': 'site-g', 'name': 'Site G'}, headers=AUTH_HEADERS)
        v1 = client.post('/api/v1/sites/site-g/visits', json={'visited_on': '2026-09-01', 'label': 'V1'}, headers=AUTH_HEADERS).json()
        v2 = client.post('/api/v1/sites/site-g/visits', json={'visited_on': '2026-09-15', 'label': 'V2'}, headers=AUTH_HEADERS).json()

        counter = iter(range(10))
        def fake_upload(*args, **kwargs):
            n = next(counter)
            return {'asset_id': f'g-asset-{n}', 'public_id': f'lex/site-g/img-{n}', 'version': n+1,
                    'resource_type': 'image', 'format': 'png', 'width': 16, 'height': 12,
                    'secure_url': f'https://res.cloudinary.com/test-cloud/image/upload/v{n+1}/lex/site-g/img-{n}.png'}
        monkeypatch.setattr(media.cloudinary.uploader, 'upload', Mock(side_effect=fake_upload))

        a1 = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                         data={'project_id': 'site-g', 'visit_date': '2026-09-01', 'visit_id': v1['id'], 'source': 'Photo'},
                         files={'file': ('1.png', create_test_image_bytes(), 'image/png')}).json()['asset_id']
        a2 = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                         data={'project_id': 'site-g', 'visit_date': '2026-09-15', 'visit_id': v2['id'], 'source': 'Photo'},
                         files={'file': ('2.png', create_test_image_bytes(), 'image/png')}).json()['asset_id']

        resp = client.post('/api/v1/pairs', json={'before_asset_id': a1, 'after_asset_id': a2}, headers=AUTH_HEADERS)
        assert resp.status_code == 201
        obs = resp.json()
        assert obs['review_status'] == 'pending'
        assert obs['ai_draft'] is None

    def test_matrix_h_valid_gemini_response_remains_pending(self, monkeypatch):
        """H. Valid structured Gemini response -> draft proposed, but strictly pending human review."""
        valid_body = {
            'status': 'changed',
            'summary': 'Visible litter substantially reduced.',
            'changes': [{'type': 'debris_reduction', 'description': 'Litter removed', 'evidence': 'Clear grass'}],
            'confidence': 0.89
        }
        def valid_gemini(request):
            if request.url.host == 'res.cloudinary.com':
                return httpx.Response(200, content=create_test_image_bytes())
            return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': json.dumps(valid_body)}]}}]})
        transport = httpx.MockTransport(valid_gemini)
        orig = httpx.AsyncClient
        monkeypatch.setattr(image_comparison.httpx, 'AsyncClient', lambda **kw: orig(transport=transport, **kw))

        client.post('/api/v1/sites', json={'id': 'site-h', 'name': 'Site H'}, headers=AUTH_HEADERS)
        v1 = client.post('/api/v1/sites/site-h/visits', json={'visited_on': '2026-09-01', 'label': 'V1'}, headers=AUTH_HEADERS).json()
        v2 = client.post('/api/v1/sites/site-h/visits', json={'visited_on': '2026-09-15', 'label': 'V2'}, headers=AUTH_HEADERS).json()

        counter = iter(range(10))
        def fake_upload(*args, **kwargs):
            n = next(counter)
            return {'asset_id': f'h-asset-{n}', 'public_id': f'lex/site-h/img-{n}', 'version': n+1,
                    'resource_type': 'image', 'format': 'png', 'width': 16, 'height': 12,
                    'secure_url': f'https://res.cloudinary.com/test-cloud/image/upload/v{n+1}/lex/site-h/img-{n}.png'}
        monkeypatch.setattr(media.cloudinary.uploader, 'upload', Mock(side_effect=fake_upload))

        a1 = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                         data={'project_id': 'site-h', 'visit_date': '2026-09-01', 'visit_id': v1['id'], 'source': 'Photo'},
                         files={'file': ('1.png', create_test_image_bytes(), 'image/png')}).json()['asset_id']
        a2 = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                         data={'project_id': 'site-h', 'visit_date': '2026-09-15', 'visit_id': v2['id'], 'source': 'Photo'},
                         files={'file': ('2.png', create_test_image_bytes(), 'image/png')}).json()['asset_id']

        resp = client.post('/api/v1/pairs', json={'before_asset_id': a1, 'after_asset_id': a2}, headers=AUTH_HEADERS)
        assert resp.status_code == 201
        obs = resp.json()
        assert obs['review_status'] == 'pending'
        assert obs['approved_text'] is None
        assert obs['ai_draft'] == 'Visible litter substantially reduced.'

        # Must NOT appear in report until approved
        rep = client.get('/api/v1/sites/site-h/report', headers=AUTH_HEADERS).json()
        assert len(rep['observations']) == 0

    def test_matrix_i_uncertain_gemini_response(self, monkeypatch):
        """I. Uncertain Gemini response -> preserves uncertainty_reason, pending for review."""
        uncertain_body = {
            'status': 'uncertain',
            'summary': None,
            'changes': [],
            'confidence': 0.35,
            'uncertainty_reason': 'camera_angle_mismatch'
        }
        def uncertain_gemini(request):
            if request.url.host == 'res.cloudinary.com':
                return httpx.Response(200, content=create_test_image_bytes())
            return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': json.dumps(uncertain_body)}]}}]})
        transport = httpx.MockTransport(uncertain_gemini)
        orig = httpx.AsyncClient
        monkeypatch.setattr(image_comparison.httpx, 'AsyncClient', lambda **kw: orig(transport=transport, **kw))

        client.post('/api/v1/sites', json={'id': 'site-i', 'name': 'Site I'}, headers=AUTH_HEADERS)
        v1 = client.post('/api/v1/sites/site-i/visits', json={'visited_on': '2026-09-01', 'label': 'V1'}, headers=AUTH_HEADERS).json()
        v2 = client.post('/api/v1/sites/site-i/visits', json={'visited_on': '2026-09-15', 'label': 'V2'}, headers=AUTH_HEADERS).json()

        counter = iter(range(10))
        def fake_upload(*args, **kwargs):
            n = next(counter)
            return {'asset_id': f'i-asset-{n}', 'public_id': f'lex/site-i/img-{n}', 'version': n+1,
                    'resource_type': 'image', 'format': 'png', 'width': 16, 'height': 12,
                    'secure_url': f'https://res.cloudinary.com/test-cloud/image/upload/v{n+1}/lex/site-i/img-{n}.png'}
        monkeypatch.setattr(media.cloudinary.uploader, 'upload', Mock(side_effect=fake_upload))

        a1 = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                         data={'project_id': 'site-i', 'visit_date': '2026-09-01', 'visit_id': v1['id'], 'source': 'Photo'},
                         files={'file': ('1.png', create_test_image_bytes(), 'image/png')}).json()['asset_id']
        a2 = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                         data={'project_id': 'site-i', 'visit_date': '2026-09-15', 'visit_id': v2['id'], 'source': 'Photo'},
                         files={'file': ('2.png', create_test_image_bytes(), 'image/png')}).json()['asset_id']

        resp = client.post('/api/v1/pairs', json={'before_asset_id': a1, 'after_asset_id': a2}, headers=AUTH_HEADERS)
        assert resp.status_code == 201
        obs = resp.json()
        assert obs['review_status'] == 'pending'
        assert obs['ai_draft'] is None
        assert obs['reliability_reason'] == 'camera_angle_mismatch'

    def test_matrix_j_insufficient_evidence_response(self, monkeypatch):
        """J. Insufficient evidence response -> preserves reason, pending for review."""
        insufficient_body = {
            'status': 'insufficient_evidence',
            'summary': None,
            'changes': [],
            'confidence': 0.05,
            'uncertainty_reason': 'poor_image_quality'
        }
        def insufficient_gemini(request):
            if request.url.host == 'res.cloudinary.com':
                return httpx.Response(200, content=create_test_image_bytes())
            return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': json.dumps(insufficient_body)}]}}]})
        transport = httpx.MockTransport(insufficient_gemini)
        orig = httpx.AsyncClient
        monkeypatch.setattr(image_comparison.httpx, 'AsyncClient', lambda **kw: orig(transport=transport, **kw))

        client.post('/api/v1/sites', json={'id': 'site-j', 'name': 'Site J'}, headers=AUTH_HEADERS)
        v1 = client.post('/api/v1/sites/site-j/visits', json={'visited_on': '2026-09-01', 'label': 'V1'}, headers=AUTH_HEADERS).json()
        v2 = client.post('/api/v1/sites/site-j/visits', json={'visited_on': '2026-09-15', 'label': 'V2'}, headers=AUTH_HEADERS).json()

        counter = iter(range(10))
        def fake_upload(*args, **kwargs):
            n = next(counter)
            return {'asset_id': f'j-asset-{n}', 'public_id': f'lex/site-j/img-{n}', 'version': n+1,
                    'resource_type': 'image', 'format': 'png', 'width': 16, 'height': 12,
                    'secure_url': f'https://res.cloudinary.com/test-cloud/image/upload/v{n+1}/lex/site-j/img-{n}.png'}
        monkeypatch.setattr(media.cloudinary.uploader, 'upload', Mock(side_effect=fake_upload))

        a1 = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                         data={'project_id': 'site-j', 'visit_date': '2026-09-01', 'visit_id': v1['id'], 'source': 'Photo'},
                         files={'file': ('1.png', create_test_image_bytes(), 'image/png')}).json()['asset_id']
        a2 = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                         data={'project_id': 'site-j', 'visit_date': '2026-09-15', 'visit_id': v2['id'], 'source': 'Photo'},
                         files={'file': ('2.png', create_test_image_bytes(), 'image/png')}).json()['asset_id']

        resp = client.post('/api/v1/pairs', json={'before_asset_id': a1, 'after_asset_id': a2}, headers=AUTH_HEADERS)
        assert resp.status_code == 201
        obs = resp.json()
        assert obs['review_status'] == 'pending'
        assert obs['ai_draft'] is None
        assert obs['reliability_reason'] == 'poor_image_quality'


# ==============================================================================
# END-TO-END PIPELINE LIFECYCLE (DETERMINISTIC)
# ==============================================================================

class TestEndToEndPipeline:
    """Verifies all phases: Cloudinary Ingestion -> Assets -> Pair -> Gemini -> Review -> Report."""

    def test_complete_evidence_lifecycle(self, monkeypatch):
        # 1. Setup Gemini mock returning structured 'changed'
        gemini_response = {
            'status': 'changed',
            'summary': 'Less visible plastic waste on shoreline.',
            'changes': [{'type': 'debris_reduction', 'description': 'Plastic bottles removed', 'evidence': 'Shoreline clear'}],
            'confidence': 0.91,
            'evidence_notes': 'Good lighting, matching angles.'
        }
        def mock_gemini(request):
            if request.url.host == 'res.cloudinary.com':
                return httpx.Response(200, content=create_test_image_bytes())
            return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': json.dumps(gemini_response)}]}}]})
        transport = httpx.MockTransport(mock_gemini)
        orig = httpx.AsyncClient
        monkeypatch.setattr(image_comparison.httpx, 'AsyncClient', lambda **kw: orig(transport=transport, **kw))

        # 2. Setup Cloudinary mock
        upload_counter = iter(range(1, 10))
        def mock_cloudinary_upload(*args, **kwargs):
            n = next(upload_counter)
            return {
                'asset_id': f'e2e-asset-{n}',
                'public_id': f'lex/river-e2e/photo-{n}',
                'version': 100 + n,
                'resource_type': 'image',
                'format': 'png',
                'width': 1024,
                'height': 768,
                'secure_url': f'https://res.cloudinary.com/test-cloud/image/upload/v{100+n}/lex/river-e2e/photo-{n}.png'
            }
        monkeypatch.setattr(media.cloudinary.uploader, 'upload', Mock(side_effect=mock_cloudinary_upload))

        # Phase 1: Site and Visits
        s_resp = client.post('/api/v1/sites', json={'id': 'river-e2e', 'name': 'River E2E Cleanup'}, headers=AUTH_HEADERS)
        assert s_resp.status_code == 201
        v1 = client.post('/api/v1/sites/river-e2e/visits', json={'visited_on': '2026-09-01', 'label': 'Pre-cleanup'}, headers=AUTH_HEADERS).json()
        v2 = client.post('/api/v1/sites/river-e2e/visits', json={'visited_on': '2026-09-20', 'label': 'Post-cleanup'}, headers=AUTH_HEADERS).json()

        # Phase 2: Ingest Before & After Assets with Cloudinary metadata
        b_up = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                           data={'project_id': 'river-e2e', 'visit_date': '2026-09-01', 'visit_id': v1['id'], 'source': 'Ranger Photo', 'permission_status': 'granted'},
                           files={'file': ('before.png', create_test_image_bytes('black'), 'image/png')})
        assert b_up.status_code == 201
        before_asset = b_up.json()
        assert before_asset['permission_status'] == 'granted'
        assert before_asset['width'] == 1024
        assert before_asset['height'] == 768
        assert before_asset['secure_url'].startswith('https://res.cloudinary.com/')
        assert 'thumbnail_url' in before_asset

        a_up = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                           data={'project_id': 'river-e2e', 'visit_date': '2026-09-20', 'visit_id': v2['id'], 'source': 'Ranger Photo', 'permission_status': 'granted'},
                           files={'file': ('after.png', create_test_image_bytes('green'), 'image/png')})
        assert a_up.status_code == 201
        after_asset = a_up.json()

        # Phase 3: Pair Validation & AI Structured Comparison
        p_resp = client.post('/api/v1/pairs', json={'before_asset_id': before_asset['asset_id'], 'after_asset_id': after_asset['asset_id']}, headers=AUTH_HEADERS)
        assert p_resp.status_code == 201
        obs = p_resp.json()
        assert obs['review_status'] == 'pending'
        assert obs['approved_text'] is None
        assert obs['ai_draft'] == 'Less visible plastic waste on shoreline.'
        assert obs['working_text'] == 'Less visible plastic waste on shoreline.'

        # Verify unapproved observation is EXCLUDED from report
        rep_pre = client.get('/api/v1/sites/river-e2e/report', headers=AUTH_HEADERS).json()
        assert len(rep_pre['observations']) == 0

        # Phase 4: Human Review & Approval
        rev_resp = client.post(
            f'/api/v1/observations/{obs["id"]}/review',
            headers=AUTH_HEADERS,
            json={'decision': 'approve', 'expected_version': obs['version'], 'text': 'Verified clean bank by human reviewer.'}
        )
        assert rev_resp.status_code == 200
        approved_obs = rev_resp.json()
        assert approved_obs['review_status'] == 'approved'
        assert approved_obs['approved_text'] == 'Verified clean bank by human reviewer.'
        assert approved_obs['reviewed_by'] == 'Aryan'
        assert approved_obs['reviewed_at'] is not None

        # Phase 5: Report Generation with Traceability
        rep_post = client.get('/api/v1/sites/river-e2e/report', headers=AUTH_HEADERS).json()
        assert len(rep_post['observations']) == 1
        item = rep_post['observations'][0]
        assert item['id'] == obs['id']
        assert item['approved_text'] == 'Verified clean bank by human reviewer.'
        assert item['before_asset_id'] == before_asset['asset_id']
        assert item['after_asset_id'] == after_asset['asset_id']
        assert item['before_url'] == before_asset['secure_url']
        assert item['after_url'] == after_asset['secure_url']
        assert item['before_date'] == '2026-09-01'
        assert item['after_date'] == '2026-09-20'
        assert item['reviewed_by'] == 'Aryan'

        # Markdown format export
        md_resp = client.get('/api/v1/sites/river-e2e/report?format=markdown', headers=AUTH_HEADERS)
        assert md_resp.status_code == 200
        assert 'River E2E Cleanup — Setowa Evidence Report' in md_resp.text
        assert 'Verified clean bank by human reviewer.' in md_resp.text
        assert before_asset['secure_url'] in md_resp.text
        assert after_asset['secure_url'] in md_resp.text

        # Revoked permission on evidence asset excludes it from the report
        from app.services import evidence_store as store
        with store.connection() as db:
            db.execute("UPDATE assets SET permission_status='revoked' WHERE asset_id=?", (before_asset['asset_id'],))
        rep_revoked = client.get('/api/v1/sites/river-e2e/report', headers=AUTH_HEADERS).json()
        assert len(rep_revoked['observations']) == 0

        # Restoring permission includes it again
        with store.connection() as db:
            db.execute("UPDATE assets SET permission_status='granted' WHERE asset_id=?", (before_asset['asset_id'],))
        rep_restored = client.get('/api/v1/sites/river-e2e/report', headers=AUTH_HEADERS).json()
        assert len(rep_restored['observations']) == 1

        # Evidence mutation after approval -> approval is invalidated
        # Ingest a third asset to swap as the after asset
        a3_up = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                            data={'project_id': 'river-e2e', 'visit_date': '2026-09-20', 'visit_id': v2['id'], 'source': 'Ranger Photo', 'permission_status': 'granted'},
                            files={'file': ('after2.png', create_test_image_bytes('blue'), 'image/png')})
        assert a3_up.status_code == 201
        after_asset2 = a3_up.json()

        # Mutate the observation pair to use after_asset2
        edit_resp = client.patch(
            f'/api/v1/observations/{obs["id"]}',
            headers=AUTH_HEADERS,
            json={'expected_version': approved_obs['version'], 'after_asset_id': after_asset2['asset_id']}
        )
        assert edit_resp.status_code == 200
        mutated_obs = edit_resp.json()
        # Invariant: AI/evidence mutation invalidates approval
        assert mutated_obs['review_status'] == 'pending'
        assert mutated_obs['approved_text'] is None
        assert mutated_obs['reviewed_by'] is None
        assert mutated_obs['reviewed_at'] is None
        assert mutated_obs['after_asset_id'] == after_asset2['asset_id']

        # Mutated observation is excluded from report again
        rep_after_mutation = client.get('/api/v1/sites/river-e2e/report', headers=AUTH_HEADERS).json()
        assert len(rep_after_mutation['observations']) == 0


# ==============================================================================
# LIVE INTEGRATION TEST (RUNS ONLY IF RUN_LIVE_INTEGRATION=1)
# ==============================================================================

@pytest.mark.skipif(
    os.getenv('RUN_LIVE_INTEGRATION') != '1',
    reason='Live integration requires RUN_LIVE_INTEGRATION=1'
)
def test_live_cloudinary_and_gemini_pipeline():
    """Live end-to-end test against real Cloudinary and Gemini APIs.

    Skips cleanly if RUN_LIVE_INTEGRATION != 1 or real credentials are not configured.
    """
    secret = (
        settings.CLOUDINARY_API_SECRET.get_secret_value()
        if hasattr(settings.CLOUDINARY_API_SECRET, 'get_secret_value')
        else (settings.CLOUDINARY_API_SECRET or '')
    )
    cloud = settings.CLOUDINARY_CLOUD_NAME or ''
    key = settings.CLOUDINARY_API_KEY or ''
    gemini_key = settings.GEMINI_API_KEY or ''

    if not (cloud and key and secret) or cloud in ('', 'test-cloud', 'demo-cloud', 'your_cloud_name'):
        pytest.skip('Real Cloudinary credentials not configured in environment; skipping live test.')
    if not gemini_key or gemini_key in ('', 'test-gemini-key', 'dummy-key', 'your_gemini_api_key'):
        pytest.skip('Real GEMINI_API_KEY not configured in environment; skipping live test.')

    site_id = f'live-{os.urandom(4).hex()}'
    client.post('/api/v1/sites', json={'id': site_id, 'name': 'Live Integration Site'}, headers=AUTH_HEADERS)
    v1 = client.post(f'/api/v1/sites/{site_id}/visits', json={'visited_on': '2026-09-01', 'label': 'Live Pre'}, headers=AUTH_HEADERS).json()
    v2 = client.post(f'/api/v1/sites/{site_id}/visits', json={'visited_on': '2026-09-20', 'label': 'Live Post'}, headers=AUTH_HEADERS).json()

    # Real Cloudinary uploads
    b_up = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                       data={'project_id': site_id, 'visit_date': '2026-09-01', 'visit_id': v1['id'], 'source': 'Live Team Photo', 'permission_status': 'granted'},
                       files={'file': ('live_before.png', create_test_image_bytes('darkred', 64, 48), 'image/png')})
    assert b_up.status_code == 201, f"Live Cloudinary upload failed: {b_up.text}"
    before_asset = b_up.json()
    assert before_asset['secure_url'].startswith('https://res.cloudinary.com/')
    assert before_asset['permission_status'] == 'granted'
    assert before_asset['width'] == 64
    assert before_asset['height'] == 48

    a_up = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                       data={'project_id': site_id, 'visit_date': '2026-09-20', 'visit_id': v2['id'], 'source': 'Live Team Photo', 'permission_status': 'granted'},
                       files={'file': ('live_after.png', create_test_image_bytes('darkgreen', 64, 48), 'image/png')})
    assert a_up.status_code == 201, f"Live Cloudinary upload failed: {a_up.text}"
    after_asset = a_up.json()
    assert after_asset['secure_url'].startswith('https://res.cloudinary.com/')
    assert after_asset['permission_status'] == 'granted'

    # Real pair selection + Real Gemini call
    pair_resp = client.post('/api/v1/pairs', json={'before_asset_id': before_asset['asset_id'], 'after_asset_id': after_asset['asset_id']}, headers=AUTH_HEADERS)
    assert pair_resp.status_code == 201, f"Pair selection failed: {pair_resp.text}"
    obs = pair_resp.json()
    assert obs['review_status'] == 'pending'
    assert obs['approved_text'] is None

    # Human review
    approved_text = obs['working_text'] or "Human reviewer confirmed site condition."
    rev_resp = client.post(f'/api/v1/observations/{obs["id"]}/review', headers=AUTH_HEADERS, json={'decision': 'approve', 'expected_version': obs['version'], 'text': approved_text})
    assert rev_resp.status_code == 200
    assert rev_resp.json()['review_status'] == 'approved'

    # Report verification
    rep = client.get(f'/api/v1/sites/{site_id}/report', headers=AUTH_HEADERS).json()
    assert len(rep['observations']) == 1
    assert rep['observations'][0]['id'] == obs['id']
    assert rep['observations'][0]['before_url'].startswith('https://res.cloudinary.com/')
    assert rep['observations'][0]['after_url'].startswith('https://res.cloudinary.com/')



@pytest.fixture(autouse=True)
def optional_gemini_provider_contract(monkeypatch):
    """These legacy contract tests deliberately exercise the optional Gemini adapter."""
    from app.config import settings
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
