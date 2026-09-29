"""Environment and Production Configuration Validator.

Provides safe configuration audits and readiness checks without ever exposing secret values.
"""
from typing import Dict, Any, List, Tuple
from app.config import Settings


def check_var_status(val: Any) -> str:
    """Classify variable status safely without revealing contents."""
    if val is None:
        return "missing"
    if isinstance(val, str):
        cleaned = val.strip()
        if not cleaned:
            return "missing"
        return "configured"
    # SecretStr or other objects
    if hasattr(val, "get_secret_value"):
        cleaned = val.get_secret_value().strip()
        if not cleaned:
            return "missing"
        return "configured"
    return "configured"


def validate_environment(settings: Settings) -> Dict[str, Any]:
    """Audit core environment variables without exposing secret values."""
    vars_status = {
        "CLOUDINARY_CLOUD_NAME": check_var_status(settings.CLOUDINARY_CLOUD_NAME),
        "CLOUDINARY_API_KEY": check_var_status(settings.CLOUDINARY_API_KEY),
        "CLOUDINARY_API_SECRET": check_var_status(settings.CLOUDINARY_API_SECRET),
        "GEMINI_API_KEY": check_var_status(settings.GEMINI_API_KEY),
        "NVIDIA_API_KEY": check_var_status(settings.NVIDIA_API_KEY),
        "ENVIRONMENT": settings.ENVIRONMENT,
        "USE_MOCK": settings.USE_MOCK,
    }

    missing = [
        k for k in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")
        if vars_status[k] == "missing"
    ]
    cloudinary_ready = all(
        vars_status[k] == "configured"
        for k in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")
    )
    gemini_ready = vars_status["GEMINI_API_KEY"] == "configured"
    is_complete = len(missing) == 0

    return {
        "status": vars_status,
        "variables": vars_status,
        "is_complete": is_complete,
        "missing_variables": missing,
        "cloudinary_ready": cloudinary_ready,
        "gemini_ready": gemini_ready,
        "nvidia_ready": vars_status["NVIDIA_API_KEY"] == "configured",
        "environment": settings.ENVIRONMENT,
        "mode": "mock" if settings.USE_MOCK else ("live" if (vars_status["NVIDIA_API_KEY"] == "configured" if settings.AI_PROVIDER == "nvidia" else gemini_ready) else "manual"),
    }


def validate_production_readiness(settings: Settings) -> Tuple[bool, List[str]]:
    """Validate whether current configuration is safe and ready for production deployment.
    
    Returns (is_ready, list_of_issues).
    """
    issues: List[str] = []

    is_prod = settings.ENVIRONMENT.lower() in ("production", "prod")

    # Cloudinary checks
    if check_var_status(settings.CLOUDINARY_CLOUD_NAME) == "missing":
        issues.append("CLOUDINARY_CLOUD_NAME is not configured")
    if check_var_status(settings.CLOUDINARY_API_KEY) == "missing":
        issues.append("CLOUDINARY_API_KEY is not configured")
    if check_var_status(settings.CLOUDINARY_API_SECRET) == "missing":
        issues.append("CLOUDINARY_API_SECRET is not configured")

    # External AI is optional: manual review and lexical search remain available.

    # Production-specific safety constraints
    if is_prod:
        if settings.USE_MOCK:
            issues.append("USE_MOCK cannot be enabled in production environment")
        
        origins = settings.cors_origins
        if "*" in origins or any("localhost" in o for o in origins):
            issues.append("CORS allowed_origins must not contain '*' or localhost in production")

        if not settings.DATABASE_URL.get_secret_value():
            issues.append("Production requires durable DATABASE_URL; ephemeral SQLite is pilot-only")
        issues.append("Production account authorization and release verification are not enabled; use pilot mode")

    is_ready = len(issues) == 0
    return is_ready, issues
