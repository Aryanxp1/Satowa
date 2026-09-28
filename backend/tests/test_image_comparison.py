import asyncio
import json

import httpx
import pytest

from app.config import settings
from app.services import image_comparison as comparison

BEFORE = {'secure_url':'https://res.cloudinary.com/demo-cloud/image/upload/v1/lex/river/before.png','format':'png'}
AFTER = {'secure_url':'https://res.cloudinary.com/demo-cloud/image/upload/v2/lex/river/after.png','format':'png'}


@pytest.mark.parametrize('model_output,expected', [
    ({'reliable':True,'observation':'Less visible litter in the photographed section.','reason':None}, True),
    ({'reliable':False,'observation':None,'reason':'Camera viewpoints do not match.'}, False),
    ({'reliable':True,'observation':'35 kg of waste was removed.','reason':None}, False),
])
def test_gemini_comparison_validates_output(monkeypatch, model_output, expected):
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', 'dummy-key')
    monkeypatch.setattr(settings, 'CLOUDINARY_CLOUD_NAME', 'demo-cloud')
    def handler(request):
        if request.url.host == 'res.cloudinary.com':
            return httpx.Response(200, content=b'image-bytes')
        assert request.headers['x-goog-api-key']=='dummy-key'
        body=json.loads(request.content)
        assert len(body['contents'][0]['parts'])==3
        return httpx.Response(200, json={'candidates':[{'content':{'parts':[{'text':json.dumps(model_output)}]}}]})
    transport=httpx.MockTransport(handler)
    original=httpx.AsyncClient
    monkeypatch.setattr(comparison.httpx,'AsyncClient',lambda **kwargs: original(transport=transport,**kwargs))
    result=asyncio.run(comparison.compare_images(BEFORE,AFTER))
    assert result.reliable is expected
    assert (result.observation is not None) is expected
    if not expected:
        assert result.reason


def test_rejects_untrusted_url_without_network(monkeypatch):
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', 'dummy-key')
    monkeypatch.setattr(settings, 'CLOUDINARY_CLOUD_NAME', 'demo-cloud')
    untrusted={**BEFORE,'secure_url':'https://example.org/private.png'}
    result=asyncio.run(comparison.compare_images(untrusted, AFTER))
    assert not result.reliable and result.observation is None


def test_invalid_model_response_refuses(monkeypatch):
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', 'dummy-key')
    monkeypatch.setattr(settings, 'CLOUDINARY_CLOUD_NAME', 'demo-cloud')
    def handler(request):
        if request.url.host == 'res.cloudinary.com':
            return httpx.Response(200, content=b'image-bytes')
        return httpx.Response(200, json={'candidates':[{'content':{'parts':[{'text':'not json'}]}}]})
    original=httpx.AsyncClient
    transport=httpx.MockTransport(handler)
    monkeypatch.setattr(comparison.httpx,'AsyncClient',lambda **kwargs: original(transport=transport,**kwargs))
    result=asyncio.run(comparison.compare_images(BEFORE,AFTER))
    assert not result.reliable and result.observation is None
    assert 'invalid result' in result.reason


def mock_gemini(monkeypatch, response_payload, status_code=200):
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', 'dummy-key')
    monkeypatch.setattr(settings, 'CLOUDINARY_CLOUD_NAME', 'demo-cloud')
    def handler(request):
        if request.url.host == 'res.cloudinary.com':
            return httpx.Response(200, content=b'image-bytes')
        assert request.headers['x-goog-api-key'] == 'dummy-key'
        if status_code != 200:
            return httpx.Response(status_code, text=str(response_payload))
        if isinstance(response_payload, str) and not response_payload.startswith('{'):
            return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': response_payload}]}}]})
        text_content = response_payload if isinstance(response_payload, str) else json.dumps(response_payload)
        return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': text_content}]}}]})
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient
    monkeypatch.setattr(comparison.httpx, 'AsyncClient', lambda **kwargs: original(transport=transport, **kwargs))
    return asyncio.run(comparison.compare_images(BEFORE, AFTER))


