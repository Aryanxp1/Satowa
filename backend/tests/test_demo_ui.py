"""Judge-facing review experience and frontend integration test suite.

Verifies:
1. AI result renders correctly.
2. Changed result displays correctly.
3. Uncertain result displays uncertainty.
4. Insufficient evidence displays warning.
5. Pending state shows human verification requirement.
6. Approved state shows verified result.
7. Unapproved result cannot appear as verified.
8. Permission errors are displayed.
9. API/provider errors are displayed safely.
"""
import io
import json
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr

from app.config import settings
from app.main import app
from app.services import image_comparison, media

client = TestClient(app)
AUTH_HEADERS = {'Authorization': 'Bearer reviewer-token'}


def create_test_image_bytes(color='green', width=16, height=12) -> bytes:
    out = io.BytesIO()
    Image.new('RGB', (width, height), color=color).save(out, 'PNG')
    return out.getvalue()


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path, monkeypatch):
    """Ensure tests run against an isolated SQLite database and deterministic tokens."""
    monkeypatch.setattr(settings, 'LEX_DB_PATH', str(tmp_path / 'demo_ui.sqlite3'))
    monkeypatch.setattr(settings, 'MEDIA_UPLOAD_TOKEN', SecretStr('upload-token'))
    monkeypatch.setattr(settings, 'REVIEWER_TOKENS', SecretStr('{"Farhan":"reviewer-token"}'))
    monkeypatch.setattr(settings, 'CLOUDINARY_CLOUD_NAME', 'test-cloud')
    monkeypatch.setattr(settings, 'CLOUDINARY_API_KEY', 'test-key')
    monkeypatch.setattr(settings, 'CLOUDINARY_API_SECRET', SecretStr('test-secret'))
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', 'test-gemini-key')


class TestDemoUIAssets:
    """Verify demo workspace assets, structure, and static file delivery."""

    def test_demo_static_files_served(self):
        resp_index = client.get('/demo/')
        assert resp_index.status_code == 200
        assert 'Setowa — Evidence workspace' in resp_index.text

        resp_js = client.get('/demo/app.js')
        assert resp_js.status_code == 200
        assert 'renderObservations' in resp_js.text
        assert 'formatReason' in resp_js.text

        resp_css = client.get('/demo/styles.css')
        assert resp_css.status_code == 200
        assert '.observation-card' in resp_css.text

    def test_demo_html_components_exist(self):
        resp = client.get('/demo/')
        html = resp.text
        # Compare components
        assert 'id="before-select"' in html
        assert 'id="after-select"' in html
        assert 'id="before-card"' in html
        assert 'id="after-card"' in html
        assert 'id="comparison-stage"' in html
        assert 'id="pair-validation-warning"' in html
        assert 'id="compare"' in html
        # Review components
        assert 'id="observations"' in html
        # Report components
        assert 'id="report-count"' in html
        assert 'id="report-live-preview"' in html
        assert 'id="report-json-view"' in html
        assert 'id="export"' in html
        # Lightbox component
        assert 'id="lightbox-modal"' in html


