"""Health check endpoints."""
from fastapi import APIRouter
from app import __version__
from app.config import settings
from app.schemas.api import HealthResponse

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
