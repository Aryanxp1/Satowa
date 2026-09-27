"""Named private-demo tokens; secrets stay on the server."""
import hmac
import json
import secrets
import time

from fastapi import HTTPException, Request

from app.config import settings

LOCAL_COOKIE = 'lex_local_reviewer'
LOCAL_SESSIONS: dict[str, tuple[str, float]] = {}


def local_request(request: Request) -> bool:
    """Only the loopback-bound desktop demo may use browser session auth."""
    return (settings.ENVIRONMENT == 'development' and request.client is not None and
            request.client.host in {'127.0.0.1', '::1'} and
            request.url.hostname in {'127.0.0.1', 'localhost'}) or (
                settings.ENVIRONMENT == 'test' and request.client is not None and
                request.client.host == 'testclient')


def same_origin(request: Request) -> bool:
    """Check same-origin, treating localhost and 127.0.0.1 as equivalent.

    The local demo server binds to 127.0.0.1, but users open the browser via
    http://localhost:... — these must be considered the same loopback origin.
    """
    origin = request.headers.get('origin')
    if not origin:
        return False
    _LOOPBACK = {'localhost', '127.0.0.1', '::1'}

    def _normalize(url: str) -> str:
        """Replace loopback hostnames so they compare equal."""
        for alias in _LOOPBACK:
            url = url.replace(f'://{alias}:', '://localhost:').replace(f'://{alias}/', '://localhost/')
        return url.rstrip('/')

    return _normalize(origin) == _normalize(str(request.base_url))


def authorization_or_local_cookie(authorization: str | None, request: Request) -> str | None:
    if authorization:
        return authorization
    if not local_request(request):
        return None
    if request.method not in {'GET', 'HEAD', 'OPTIONS'} and not same_origin(request):
        return None
    actor = local_session_actor(request)
    token = reviewer_tokens().get(actor) if actor else None
    return f'Bearer {token}' if token else None


def local_session_actor(request: Request) -> str | None:
    if not local_request(request):
        return None
    session_id = request.cookies.get(LOCAL_COOKIE)
    session = LOCAL_SESSIONS.get(session_id or '')
    if not session:
        return None
    actor, expires_at = session
    if time.monotonic() >= expires_at:
        LOCAL_SESSIONS.pop(session_id, None)
        return None
    return actor


def new_local_session(actor: str) -> str:
    session_id = secrets.token_urlsafe(32)
    LOCAL_SESSIONS[session_id] = (actor, time.monotonic() + 8 * 60 * 60)
    return session_id


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
