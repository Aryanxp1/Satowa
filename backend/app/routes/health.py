"""Health and readiness check endpoints."""
from fastapi import APIRouter, Header, Response
from app import __version__
from app.config import settings
from app.schemas.api import HealthResponse, ReadinessResponse
from app.services import evidence_store as store
from app.services.env_validator import validate_environment
from app.services.reviewer_auth import reviewer_configuration_status, reviewer_for_authorization

router = APIRouter(prefix="/api/v1", tags=["System Health"])


@router.get("/pilot/session")
def pilot_session(response: Response, authorization: str | None = Header(default=None)):
    """Validate a named reviewer token without echoing it or persisting it in the browser."""
    actor = reviewer_for_authorization(authorization)
    response.headers['Cache-Control'] = 'no-store'
    return {
        'reviewer': actor,
        'reviewer_ready': True,
        'cloudinary_ready': bool(settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY
                                 and settings.CLOUDINARY_API_SECRET.get_secret_value()),
        'gemini_ready': bool(settings.GEMINI_API_KEY),
    }


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Returns the operational status and active configuration mode of the service."""
    return HealthResponse(
        status="healthy",
        version=__version__,
        environment=settings.ENVIRONMENT,
        mock_mode=settings.USE_MOCK or not bool(settings.GEMINI_API_KEY),
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check(response: Response):
    """Returns readiness probe status checking database connectivity and provider configuration."""
    db_status = "ready"
    try:
        with store.connection() as db:
            row = store.one(db, "SELECT 1 as ping")
            if not row or row.get("ping") != 1:
                db_status = "degraded"
    except Exception:
        db_status = "unavailable"

    env_report = validate_environment(settings)
    cloudinary_status = "configured" if env_report["cloudinary_ready"] else "missing"
    gemini_status = "configured" if env_report["gemini_ready"] else "missing"
    reviewer_status = reviewer_configuration_status()

    pilot = settings.ENVIRONMENT.lower() == 'pilot'
    overall_status = "ready" if db_status == "ready" and (
        not pilot or (cloudinary_status == 'configured' and gemini_status == 'configured'
                      and reviewer_status == 'configured' and not settings.USE_MOCK)
    ) else "degraded"
    if overall_status == 'degraded':
        response.status_code = 503
    response.headers['Cache-Control'] = 'no-store'

    return ReadinessResponse(
        status=overall_status,
        application="ready" if db_status == 'ready' else 'degraded',
        database=db_status,
        cloudinary=cloudinary_status,
        gemini=gemini_status,
        reviewer_auth=reviewer_status,
        environment=settings.ENVIRONMENT,
        mode=env_report["mode"],
    )