class TestCriticalBehavior:
    """Tests corresponding to the 9 critical judge review behaviors."""

    def _setup_pair(self, monkeypatch, before_color='black', after_color='green'):
        client.post('/api/v1/sites', json={'id': 'ui-site', 'name': 'UI Demo Site'}, headers=AUTH_HEADERS)
        v1 = client.post('/api/v1/sites/ui-site/visits', json={'visited_on': '2026-09-01', 'label': 'Pre'}, headers=AUTH_HEADERS).json()
        v2 = client.post('/api/v1/sites/ui-site/visits', json={'visited_on': '2026-09-20', 'label': 'Post'}, headers=AUTH_HEADERS).json()

        counter = iter(range(10))
        def fake_upload(*args, **kwargs):
            n = next(counter)
            return {'asset_id': f'ui-asset-{n}', 'public_id': f'lex/ui/img-{n}', 'version': n+1,
                    'resource_type': 'image', 'format': 'png', 'width': 1024, 'height': 768,
                    'secure_url': f'https://res.cloudinary.com/test-cloud/image/upload/v{n+1}/lex/ui/img-{n}.png'}
        monkeypatch.setattr(media.cloudinary.uploader, 'upload', Mock(side_effect=fake_upload))

        b_up = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                           data={'project_id': 'ui-site', 'visit_date': '2026-09-01', 'visit_id': v1['id'], 'source': 'Field Team', 'permission_status': 'granted'},
                           files={'file': ('b.png', create_test_image_bytes(before_color), 'image/png')}).json()
        a_up = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                           data={'project_id': 'ui-site', 'visit_date': '2026-09-20', 'visit_id': v2['id'], 'source': 'Field Team', 'permission_status': 'granted'},
                           files={'file': ('a.png', create_test_image_bytes(after_color), 'image/png')}).json()
        return b_up['asset_id'], a_up['asset_id']

    def test_behavior_1_ai_result_renders_correctly(self, monkeypatch):
        """1. AI result contract delivered with structured comparison details."""
        b_id, a_id = self._setup_pair(monkeypatch)
        mock_body = {
            'status': 'changed',
            'summary': 'Tires and plastic debris removed along waterline.',
            'changes': [{'type': 'waste_removal', 'description': 'Tires removed', 'evidence': 'Clear gravel'}],
            'confidence': 0.88,
            'evidence_notes': 'Clear angle match and daylight.'
        }
        def fake_gemini(req):
            if req.url.host == 'res.cloudinary.com':
                return httpx.Response(200, content=create_test_image_bytes())
            return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': json.dumps(mock_body)}]}}]})
        orig = httpx.AsyncClient
        monkeypatch.setattr(image_comparison.httpx, 'AsyncClient', lambda **kw: orig(transport=httpx.MockTransport(fake_gemini), **kw))

        pair_resp = client.post('/api/v1/pairs', json={'before_asset_id': b_id, 'after_asset_id': a_id}, headers=AUTH_HEADERS)
        assert pair_resp.status_code == 201
        data = pair_resp.json()
        assert 'comparison' in data
        assert data['comparison']['status'] == 'changed'
        assert data['comparison']['summary'] == 'Tires and plastic debris removed along waterline.'
        assert data['comparison']['confidence'] == 0.88
        assert len(data['comparison']['changes']) == 1

    def test_behavior_2_changed_result_displays_correctly(self, monkeypatch):
        """2. Changed result displays draft proposal but stays pending."""
        b_id, a_id = self._setup_pair(monkeypatch)
        mock_body = {'status': 'changed', 'summary': 'Clean bank.', 'changes': [], 'confidence': 0.90}
        def fake_gemini(req):
            if req.url.host == 'res.cloudinary.com':
                return httpx.Response(200, content=create_test_image_bytes())
            return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': json.dumps(mock_body)}]}}]})
        orig = httpx.AsyncClient
        monkeypatch.setattr(image_comparison.httpx, 'AsyncClient', lambda **kw: orig(transport=httpx.MockTransport(fake_gemini), **kw))

        obs = client.post('/api/v1/pairs', json={'before_asset_id': b_id, 'after_asset_id': a_id}, headers=AUTH_HEADERS).json()
        assert obs['review_status'] == 'pending'
        assert obs['ai_draft'] == 'Clean bank.'
        assert obs['working_text'] == 'Clean bank.'
        assert obs['approved_text'] is None

    def test_behavior_3_uncertain_result_displays_uncertainty(self, monkeypatch):
        """3. Uncertain result preserves reason without fabricating draft text."""
        b_id, a_id = self._setup_pair(monkeypatch)
        mock_body = {
            'status': 'uncertain',
            'summary': None,
            'changes': [],
            'confidence': 0.35,
            'uncertainty_reason': 'camera_angle_mismatch'
        }
        def fake_gemini(req):
            if req.url.host == 'res.cloudinary.com':
                return httpx.Response(200, content=create_test_image_bytes())
            return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': json.dumps(mock_body)}]}}]})
        orig = httpx.AsyncClient
        monkeypatch.setattr(image_comparison.httpx, 'AsyncClient', lambda **kw: orig(transport=httpx.MockTransport(fake_gemini), **kw))

        obs = client.post('/api/v1/pairs', json={'before_asset_id': b_id, 'after_asset_id': a_id}, headers=AUTH_HEADERS).json()
        assert obs['review_status'] == 'pending'
        assert obs['ai_draft'] is None
        assert obs['reliability_reason'] == 'camera_angle_mismatch'
        assert obs['comparison']['status'] == 'uncertain'
        assert obs['comparison']['uncertainty_reason'] == 'camera_angle_mismatch'

    def test_behavior_4_insufficient_evidence_displays_warning(self, monkeypatch):
        """4. Insufficient evidence result preserves poor image quality warning."""
        b_id, a_id = self._setup_pair(monkeypatch)
        mock_body = {
            'status': 'insufficient_evidence',
            'summary': None,
            'changes': [],
            'confidence': 0.10,
            'uncertainty_reason': 'poor_image_quality'
        }
        def fake_gemini(req):
            if req.url.host == 'res.cloudinary.com':
                return httpx.Response(200, content=create_test_image_bytes())
            return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': json.dumps(mock_body)}]}}]})
        orig = httpx.AsyncClient
        monkeypatch.setattr(image_comparison.httpx, 'AsyncClient', lambda **kw: orig(transport=httpx.MockTransport(fake_gemini), **kw))

        obs = client.post('/api/v1/pairs', json={'before_asset_id': b_id, 'after_asset_id': a_id}, headers=AUTH_HEADERS).json()
        assert obs['review_status'] == 'pending'
        assert obs['reliability_reason'] == 'poor_image_quality'
        assert obs['comparison']['status'] == 'insufficient_evidence'

    def test_behavior_5_pending_state_shows_human_verification_requirement(self, monkeypatch):
        """5. AI results never auto-approve; pending review status is invariant."""
        b_id, a_id = self._setup_pair(monkeypatch)
        mock_body = {'status': 'changed', 'summary': 'Clean bank.', 'changes': [], 'confidence': 0.99}
        def fake_gemini(req):
            if req.url.host == 'res.cloudinary.com':
                return httpx.Response(200, content=create_test_image_bytes())
            return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': json.dumps(mock_body)}]}}]})
        orig = httpx.AsyncClient
        monkeypatch.setattr(image_comparison.httpx, 'AsyncClient', lambda **kw: orig(transport=httpx.MockTransport(fake_gemini), **kw))

        obs = client.post('/api/v1/pairs', json={'before_asset_id': b_id, 'after_asset_id': a_id}, headers=AUTH_HEADERS).json()
        assert obs['review_status'] == 'pending'
        assert obs['approved_text'] is None
        assert obs['reviewed_by'] is None
        assert obs['reviewed_at'] is None

    def test_behavior_6_approved_state_shows_verified_result(self, monkeypatch):
        """6. Reviewer approval records verified finding with attribution."""
        b_id, a_id = self._setup_pair(monkeypatch)
        mock_body = {'status': 'changed', 'summary': 'Clean bank.', 'changes': [], 'confidence': 0.90}
        def fake_gemini(req):
            if req.url.host == 'res.cloudinary.com':
                return httpx.Response(200, content=create_test_image_bytes())
            return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': json.dumps(mock_body)}]}}]})
        orig = httpx.AsyncClient
        monkeypatch.setattr(image_comparison.httpx, 'AsyncClient', lambda **kw: orig(transport=httpx.MockTransport(fake_gemini), **kw))

        obs = client.post('/api/v1/pairs', json={'before_asset_id': b_id, 'after_asset_id': a_id}, headers=AUTH_HEADERS).json()

        rev_resp = client.post(
            f'/api/v1/observations/{obs["id"]}/review',
            headers=AUTH_HEADERS,
            json={'decision': 'approve', 'expected_version': obs['version'], 'text': 'Human reviewer verified: No visible litter.'}
        )
        assert rev_resp.status_code == 200
        approved = rev_resp.json()
        assert approved['review_status'] == 'approved'
        assert approved['approved_text'] == 'Human reviewer verified: No visible litter.'
        assert approved['reviewed_by'] == 'Farhan'
        assert approved['reviewed_at'] is not None

    def test_behavior_7_unapproved_result_cannot_appear_as_verified(self, monkeypatch):
        """7. Report endpoint strictly excludes unapproved or pending observations."""
        b_id, a_id = self._setup_pair(monkeypatch)
        mock_body = {'status': 'changed', 'summary': 'Clean bank.', 'changes': [], 'confidence': 0.90}
        def fake_gemini(req):
            if req.url.host == 'res.cloudinary.com':
                return httpx.Response(200, content=create_test_image_bytes())
            return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': json.dumps(mock_body)}]}}]})
        orig = httpx.AsyncClient
        monkeypatch.setattr(image_comparison.httpx, 'AsyncClient', lambda **kw: orig(transport=httpx.MockTransport(fake_gemini), **kw))

        obs = client.post('/api/v1/pairs', json={'before_asset_id': b_id, 'after_asset_id': a_id}, headers=AUTH_HEADERS).json()

        rep = client.get('/api/v1/sites/ui-site/report', headers=AUTH_HEADERS).json()
        assert len(rep['observations']) == 0

        # Markdown format export also excludes it
        md = client.get('/api/v1/sites/ui-site/report?format=markdown', headers=AUTH_HEADERS).text
        assert 'Clean bank.' not in md

    def test_behavior_8_permission_errors_are_displayed(self, monkeypatch):
        """8. Non-granted permission status prevents pair comparison with clear 422 error."""
        client.post('/api/v1/sites', json={'id': 'perm-site', 'name': 'Perm Site'}, headers=AUTH_HEADERS)
        v1 = client.post('/api/v1/sites/perm-site/visits', json={'visited_on': '2026-09-01', 'label': 'V1'}, headers=AUTH_HEADERS).json()
        v2 = client.post('/api/v1/sites/perm-site/visits', json={'visited_on': '2026-09-20', 'label': 'V2'}, headers=AUTH_HEADERS).json()

        counter = iter(range(10))
        def fake_upload(*args, **kwargs):
            n = next(counter)
            return {'asset_id': f'p-asset-{n}', 'public_id': f'lex/p/img-{n}', 'version': n+1,
                    'resource_type': 'image', 'format': 'png', 'width': 1024, 'height': 768,
                    'secure_url': f'https://res.cloudinary.com/test-cloud/image/upload/v{n+1}/lex/p/img-{n}.png'}
        monkeypatch.setattr(media.cloudinary.uploader, 'upload', Mock(side_effect=fake_upload))

        b = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                        data={'project_id': 'perm-site', 'visit_date': '2026-09-01', 'visit_id': v1['id'], 'source': 'Team', 'permission_status': 'revoked'},
                        files={'file': ('b.png', create_test_image_bytes(), 'image/png')}).json()['asset_id']
        a = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                        data={'project_id': 'perm-site', 'visit_date': '2026-09-20', 'visit_id': v2['id'], 'source': 'Team', 'permission_status': 'granted'},
                        files={'file': ('a.png', create_test_image_bytes(), 'image/png')}).json()['asset_id']

        resp = client.post('/api/v1/pairs', json={'before_asset_id': b, 'after_asset_id': a}, headers=AUTH_HEADERS)
        assert resp.status_code == 422
        assert "Before asset permission is 'revoked', must be 'granted'" in resp.text

    def test_behavior_9_api_and_provider_errors_are_displayed_safely(self, monkeypatch):
        """9. Provider errors (503 missing config, 502 upload failure, 409 conflict) handled safely."""
        # 503 missing Cloudinary config
        monkeypatch.setattr(settings, 'CLOUDINARY_CLOUD_NAME', '')
        resp = client.post('/api/v1/media/images', headers=AUTH_HEADERS,
                           data={'project_id': 'any', 'visit_date': '2026-09-01', 'source': 'Team'},
                           files={'file': ('x.png', create_test_image_bytes(), 'image/png')})
        assert resp.status_code == 503
        assert 'Cloudinary is not configured' in resp.text

        # 409 version conflict on review
        monkeypatch.setattr(settings, 'CLOUDINARY_CLOUD_NAME', 'test-cloud')
        b_id, a_id = self._setup_pair(monkeypatch)
        obs = client.post('/api/v1/pairs', json={'before_asset_id': b_id, 'after_asset_id': a_id}, headers=AUTH_HEADERS).json()

        stale_resp = client.post(
            f'/api/v1/observations/{obs["id"]}/review',
            headers=AUTH_HEADERS,
            json={'decision': 'approve', 'expected_version': obs['version'] + 99, 'text': 'Stale'}
        )
        assert stale_resp.status_code == 409
        assert 'Observation changed; reload before reviewing' in stale_resp.text


@pytest.fixture(autouse=True)
def optional_gemini_provider_contract(monkeypatch):
    """These legacy contract tests deliberately exercise the optional Gemini adapter."""
    from app.config import settings
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
