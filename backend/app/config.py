"""Application settings, read from environment variables and the ``.env`` file.

Why pydantic-settings? It reads variables once, converts them to the right
Python type (``str``, ``int``, ``list``...) and fails loudly at startup if a
value is invalid, instead of crashing later in the middle of a request.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The model is imposed by FRANKS in OmniRoute (key app-sport): by default the app
# names none and OmniRoute picks its own. COACH_MODEL / COACH_LIGHT_MODEL only
# exist to override that. The key is paid, so prompts are not kept (R-08).
DEFAULT_MODEL = ""
DEFAULT_LIGHT_MODEL = ""
# US dollars per million tokens, (input, output), only to ESTIMATE each call's
# cost (https://www.anthropic.com/pricing). The budget itself lives in OmniRoute.
DEFAULT_PRICES = (3.0, 15.0)
DEFAULT_LIGHT_PRICES = (1.0, 5.0)


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
    # Argon2 fingerprint of the app password (`make set-password`), never the password
    # itself. Empty = no login screen, only allowed outside production (phase 6).
    app_password_hash: str = ""
    # How long a device stays signed in.
    session_days: int = Field(default=30, ge=1, le=365)

    # --- Production (phase 6) ---
    # Built interface (`npm run build`) served by FastAPI itself: one server, one port.
    # Empty = not served (development uses the Vite server on port 5173).
    frontend_dist: str = ""
    # No backup of its own (référentiel R-11, SPT-09): the server's nightly archive
    # copies the whole `app-sport-data` volume, 7 days on Google Drive.
    # Address of the "App Sport" Grafana dashboard, for the button of the Monitoring
    # page. Empty = no button. Grafana is only reachable inside the tailnet.
    grafana_url: str = ""
    # Healthchecks check pinged after each scheduled sync (référentiel R-26). The URL
    # is a secret of its own: it comes from the vault (apps/app-sport/HEALTHCHECKS_URL).
    healthchecks_url: str = ""

    # --- AI coaches (phase 5) ---
    # Only through OmniRoute (référentiel R-05). The key comes from the OpenBao
    # vault (apps/app-sport/OMNIROUTE_API_KEY), never from a file; never logged.
    # Empty = coaches disabled. The monthly budget is set in OmniRoute, never here (R-07).
    omniroute_api_key: str = ""
    omniroute_base_url: str = "http://omniroute:20128/v1"
    # Models are configuration, not code: empty means the defaults above.
    coach_model: str = ""
    coach_light_model: str = ""
    # Prices to estimate costs, in US dollars per million tokens (empty = defaults above).
    coach_price_input_usd: float | None = None
    coach_price_output_usd: float | None = None
    coach_light_price_input_usd: float | None = None
    coach_light_price_output_usd: float | None = None
    usd_to_eur: float = 0.92

    @field_validator(
        "coach_price_input_usd",
        "coach_price_output_usd",
        "coach_light_price_input_usd",
        "coach_light_price_output_usd",
        mode="before",
    )
    @classmethod
    def _empty_is_default(cls, value: object) -> object:
        """``COACH_PRICE_INPUT_USD=`` (empty) means "not set", not an invalid value."""
        return None if value == "" else value

    @property
    def auth_enabled(self) -> bool:
        """The login screen is on as soon as a password has been set."""
        return bool(self.app_password_hash)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def coach_enabled(self) -> bool:
        """The coaches work as soon as the app has its OmniRoute key."""
        return bool(self.omniroute_api_key)

    @property
    def main_model(self) -> str:
        return self.coach_model or DEFAULT_MODEL

    @property
    def light_model(self) -> str:
        return self.coach_light_model or DEFAULT_LIGHT_MODEL

    def prices(self, model: str) -> tuple[float, float]:
        """(input, output) price of a model, in dollars per million tokens."""
        if model == self.light_model and self.light_model != self.main_model:
            default_in, default_out = DEFAULT_LIGHT_PRICES
            given = (self.coach_light_price_input_usd, self.coach_light_price_output_usd)
        else:
            default_in, default_out = DEFAULT_PRICES
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
