"""Main application entry point for Project LEX Backend."""
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi import HTTPException
from app import __version__
from app.config import settings
from app.routes.evidence import router as evidence_router
from app.routes.media import router as media_router
from app.routes.health import router as health_router
from app.routes.analyze import router as analyze_router
from app.routes.local_setup import router as local_setup_router
from app.routes.skills import router as skills_router
from app.routes.workflows import router as workflows_router
from app.routes.projects import router as projects_router
from app.routes.impact_stories import router as impact_stories_router
from app.routes.public_impact import public_router
from app.routes.discovery_campaign import router as discovery_campaign_router
from app.services.reviewer_auth import local_request, reviewer_for_authorization

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("lex.main")

# Initialize FastAPI application
app = FastAPI(
    title="Setowa — Evidence API",
    description=(
        "Setowa, built by Team LEX for Code Cubicle. "
        "Reviewable cleanup evidence, cautious image comparison, and grounded reports."
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


@app.middleware('http')
async def gate_remote_api(request: Request, call_next):
    """The remote pilot shares a single reviewer secret and never exposes API writes anonymously.

    Keep the guard even if a host accidentally leaves ENVIRONMENT=development.
    Loopback tests and the local demo retain their existing session behavior.
    """
    path = request.url.path
    test_client = (settings.ENVIRONMENT in {'development', 'test'} and
                   request.client is not None and request.client.host == 'testclient')
    if (path.startswith('/api/v1/') and path not in {'/api/v1/health', '/api/v1/ready'}
            and not (local_request(request) or test_client)):
        try:
            reviewer_for_authorization(request.headers.get('authorization'))
        except HTTPException as exc:
            return JSONResponse({'detail': exc.detail}, status_code=exc.status_code,
                                headers={'Cache-Control': 'no-store'})
    return await call_next(request)

# Register route modules
app.include_router(media_router)
app.include_router(projects_router)
app.include_router(impact_stories_router)
app.include_router(evidence_router)
app.include_router(health_router)
app.include_router(analyze_router)
app.include_router(local_setup_router)
app.include_router(skills_router)
app.include_router(workflows_router)
app.include_router(public_router)
app.include_router(discovery_campaign_router)
app.mount('/demo', StaticFiles(directory=Path(__file__).parent / 'demo', html=True), name='demo')
showcase_dir = Path(__file__).resolve().parents[2] / 'showcase'
if showcase_dir.is_dir():
    app.mount('/showcase', StaticFiles(directory=showcase_dir, html=True), name='showcase')


@app.get("/", tags=["System Root"], include_in_schema=False)
async def root(request: Request):
    """Open the workspace in browsers and preserve JSON metadata for API clients."""
    if 'text/html' in request.headers.get('accept', ''):
        return RedirectResponse('/demo/', status_code=307)
    return {
        'service': 'Setowa Evidence API',
        'team': 'Team LEX (Code Cubicle Hackathon)',
        'version': __version__,
        'status': 'online',
        'mock_mode': settings.USE_MOCK or not bool(settings.GEMINI_API_KEY),
        'docs_url': '/docs',
        'healthcheck': '/api/v1/health',
        'readiness': '/api/v1/ready',
    }


@app.get("/workspace", include_in_schema=False)
@app.get("/workspace/", include_in_schema=False)
async def workspace_redirect():
    """Redirect canonical workspace alias to /demo/."""
    return RedirectResponse('/demo/', status_code=307)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon_redirect():
    """Serve the Setowa mark for browsers that request the default icon path."""
    return RedirectResponse('/demo/favicon.svg', status_code=307)
