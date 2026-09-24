"""Named private-demo tokens; secrets stay on the server."""
import hmac
import json

from fastapi import HTTPException

from app.config import settings


def reviewer_tokens():
    raw = settings.REVIEWER_TOKENS.get_secret_value()
    if not raw:
        return {}
    try:
        configured = json.loads(raw)
    except (ValueError, TypeError):
        raise HTTPException(503, 'Reviewer authentication is misconfigured') from None
    if not isinstance(configured, dict) or any(
        not isinstance(name, str) or not name.strip() or
        not isinstance(token, str) or not token
        for name, token in configured.items()
    ) or len(set(configured.values())) != len(configured) or any(
        hmac.compare_digest(token, settings.MEDIA_UPLOAD_TOKEN.get_secret_value())
        for token in configured.values()
    ):
        raise HTTPException(503, 'Reviewer authentication is misconfigured')
    return configured


def reviewer_for_authorization(authorization):
    configured = reviewer_tokens()
    if not configured:
        raise HTTPException(503, 'Reviewer authentication is not configured')
    prefix = 'Bearer '
    if not authorization or not authorization.startswith(prefix):
        raise HTTPException(401, 'Reviewer token required')
    candidate = authorization[len(prefix):]
    for name, token in configured.items():
        if hmac.compare_digest(candidate.encode(), token.encode()):
            return name
    raise HTTPException(403, 'A named reviewer token is required')