def test_matrix_a_changed_result_parses_correctly(monkeypatch):
    data = {
        "status": "changed",
        "summary": "Visible litter substantially reduced along the river bank.",
        "changes": [
            {
                "type": "debris_reduction",
                "description": "Fewer plastic bottles and bags visible on shore",
                "evidence": "Foreground shoreline clear in second image"
            }
        ],
        "confidence": 0.88,
        "evidence_notes": "Consistent daylight lighting and angles."
    }
    result = mock_gemini(monkeypatch, data)
    assert result.status == comparison.ComparisonStatus.CHANGED
    assert result.summary == "Visible litter substantially reduced along the river bank."
    assert result.observation == "Visible litter substantially reduced along the river bank."
    assert len(result.changes) == 1
    assert result.changes[0].type == "debris_reduction"
    assert result.changes[0].description == "Fewer plastic bottles and bags visible on shore"
    assert result.confidence == 0.88
    assert result.reliable is True
    assert result.uncertainty_reason is None
    assert result.reason is None


def test_matrix_b_unchanged_result_parses_correctly(monkeypatch):
    data = {
        "status": "unchanged",
        "summary": "No noticeable difference in litter or site condition.",
        "changes": [],
        "confidence": 0.92,
        "evidence_notes": "Site appears unchanged between visits."
    }
    result = mock_gemini(monkeypatch, data)
    assert result.status == comparison.ComparisonStatus.UNCHANGED
    assert result.summary == "No noticeable difference in litter or site condition."
    assert result.reliable is True
    assert result.confidence == 0.92
    assert result.uncertainty_reason is None


def test_matrix_c_uncertain_result_parses_correctly(monkeypatch):
    data = {
        "status": "uncertain",
        "summary": None,
        "changes": [],
        "confidence": 0.35,
        "uncertainty_reason": "camera_angle_mismatch",
        "evidence_notes": "Camera angles differ by ~90 degrees making comparison unreliable."
    }
    result = mock_gemini(monkeypatch, data)
    assert result.status == comparison.ComparisonStatus.UNCERTAIN
    assert result.uncertainty_reason == "camera_angle_mismatch"
    assert result.reliable is False
    assert result.observation is None
    assert result.confidence == 0.35


def test_matrix_d_insufficient_evidence_result_parses_correctly(monkeypatch):
    data = {
        "status": "insufficient_evidence",
        "summary": None,
        "changes": [],
        "confidence": 0.05,
        "uncertainty_reason": "poor_image_quality",
        "evidence_notes": "Heavy lens glare and blur obscure the cleanup area."
    }
    result = mock_gemini(monkeypatch, data)
    assert result.status == comparison.ComparisonStatus.INSUFFICIENT_EVIDENCE
    assert result.uncertainty_reason == "poor_image_quality"
    assert result.reliable is False
    assert result.observation is None
    assert result.confidence == 0.05


@pytest.mark.parametrize('valid_conf', [0.0, 0.01, 0.5, 0.99, 1.0])
def test_matrix_e_confidence_range_valid(valid_conf):
    comp = comparison.Comparison(
        status=comparison.ComparisonStatus.CHANGED,
        summary="Test change",
        confidence=valid_conf
    )
    assert comp.confidence == valid_conf


@pytest.mark.parametrize('invalid_conf', [-0.5, -0.01, 1.01, 2.5, 99.4])
def test_matrix_f_invalid_confidence_rejected_safely(monkeypatch, invalid_conf):
    data = {
        "status": "changed",
        "summary": "Looks cleaner",
        "confidence": invalid_conf
    }
    result = mock_gemini(monkeypatch, data)
    assert result.reliable is False
    assert result.status == comparison.ComparisonStatus.UNCERTAIN
    assert result.uncertainty_reason == comparison.UncertaintyReason.PROVIDER_ERROR.value
    assert result.observation is None


