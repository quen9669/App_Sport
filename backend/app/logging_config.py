"""Logging setup, with a filter that hides secrets.

Health data and API tokens are sensitive: even if some code accidentally logs a
token, this filter replaces it with ``***`` before the line is written.
"""

import logging
import re

# Patterns that look like secrets: "access_token=...", "Authorization: Bearer ...",
# "password": "...", and so on. The value part (group 2) is replaced.
_SECRET_PATTERN = re.compile(
    r"(?i)((?:access_token|refresh_token|client_secret|password|api_key|authorization)"
    r"[\"']?\s*[:=]\s*[\"']?(?:bearer\s+)?)([^\s\"',&]+)"
)


def redact_secrets(message: str) -> str:
    """Return ``message`` with every secret-looking value replaced by ``***``."""
    return _SECRET_PATTERN.sub(r"\1***", message)


class SecretRedactingFilter(logging.Filter):
    """Logging filter that rewrites each record's message through :func:`redact_secrets`."""

    def filter(self, record: logging.LogRecord) -> bool:
        # getMessage() merges the message template with its arguments first,
        # so secrets passed as arguments (logger.info("%s", token)) are caught too.
        record.msg = redact_secrets(record.getMessage())
        record.args = None
        return True  # True = keep the record (we only modify it, never drop it).


def configure_logging(level: str) -> None:
    """Configure the root logger once, at application startup."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(SecretRedactingFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
