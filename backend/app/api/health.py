"""Health check route: lets the frontend (and later monitoring) know the API is alive."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Shape of the JSON returned by ``GET /api/health``.

    Declaring it as a Pydantic model gives us validation and automatic
    documentation on http://localhost:8000/docs.
    """

    status: Literal["ok"]
    version: str


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return a fixed "ok" payload. If this answers, the server is running."""
    return HealthResponse(status="ok", version="0.1.0")
