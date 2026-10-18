"""Application settings, read from environment variables and the ``.env`` file.

Why pydantic-settings? It reads variables once, converts them to the right
Python type (``str``, ``int``, ``list``...) and fails loudly at startup if a
value is invalid, instead of crashing later in the middle of a request.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration values of the backend, with safe defaults for development."""

    # Look for a `.env` file in the backend folder first, then at the repo root.
    # Unknown variables (e.g. VITE_* used by the frontend) are ignored.
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_timezone: str = "Europe/Luxembourg"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    database_url: str = "sqlite:///./data/app_sport.db"
    # Comma-separated in the env file, e.g. "http://localhost:5173,http://127.0.0.1:5173".
    cors_origins: str = Field(default="http://localhost:5173")
    # Where the browser is sent back after connecting Strava.
    frontend_url: str = "http://localhost:5173"

    # --- Strava (https://www.strava.com/settings/api) ---
    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_redirect_uri: str = "http://localhost:8000/api/strava/callback"

    # --- Security ---
    # Fernet key used to encrypt OAuth tokens before they are written to the database.
    token_encryption_key: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        """Return CORS origins as a clean list (the env file stores them as one string)."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the settings, built only once.

    ``lru_cache`` remembers the result of the first call, so the ``.env`` file is
    read a single time. Tests can call ``get_settings.cache_clear()`` to reload.
    """
    return Settings()