@pytest.mark.parametrize('invalid_status', ['completely_cleaned', 'done', 'better', 'random_state', ''])
def test_matrix_g_invalid_status_rejected_safely(monkeypatch, invalid_status):
    data = {
        "status": invalid_status,
        "summary": "Visible change",
        "confidence": 0.8
    }
    result = mock_gemini(monkeypatch, data)
    assert result.reliable is False
    assert result.status == comparison.ComparisonStatus.UNCERTAIN
    assert result.uncertainty_reason == comparison.UncertaintyReason.PROVIDER_ERROR.value


@pytest.mark.parametrize('malformed_text', ['{not: json}', 'Plain text without json', '', '{"status": '])
def test_matrix_h_malformed_provider_json_safe(monkeypatch, malformed_text):
    result = mock_gemini(monkeypatch, malformed_text)
    assert result.reliable is False
    assert result.status == comparison.ComparisonStatus.UNCERTAIN
    assert result.uncertainty_reason == comparison.UncertaintyReason.PROVIDER_ERROR.value


def test_matrix_i_missing_fields_safe(monkeypatch):
    result = mock_gemini(monkeypatch, {})
    assert result.reliable is False
    assert result.status in (comparison.ComparisonStatus.UNCERTAIN, comparison.ComparisonStatus.INSUFFICIENT_EVIDENCE)


def test_matrix_j_provider_http_failure_safe(monkeypatch):
    result = mock_gemini(monkeypatch, "Internal Server Error", status_code=500)
    assert result.reliable is False
    assert result.status == comparison.ComparisonStatus.UNCERTAIN
    assert result.uncertainty_reason == comparison.UncertaintyReason.PROVIDER_ERROR.value


def test_matrix_k_uncertain_result_preserves_reason(monkeypatch):
    data = {
        "status": "uncertain",
        "summary": None,
        "uncertainty_reason": "lighting_difference",
        "confidence": 0.25,
        "evidence_notes": "Sunset lighting creates long shadows obscuring ground."
    }
    result = mock_gemini(monkeypatch, data)
    assert result.status == comparison.ComparisonStatus.UNCERTAIN
    assert result.uncertainty_reason == "lighting_difference"
    assert result.reason == "lighting_difference"


def test_matrix_l_insufficient_evidence_preserves_reason(monkeypatch):
    data = {
        "status": "insufficient_evidence",
        "summary": None,
        "uncertainty_reason": "relevant_area_not_visible",
        "confidence": 0.1,
        "evidence_notes": "Camera pointed at sky instead of ground."
    }
    result = mock_gemini(monkeypatch, data)
    assert result.status == comparison.ComparisonStatus.INSUFFICIENT_EVIDENCE
    assert result.uncertainty_reason == "relevant_area_not_visible"
    assert result.reason == "relevant_area_not_visible"


@pytest.mark.parametrize('claim', [
    '35 kg of litter removed',
    'Collected 12 kilograms of debris',
    'Site is 85% cleaner',
    'Site is 85 percent improved',
    'Removed 10 bags of trash',
    'Collected 50 items',
    'Removed 20 lbs of waste',
])
def test_matrix_m_quantitative_claims_refused(monkeypatch, claim):
    data = {
        "status": "changed",
        "summary": f"Great work: {claim}.",
        "changes": [
            {"type": "debris_reduction", "description": claim, "evidence": "Clean ground"}
        ],
        "confidence": 0.95
    }
    result = mock_gemini(monkeypatch, data)
    assert result.reliable is False
    assert result.status == comparison.ComparisonStatus.UNCERTAIN
    assert result.uncertainty_reason == comparison.UncertaintyReason.UNVERIFIED_QUANTITATIVE_CLAIM.value
    assert result.observation is None

