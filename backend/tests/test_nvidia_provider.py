"""Provider contract tests use a fake key and no live network."""
import asyncio
import httpx
import pytest
from pydantic import SecretStr
from app.config import settings
from app.providers import nvidia


def configure(monkeypatch, handler):
    monkeypatch.setattr(settings, 'NVIDIA_API_KEY', SecretStr('unit-test-only'))
    original = httpx.AsyncClient
    monkeypatch.setattr(nvidia.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))


def test_embedding_modes_and_order(monkeypatch):
    requests = []
    def handler(request):
        import json
        body = json.loads(request.content)
        requests.append(body)
        assert request.headers['authorization'] == 'Bearer unit-test-only'
        return httpx.Response(200, json={'data': [
            {'index': i, 'embedding': [0.2, 0.3]} for i in reversed(range(len(body['input'])))]})
    configure(monkeypatch, handler)
    assert asyncio.run(nvidia.embeddings(['a', 'b'], input_type='passage')) == [[0.2, 0.3]] * 2
    asyncio.run(nvidia.embeddings(['q'], input_type='query'))
    assert [r['input_type'] for r in requests] == ['passage', 'query']


def test_auth_error_is_sanitized_and_not_retried(monkeypatch):
    calls = []
    def handler(request):
        calls.append(1)
        return httpx.Response(403, text='private-provider-details')
    configure(monkeypatch, handler)
    with pytest.raises(nvidia.ProviderUnavailable) as error:
        asyncio.run(nvidia.embeddings(['a'], input_type='passage'))
    assert len(calls) == 1
    assert 'private-provider-details' not in str(error.value)
    assert 'unit-test-only' not in str(error.value)


def test_retry_limit(monkeypatch):
    calls = []
    def handler(request):
        calls.append(1)
        return httpx.Response(429)
    configure(monkeypatch, handler)
    async def no_wait(_): pass
    monkeypatch.setattr(nvidia.asyncio, 'sleep', no_wait)
    with pytest.raises(nvidia.ProviderUnavailable):
        asyncio.run(nvidia.embeddings(['a'], input_type='passage'))
    assert len(calls) == 3


def test_nonfinite_vectors_rejected(monkeypatch):
    configure(monkeypatch, lambda _: httpx.Response(200, json={'data': [{'index': 0, 'embedding': ['NaN']}]}))
    with pytest.raises(nvidia.ProviderUnavailable):
        asyncio.run(nvidia.embeddings(['a'], input_type='query'))


def test_unregistered_vision_never_calls_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'LEX_DB_PATH', str(tmp_path / 'vision.sqlite3'))
    async def forbidden(*args, **kwargs):
        pytest.fail('Unregistered media reached provider')
    monkeypatch.setattr(nvidia, 'request_json', forbidden)
    with pytest.raises(nvidia.ProviderUnavailable):
        asyncio.run(nvidia.describe_registered_media('missing'))


def test_nvidia_pair_does_not_invent_comparison(monkeypatch):
    from app.services.image_comparison import compare_images
    monkeypatch.setattr(settings, 'AI_PROVIDER', 'nvidia')
    result = asyncio.run(compare_images({'secure_url': 'https://example.test/a'}, {'secure_url': 'https://example.test/b'}))
    assert result.reliable is False
    assert result.observation is None
    assert result.uncertainty_reason == 'pair_model_not_validated'


def test_registered_vision_schema_cache_and_revocation(tmp_path, monkeypatch):
    import json
    from app.services import evidence_store as store
    from app.services.media_intelligence import analyze_asset
    from fastapi import HTTPException
    from tests.test_discovery_campaign import seed
    monkeypatch.setattr(settings, 'LEX_DB_PATH', str(tmp_path / 'registered.sqlite3'))
    monkeypatch.setattr(settings, 'AI_PROVIDER', 'nvidia')
    monkeypatch.setattr(settings, 'CLOUDINARY_CLOUD_NAME', 'test')
    with store.connection() as db:
        seed(db)
    calls = []
    async def vision(endpoint, body):
        calls.append(body)
        return {'choices': [{'message': {'content': json.dumps({
            'description': 'Visible debris near water.', 'observations': ['Visible debris.'],
            'tags': ['debris', 'water'], 'status': 'analyzed', 'uncertainty': None})}}]}
    monkeypatch.setattr(nvidia, 'request_json', vision)
    async def run_analysis():
        with store.connection() as db:
            return await analyze_asset(db, 'p-one-before')
    first = asyncio.run(run_analysis())
    second = asyncio.run(run_analysis())
    assert first.id == second.id
    assert first.model_provider == 'nvidia'
    assert len(calls) == 1
    with store.connection() as db:
        db.execute("UPDATE assets SET permission_status='revoked' WHERE asset_id='p-one-before'")
    with pytest.raises(HTTPException) as error:
        asyncio.run(run_analysis())
    assert error.value.status_code == 403
    assert len(calls) == 1
