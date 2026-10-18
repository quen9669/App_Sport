"""Application settings, read from environment variables and the ``.env`` file.

Why pydantic-settings? It reads variables once, converts them to the right
Python type (``str``, ``int``, ``list``...) and fails loudly at startup if a
value is invalid, instead of crashing later in the middle of a request.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Used when COACH_MODEL / COACH_LIGHT_MODEL are left empty in .env.
DEFAULT_COACH_MODEL = "claude-sonnet-5-5"
DEFAULT_COACH_LIGHT_MODEL = "claude-haiku-5-5"


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

    # --- Garmin (unofficial `garminconnect` library) ---
    garmin_email: str = ""
    garmin_password: str = ""
    # Folder where the Garmin session tokens are saved, outside the repository.
    garmin_tokenstore: str = "~/.app_sport/garmin"
    # How many days back the very first Garmin sync goes.
    garmin_initial_days: int = Field(default=90, ge=1, le=3650)

    # --- Scheduled synchronisation ---
    scheduler_enabled: bool = True
    sync_interval_hours: float = Field(default=3, gt=0, le=48)

    # --- Security ---
    # Fernet key used to encrypt OAuth tokens before they are written to the database.
    token_encryption_key: str = ""

    # --- AI coaches (phase 5) ---
    # The key stays in .env (never in the code, never logged). Empty = coaches disabled.
    anthropic_api_key: str = ""
    # Models are configuration, not code: empty means the defaults below.
    coach_model: str = ""
    coach_light_model: str = ""  # cheaper model for small jobs (summaries)
    coach_monthly_budget_eur: float = Field(default=10, ge=0, le=1000)
    # Prices to estimate costs, in US dollars per million tokens (check
    # https://www.anthropic.com/pricing if they change). Cache reads cost 10 %
    # of the input price, cache writes 125 %.
    coach_price_input_usd: float = 3.0
    coach_price_output_usd: float = 15.0
    coach_light_price_input_usd: float = 1.0
    coach_light_price_output_usd: float = 5.0
    usd_to_eur: float = 0.92

    @property
    def main_model(self) -> str:
        return self.coach_model or DEFAULT_COACH_MODEL

    @property
    def light_model(self) -> str:
        return self.coach_light_model or DEFAULT_COACH_LIGHT_MODEL

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
