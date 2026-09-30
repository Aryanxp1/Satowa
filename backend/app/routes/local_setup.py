"""Loopback-only setup for the local demo. Provider secrets never go in responses."""
import json
import os
import tempfile

from fastapi import APIRouter, HTTPException, Request, Response

from app.config import credential_path, load_local_credentials, refresh_provider_settings, settings
from app.services.reviewer_auth import (LOCAL_COOKIE, LOCAL_SESSIONS, local_request,
                                         local_session_actor, new_local_session,
                                         reviewer_tokens, same_origin)

router = APIRouter(prefix='/api/v1/local', tags=['Local demo setup'])


def require_local(request: Request, *, mutation: bool = False):
    if not local_request(request) or (mutation and not same_origin(request)):
        raise HTTPException(403, 'This action is available only in the local demo')


def public_status(request: Request):
    return {
        'cloudinary_ready': all((settings.CLOUDINARY_CLOUD_NAME,
                                 settings.CLOUDINARY_API_KEY,
                                 settings.CLOUDINARY_API_SECRET.get_secret_value())),
        'gemini_ready': bool(settings.GEMINI_API_KEY),
        'nvidia_ready': bool(settings.NVIDIA_API_KEY.get_secret_value()),
        'reviewer_ready': bool(reviewer_tokens()),
        'reviewer': local_session_actor(request),
    }


@router.get('/status')
def status(request: Request, response: Response):
    require_local(request)
    response.headers['Cache-Control'] = 'no-store'
    return public_status(request)


@router.post('/session')
def start_session(request: Request, response: Response):
    require_local(request, mutation=True)
    reviewers = reviewer_tokens()
    if not reviewers:
        raise HTTPException(503, 'No local reviewer is configured')
    actor = 'Aryan' if 'Aryan' in reviewers else next(iter(reviewers))
    response.set_cookie(LOCAL_COOKIE, new_local_session(actor), httponly=True,
                        samesite='strict', secure=False, path='/api/v1', max_age=8 * 60 * 60)
    response.headers['Cache-Control'] = 'no-store'
    return {'reviewer': actor}


@router.post('/session/logout')
def end_session(request: Request, response: Response):
    require_local(request, mutation=True)
    LOCAL_SESSIONS.pop(request.cookies.get(LOCAL_COOKIE, ''), None)
    response.delete_cookie(LOCAL_COOKIE, path='/api/v1')
    response.headers['Cache-Control'] = 'no-store'
    return {'reviewer': None}


@router.put('/credentials')
async def save_credentials(request: Request, response: Response):
    require_local(request, mutation=True)
    if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
        raise HTTPException(415, 'JSON is required')
    body = await request.body()
    if len(body) > 4096:
        raise HTTPException(413, 'Credential form is too large')
    try:
        submitted = json.loads(body)
        if not isinstance(submitted, dict) or set(submitted) - {'cloudinary', 'gemini'}:
            raise ValueError
        patch = {}
        for section, allowed in {'cloudinary': {'cloud_name', 'api_key', 'api_secret'},
                                 'gemini': {'api_key'}}.items():
            values = submitted.get(section, {})
            if not isinstance(values, dict) or set(values) - allowed:
                raise ValueError
            patch[section] = {}
            for name, value in values.items():
                if not isinstance(value, str) or len(value) > 512:
                    raise ValueError
                if value.strip():
                    patch[section][name] = value.strip()
    except (UnicodeDecodeError, ValueError, TypeError):
        raise HTTPException(422, 'Credential form is invalid') from None

    path = credential_path()
    try:
        existing = load_local_credentials(path)
        merged = {
            'cloudinary': {
                name: patch['cloudinary'].get(name, existing.get(f'cloudinary.{name}', ''))
                for name in ('cloud_name', 'api_key', 'api_secret')
            },
            'gemini': {
                'api_key': patch['gemini'].get('api_key', existing.get('gemini.api_key', ''))
            },
        }
        descriptor, temporary = tempfile.mkstemp(prefix='.credential-', suffix='.tmp', dir=path.parent)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(merged, stream, indent=2)
                stream.write('\n')
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        refresh_provider_settings()
    except (OSError, ValueError):
        raise HTTPException(500, 'Could not save local credentials') from None
    response.headers['Cache-Control'] = 'no-store'
    return public_status(request)
