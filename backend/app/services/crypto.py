"""Encryption of OAuth tokens before they are stored in the database.

We use Fernet (from the ``cryptography`` library): symmetric encryption with
authentication, so a modified ciphertext is detected instead of silently
decrypted into garbage. The key comes from ``TOKEN_ENCRYPTION_KEY`` in ``.env``.
"""

from cryptography.fernet import Fernet, InvalidToken


class TokenEncryptionError(RuntimeError):
    """Raised when the key is missing/invalid or a value cannot be decrypted."""


class TokenCipher:
    """Encrypt and decrypt short secrets (tokens) with one Fernet key."""

    def __init__(self, key: str) -> None:
        if not key:
            raise TokenEncryptionError(
                "TOKEN_ENCRYPTION_KEY is empty. Generate one (see .env.example) and add it to .env."
            )
        try:
            self._fernet = Fernet(key.encode())
        except ValueError:
            # "from None" hides the original error, whose message could echo part of the key.
            raise TokenEncryptionError("TOKEN_ENCRYPTION_KEY is not a valid Fernet key.") from None

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            raise TokenEncryptionError(
                "Could not decrypt a stored token: TOKEN_ENCRYPTION_KEY probably changed. "
                "Reconnect the service."
            ) from None


def generate_key() -> str:
    """Return a new random key, to paste into ``.env``."""
    return Fernet.generate_key().decode()
