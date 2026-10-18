"""Serving the built interface from FastAPI (production, phase 6).

In development the Vite server (port 5173) serves the interface. In production
``npm run build`` writes it to ``frontend/dist`` and the backend serves it too:
one server, one port, and the API is on the same address (no CORS needed).
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

# Files that must never be kept stale by the browser: the page itself and the
# service worker (which decides when a new version of the app is installed).
NO_CACHE = {"index.html", "sw.js", "registerSW.js", "manifest.webmanifest"}


def mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve ``dist``: real files as they are, every other address gets index.html
    (react-router then shows the right page, e.g. /sante/sommeil)."""
    root = dist.resolve()
    index = root / "index.html"
    if not index.is_file():
        raise RuntimeError(f"FRONTEND_DIST={dist}: no index.html (run `npm run build`).")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path.startswith("api/") or path == "api":
            raise HTTPException(404)  # unknown API route: a real 404, not the page
        file = (root / path).resolve()
        # is_relative_to: "../../.env" must never escape the dist folder.
        if path and file.is_relative_to(root) and file.is_file():
            return FileResponse(file, headers=_cache_headers(file.name, path))
        return FileResponse(index, headers=_cache_headers("index.html", ""))


def _cache_headers(name: str, path: str) -> dict[str, str]:
    if name in NO_CACHE:
        return {"Cache-Control": "no-cache"}
    if path.startswith("assets/"):
        # Vite puts a content hash in these names: a new version = a new name.
        return {"Cache-Control": "public, max-age=31536000, immutable"}
    return {"Cache-Control": "public, max-age=3600"}
