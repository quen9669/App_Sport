"""Store Strava tokens encrypted and always hand out a valid access token."""

from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models import SourceCredential
from app.db.models.enums import DataSource
from app.db.types import utc_now
from app.integrations.strava.oauth import StravaOAuth, TokenSet
from app.repositories import credentials as credentials_repo
from app.services.crypto import TokenCipher

# Refresh a bit before the real expiry, so a token never expires mid-sync.
REFRESH_MARGIN = timedelta(minutes=5)


class StravaNotConnectedError(RuntimeError):
    """No Strava account connected yet (or it was disconnected)."""


class StravaCredentialService:
    def __init__(
        self,
        db: Session,
        cipher: TokenCipher,
        oauth: StravaOAuth,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self._db = db
        self._cipher = cipher
        self._oauth = oauth
        self._now = now

    def save_tokens(self, tokens: TokenSet, scope: str | None = None) -> SourceCredential:
        """Encrypt and store tokens (first connection or after a refresh)."""
        credential = credentials_repo.get_credential(self._db, DataSource.STRAVA)
        if credential is None:
            credential = SourceCredential(source=DataSource.STRAVA)
            self._db.add(credential)
        credential.access_token_encrypted = self._cipher.encrypt(tokens.access_token)
        credential.refresh_token_encrypted = self._cipher.encrypt(tokens.refresh_token)
        credential.expires_at = tokens.expires_at_datetime
        if scope is not None:
            credential.scope = scope
        if tokens.athlete is not None:
            credential.external_account_id = str(tokens.athlete.id)
        self._db.commit()
        return credential

    def get_access_token(self) -> str:
        """Return a valid access token, refreshing it first if it (almost) expired."""
        credential = credentials_repo.get_credential(self._db, DataSource.STRAVA)
        if credential is None:
            raise StravaNotConnectedError("Strava is not connected.")
        expires_at = credential.expires_at
        if expires_at is not None and expires_at - REFRESH_MARGIN > self._now():
            return self._cipher.decrypt(credential.access_token_encrypted)

        if not credential.refresh_token_encrypted:
            raise StravaNotConnectedError("No refresh token stored; reconnect Strava.")
        refresh_token = self._cipher.decrypt(credential.refresh_token_encrypted)
        # Strava may return a *new* refresh token: always store the latest one.
        tokens = self._oauth.refresh(refresh_token)
        self.save_tokens(tokens)
        return tokens.access_token

    def disconnect(self) -> None:
        """Revoke access on Strava (best effort) and delete our stored tokens."""
        credential = credentials_repo.get_credential(self._db, DataSource.STRAVA)
        if credential is None:
            return
        try:
            self._oauth.deauthorize(self._cipher.decrypt(credential.access_token_encrypted))
        finally:
            credentials_repo.delete_credential(self._db, DataSource.STRAVA)
