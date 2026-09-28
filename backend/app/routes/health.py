"""Health and readiness check endpoints."""
from fastapi import APIRouter
from app import __version__
from app.config import settings
from app.schemas.api import HealthResponse, ReadinessResponse
from app.services import evidence_store as store
from app.services.env_validator import validate_environment

router = APIRouter(prefix="/api/v1", tags=["System Health"])


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
async def readiness_check():
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

    overall_status = "ready" if db_status == "ready" else "degraded"

    return ReadinessResponse(
        status=overall_status,
        application="ready",
        database=db_status,
        cloudinary=cloudinary_status,
        gemini=gemini_status,
        environment=settings.ENVIRONMENT,
        mode=env_report["mode"],
    )
