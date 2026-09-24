"""Main application entry point for Project LEX Backend."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app import __version__
from app.config import settings
from app.routes.evidence import router as evidence_router
from app.routes.media import router as media_router
from app.routes.health import router as health_router
from app.routes.analyze import router as analyze_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("lex.main")

# Initialize FastAPI application
app = FastAPI(
    title="Project LEX — AI & Analytics Engine",
    description=(
        "Core Backend & AI Inference Service for Team LEX at Code Cubicle Hackathon. "
        "Engineered for sub-second latency, multi-modal reasoning, and resilient fallback mocks."
    ),
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if settings.cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(media_router)
app.include_router(evidence_router)
app.include_router(health_router)
app.include_router(analyze_router)


@app.get("/", tags=["System Root"])
async def root():
    """Service metadata and interactive documentation links."""
    return {
        "service": "Project LEX Backend API",
        "team": "Team LEX (Code Cubicle Hackathon)",
        "version": __version__,
        "status": "online",
        "mock_mode": settings.USE_MOCK or not bool(settings.GEMINI_API_KEY),
        "docs_url": "/docs",
        "healthcheck": "/api/v1/health",
    }
