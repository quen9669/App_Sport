"""Shared pytest fixtures. pytest loads this file automatically before the tests."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Give each test an HTTP client talking to a fresh app, without a real server."""
    with TestClient(create_app()) as test_client:
        yield test_client
