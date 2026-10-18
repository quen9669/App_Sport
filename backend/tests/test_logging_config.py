"""Tests for the secret-redacting log filter: tokens must never reach the logs."""

import logging

import pytest

from app.logging_config import SecretRedactingFilter, redact_secrets


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("access_token=abc123", "access_token=***"),
        ('{"refresh_token": "xyz"}', '{"refresh_token": "***"}'),
        ("Authorization: Bearer secret.jwt.value", "Authorization: Bearer ***"),
        ("password=hunter2&user=me", "password=***&user=me"),
        ("nothing secret here", "nothing secret here"),
    ],
)
def test_redact_secrets(raw: str, expected: str) -> None:
    assert redact_secrets(raw) == expected


def test_filter_redacts_secrets_passed_as_arguments() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="token refreshed: %s",
        args=("access_token=abc123",),
        exc_info=None,
    )

    SecretRedactingFilter().filter(record)

    assert record.getMessage() == "token refreshed: access_token=***"
