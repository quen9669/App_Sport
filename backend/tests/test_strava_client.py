"""Tests for the Strava HTTP client against a mocked API (respx intercepts httpx)."""

import httpx
import pytest
import respx

from app.integrations.strava.client import API_BASE_URL, StravaApiError, StravaClient
from app.integrations.strava.rate_limit import RateLimiter
from tests.fixtures.strava import BASE_TIME, make_activity, make_streams, rate_limit_headers

ACTIVITIES_URL = f"{API_BASE_URL}/athlete/activities"


def make_client(http: httpx.Client, sleeps: list[float]) -> StravaClient:
    return StravaClient(
        http,
        access_token=lambda: "token-abc",
        rate_limiter=RateLimiter(sleep=sleeps.append),
        sleep=sleeps.append,
    )


@respx.mock
def test_sends_bearer_token_and_params() -> None:
    route = respx.get(ACTIVITIES_URL).mock(
        return_value=httpx.Response(
            200, json=[make_activity(1, BASE_TIME)], headers=rate_limit_headers()
        )
    )

    with httpx.Client() as http:
        items = make_client(http, []).list_activities(after=100, page=2, per_page=50)

    assert len(items) == 1
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer token-abc"
    assert request.url.params["after"] == "100"
    assert request.url.params["page"] == "2"


@respx.mock
def test_retries_after_429_once_window_resets() -> None:
    respx.get(ACTIVITIES_URL).mock(
        side_effect=[
            httpx.Response(429, headers=rate_limit_headers(short_usage=100)),
            httpx.Response(200, json=[], headers=rate_limit_headers()),
        ]
    )
    sleeps: list[float] = []

    with httpx.Client() as http:
        assert make_client(http, sleeps).list_activities() == []

    assert len(sleeps) == 1  # waited for the next 15-minute window


@respx.mock
def test_retries_server_errors_with_backoff_then_gives_up() -> None:
    respx.get(ACTIVITIES_URL).mock(return_value=httpx.Response(503))
    sleeps: list[float] = []

    with httpx.Client() as http, pytest.raises(StravaApiError) as error:
        make_client(http, sleeps).list_activities()

    assert error.value.status_code == 503
    assert sleeps == [1, 2, 4]  # exponential backoff


@respx.mock
def test_client_errors_are_not_retried() -> None:
    route = respx.get(ACTIVITIES_URL).mock(return_value=httpx.Response(401))

    with httpx.Client() as http, pytest.raises(StravaApiError):
        make_client(http, []).list_activities()

    assert route.call_count == 1


@respx.mock
def test_streams_return_empty_dict_when_activity_has_none() -> None:
    respx.get(f"{API_BASE_URL}/activities/42/streams").mock(return_value=httpx.Response(404))

    with httpx.Client() as http:
        assert make_client(http, []).get_activity_streams("42") == {}


@respx.mock
def test_streams_are_requested_keyed_by_type() -> None:
    route = respx.get(f"{API_BASE_URL}/activities/42/streams").mock(
        return_value=httpx.Response(200, json=make_streams())
    )

    with httpx.Client() as http:
        streams = make_client(http, []).get_activity_streams("42")

    assert "heartrate" in streams
    assert route.calls.last.request.url.params["key_by_type"] == "true"
