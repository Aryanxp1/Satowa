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
