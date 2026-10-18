"""Security headers and the built interface served by FastAPI (phase 6)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.session import provide_session_factory
from app.main import create_app
from app.services.auth import hash_password


def test_every_response_carries_the_security_headers(client: TestClient) -> None:
    headers = client.get("/api/health").headers
    csp = headers["content-security-policy"]
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "https://tile.openstreetmap.org" in csp
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    # HSTS only once the app is served over HTTPS (production).
    assert "strict-transport-security" not in headers


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    """A tiny fake build of the interface."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>App Sport</html>")
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log('app')")
    (tmp_path / "sw.js").write_text("// service worker")
    (tmp_path.parent / "secret.txt").write_text("do not serve")
    return tmp_path


@pytest.fixture
def prod_client(
    monkeypatch: pytest.MonkeyPatch, session_factory: sessionmaker[Session], dist: Path
) -> Iterator[TestClient]:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_PASSWORD_HASH", hash_password("pw"))
    monkeypatch.setenv("FRONTEND_DIST", str(dist))
    get_settings.cache_clear()
    application = create_app()
    application.dependency_overrides[provide_session_factory] = lambda: session_factory
    with TestClient(application, base_url="https://testserver") as test_client:
        yield test_client


def test_production_serves_the_interface_on_every_page_address(prod_client: TestClient) -> None:
    page = prod_client.get("/sante/sommeil")
    assert page.status_code == 200
    assert "App Sport" in page.text
    assert page.headers["cache-control"] == "no-cache"
    asset = prod_client.get("/assets/index-abc123.js")
    assert "immutable" in asset.headers["cache-control"]
    assert prod_client.get("/sw.js").headers["cache-control"] == "no-cache"


def test_production_keeps_api_errors_and_never_serves_outside_the_build(
    prod_client: TestClient,
) -> None:
    assert prod_client.get("/api/does-not-exist").status_code == 404
    assert prod_client.get("/api/goals").status_code == 401
    # "../secret.txt" falls back to the page instead of reading outside dist.
    response = prod_client.get("/..%2Fsecret.txt")
    assert "do not serve" not in response.text


def test_production_adds_hsts_and_hides_the_api_docs(prod_client: TestClient) -> None:
    assert "max-age" in prod_client.get("/api/health").headers["strict-transport-security"]
    assert "App Sport" in prod_client.get("/docs").text  # just the interface, no Swagger
    assert prod_client.get("/openapi.json").headers["content-type"].startswith("text/html")
