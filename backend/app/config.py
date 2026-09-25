"""Configuration settings for Project LEX Backend."""
import json
import os
from pathlib import Path
from typing import List
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or defaults."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ENVIRONMENT: str = "development"

    # AI Service Settings
    USE_MOCK: bool = True
    AI_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Cloudinary uploads are independent of AI mock mode.
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: SecretStr = SecretStr("")
    MEDIA_UPLOAD_TOKEN: SecretStr = SecretStr("")
    REVIEWER_TOKENS: SecretStr = SecretStr("")

    # SQLite persistence for sites, visits, evidence, and review history.
    LEX_DB_PATH: str = "./lex.sqlite3"
    GEMINI_VISION_MODEL: str = "gemini-2.5-flash"

    # CORS origins
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:8080,https://lex-app.vercel.app"

    @property
    def cors_origins(self) -> List[str]:
        """Return parsed list of allowed CORS origins."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


def load_local_credentials(path: Path) -> dict:
    """Read the gitignored local JSON template without exposing secret values."""
    if not path.is_file():
        return {}
    try:
        credentials = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError("credential.json is unreadable or invalid JSON") from None
    if not isinstance(credentials, dict):
        raise ValueError("credential.json must contain a JSON object")
    result = {}
    for section, names in {
        "cloudinary": ("cloud_name", "api_key", "api_secret"),
        "gemini": ("api_key",),
    }.items():
        values = credentials.get(section, {})
        if not isinstance(values, dict):
            raise ValueError(f"credential.json section {section} must be an object")
        for name in names:
            value = values.get(name, "")
            if not isinstance(value, str):
                raise ValueError(f"credential.json field {section}.{name} must be a string")
            result[f"{section}.{name}"] = value.strip()
    return result


def apply_local_credentials(target: Settings, credentials: dict) -> None:
    """Environment and .env values win; JSON fills only empty settings."""
    for key, field in (
        ("cloudinary.cloud_name", "CLOUDINARY_CLOUD_NAME"),
        ("cloudinary.api_key", "CLOUDINARY_API_KEY"),
        ("gemini.api_key", "GEMINI_API_KEY"),
    ):
        if not getattr(target, field) and credentials.get(key):
            setattr(target, field, credentials[key])
    secret = credentials.get("cloudinary.api_secret")
    if secret and not target.CLOUDINARY_API_SECRET.get_secret_value():
        target.CLOUDINARY_API_SECRET = SecretStr(secret)


def credential_path() -> Path:
    return Path(__file__).resolve().parents[2] / "credential.json"


def refresh_provider_settings() -> None:
    """Apply a saved local credential edit without requiring a server restart."""
    fresh = Settings()
    apply_local_credentials(fresh, load_local_credentials(credential_path()))
    for field in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY",
                  "CLOUDINARY_API_SECRET", "GEMINI_API_KEY"):
        setattr(settings, field, getattr(fresh, field))


settings = Settings()
apply_local_credentials(settings, load_local_credentials(credential_path()))
