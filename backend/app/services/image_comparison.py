"""Conservative two-image Gemini comparison; errors never produce a fake observation."""
import base64
import json
import re
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.services.media import MAX_BYTES


class Comparison(BaseModel):
    reliable: bool
    observation: str | None = Field(default=None, max_length=600)
    reason: str | None = Field(default=None, max_length=300)


def unavailable(reason):
    return Comparison(reliable=False, reason=reason)


async def _image_bytes(client, asset):
    parsed = urlparse(asset['secure_url'])
    expected = f'/'+settings.CLOUDINARY_CLOUD_NAME+'/image/upload/'
    if parsed.scheme != 'https' or parsed.netloc != 'res.cloudinary.com' or not parsed.path.startswith(expected):
        raise ValueError('Evidence URL is not a trusted Cloudinary image')
    data = bytearray()
    async with client.stream('GET', asset['secure_url'], follow_redirects=False) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError('Evidence could not be retrieved')
        async for chunk in response.aiter_bytes():
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise ValueError('Evidence exceeds image size limit')
    if not data:
        raise ValueError('Evidence is empty')
    return base64.b64encode(data).decode('ascii')


async def compare_images(before, after):
    if not settings.GEMINI_API_KEY:
        return unavailable('AI comparison is unavailable until GEMINI_API_KEY is configured. A reviewer may write an observation manually.')
    prompt = (
        'Compare BEFORE image first with AFTER image second for one cleanup site. '
        'Return JSON with exactly reliable (boolean), observation (string or null), '
        'reason (string or null). If viewpoint, framing, lighting, visibility, or image '
        'quality makes a meaningful comparison uncertain, set reliable=false, '
        'observation=null, and explain why. If reliable, describe only visible change '
        'in one cautious sentence. Never infer waste weight, environmental impact, '
        'cause, elapsed time, or work performed from photos. No numerical impact claims.'
    )
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            before_data = await _image_bytes(client, before)
            after_data = await _image_bytes(client, after)
            payload = {'contents': [{'parts': [
                {'text': prompt},
                {'inline_data': {'mime_type': 'image/'+('jpeg' if before['format']=='jpg' else before['format']), 'data': before_data}},
                {'inline_data': {'mime_type': 'image/'+('jpeg' if after['format']=='jpg' else after['format']), 'data': after_data}},
            ]}], 'generationConfig': {'responseMimeType': 'application/json'}}
            response = await client.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_VISION_MODEL}:generateContent',
                headers={'x-goog-api-key': settings.GEMINI_API_KEY}, json=payload,
            )
            response.raise_for_status()
            parts = response.json()['candidates'][0]['content']['parts']
            result = Comparison.model_validate(json.loads(''.join(part.get('text','') for part in parts)))
            if not result.reliable:
                return unavailable(result.reason or 'The images cannot be compared reliably.')
            if not result.observation or not result.observation.strip():
                return unavailable('The AI did not provide a supported observation.')
            if re.search(r'\b\d+(?:\.\d+)?\s*(?:kg|kilograms?|tonnes?|tons?|%|percent)\b', result.observation, re.I):
                return unavailable('The AI proposed an unverified numerical impact claim.')
            return Comparison(reliable=True, observation=result.observation.strip())
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, ValidationError):
        return unavailable('AI comparison failed or returned an invalid result. Review the images manually.')
