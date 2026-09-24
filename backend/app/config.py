"""Configuration settings for Project LEX Backend."""
import os
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


settings = Settings()
