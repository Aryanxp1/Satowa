"""Routes module export."""
from app.routes.health import router as health_router
from app.routes.analyze import router as analyze_router

__all__ = ["health_router", "analyze_router"]
