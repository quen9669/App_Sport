"""Tests for token encryption."""

import pytest

from app.services.crypto import TokenCipher, TokenEncryptionError, generate_key


def test_encrypt_then_decrypt_returns_original() -> None:
    cipher = TokenCipher(generate_key())

    ciphertext = cipher.encrypt("my-secret-token")

    assert ciphertext != "my-secret-token"
    assert cipher.decrypt(ciphertext) == "my-secret-token"


def test_decrypt_with_another_key_fails_clearly() -> None:
    ciphertext = TokenCipher(generate_key()).encrypt("token")

    with pytest.raises(TokenEncryptionError, match="Reconnect"):
        TokenCipher(generate_key()).decrypt(ciphertext)


@pytest.mark.parametrize("bad_key", ["", "not-a-valid-key"])
def test_missing_or_invalid_key_is_rejected(bad_key: str) -> None:
    with pytest.raises(TokenEncryptionError):
        TokenCipher(bad_key)
