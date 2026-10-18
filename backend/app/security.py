"""Security headers added to every response (phase 6).

They tell the browser what the app is allowed to do, so that even if some
malicious content ever got into a page, it could not load scripts from
elsewhere, send data to another site, or show the app inside another site.
"""

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# Content Security Policy: everything comes from the app itself, except the map
# background (OpenStreetMap tiles). No third-party script, ever.
# 'unsafe-inline' is only allowed for styles: the map and chart libraries set
# style attributes on their elements; scripts stay strictly 'self'.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob: https://tile.openstreetmap.org",
        "font-src 'self' data:",
        "connect-src 'self'",
        "worker-src 'self'",
        "manifest-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)

BASE_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    # Never guess a file type from its content (a "text" file run as a script...).
    "X-Content-Type-Options": "nosniff",
    # Other sites never learn which page of the app a link came from.
    "Referrer-Policy": "same-origin",
    # Old browsers: refuse to be shown inside a frame (CSP frame-ancestors for new ones).
    "X-Frame-Options": "DENY",
    # The app needs none of these device features.
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
}

# HTTPS only for a year, once the app is served over HTTPS (production).
HSTS = "max-age=31536000"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, https: bool) -> None:
        super().__init__(app)
        self.headers = dict(BASE_HEADERS)
        if https:
            self.headers["Strict-Transport-Security"] = HSTS

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for name, value in self.headers.items():
            response.headers.setdefault(name, value)
        return response
