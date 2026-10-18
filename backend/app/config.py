"""Application settings, read from environment variables and the ``.env`` file.

Why pydantic-settings? It reads variables once, converts them to the right
Python type (``str``, ``int``, ``list``...) and fails loudly at startup if a
value is invalid, instead of crashing later in the middle of a request.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

CoachProvider = Literal["gemini", "anthropic"]


@dataclass(frozen=True)
class ModelDefaults:
    """What a provider uses when COACH_MODEL / COACH_*_PRICE_* are left empty in .env."""

    model: str
    light_model: str  # cheaper model for small jobs (summaries)
    # US dollars per million tokens: (input, output) for the main and the light model.
    prices: tuple[float, float]
    light_prices: tuple[float, float]


COACH_DEFAULTS: dict[CoachProvider, ModelDefaults] = {
    # https://ai.google.dev/gemini-api/docs/pricing. Gemini 3.8 Flash costs half until
    # 31 Dec 2026 (0.75 / 3.75); the full price is used so the budget never underestimates.
    "gemini": ModelDefaults("gemini-3.8-flash", "gemini-3.5-flash-lite", (1.5, 7.5), (0.3, 2.5)),
    # https://www.anthropic.com/pricing
    "anthropic": ModelDefaults("claude-sonnet-5-5", "claude-haiku-5-5", (3.0, 15.0), (1.0, 5.0)),
}


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
    # Keys stay in .env (never in the code, never logged). Both empty = coaches disabled.
    # With a Gemini key the coaches use Gemini, else Claude; COACH_PROVIDER forces one.
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    coach_provider: CoachProvider | None = None
    # Models are configuration, not code: empty means the provider's defaults above.
    coach_model: str = ""
    coach_light_model: str = ""
    coach_monthly_budget_eur: float = Field(default=10, ge=0, le=1000)
    # Prices to estimate costs, in US dollars per million tokens (empty = defaults above).
    coach_price_input_usd: float | None = None
    coach_price_output_usd: float | None = None
    coach_light_price_input_usd: float | None = None
    coach_light_price_output_usd: float | None = None
    usd_to_eur: float = 0.92

    @field_validator(
        "coach_provider",
        "coach_price_input_usd",
        "coach_price_output_usd",
        "coach_light_price_input_usd",
        "coach_light_price_output_usd",
        mode="before",
    )
    @classmethod
    def _empty_is_default(cls, value: object) -> object:
        """``COACH_PROVIDER=`` (empty in .env) means "not set", not an invalid value."""
        return None if value == "" else value

    @property
    def provider(self) -> CoachProvider | None:
        """The model provider in use, or None when no key is set."""
        if self.coach_provider:
            return self.coach_provider if self.api_key_for(self.coach_provider) else None
        if self.gemini_api_key:
            return "gemini"
        return "anthropic" if self.anthropic_api_key else None

    def api_key_for(self, provider: CoachProvider) -> str:
        return self.gemini_api_key if provider == "gemini" else self.anthropic_api_key

    @property
    def _defaults(self) -> ModelDefaults:
        return COACH_DEFAULTS[self.provider or "gemini"]

    @property
    def main_model(self) -> str:
        return self.coach_model or self._defaults.model

    @property
    def light_model(self) -> str:
        return self.coach_light_model or self._defaults.light_model

    def prices(self, model: str) -> tuple[float, float]:
        """(input, output) price of a model, in dollars per million tokens."""
        if model == self.light_model:
            default_in, default_out = self._defaults.light_prices
            given = (self.coach_light_price_input_usd, self.coach_light_price_output_usd)
        else:
            default_in, default_out = self._defaults.prices
            given = (self.coach_price_input_usd, self.coach_price_output_usd)
        return (
            default_in if given[0] is None else given[0],
            default_out if given[1] is None else given[1],
        )

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
