"""The common contract (SPT-06): /health and /vitrine.json, and the Healthchecks ping."""

from datetime import UTC, datetime

import httpx
import respx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Activity
from app.services.jobs import ping_healthchecks


def test_health_in_the_common_format(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert (body["app"], body["code"], body["etat"]) == ("app-sport", "EXP-04", "en_service")
    names = [check["nom"] for check in body["controles"]]
    assert names == ["base", "synchro_garmin", "synchro_strava", "coach", "memoire"]


def test_vitrine_has_aggregates_only(client: TestClient, db: Session) -> None:
    start = datetime(2026, 11, 1, 8, tzinfo=UTC)
    for i, hidden in enumerate([False, False, True]):
        db.add(
            Activity(
                source="garmin",
                external_id=str(i),
                name="Course",
                sport_type="Run",
                start_time=start,
                elapsed_time_s=1800,
                hidden=hidden,
            )
        )
    db.commit()
    body = client.get("/vitrine.json").json()
    assert (body["code"], body["ligne"], body["etape"]) == ("EXP-04", "ml", 5)
    figures = {f["libelle"]: f["valeur"] for f in body["chiffres"]}
    assert figures["Séances synchronisées"] == 2  # the hidden one is not counted
    assert set(body) == {"app", "code", "ligne", "etape", "etape_libelle", "chiffres", "maj"}


@respx.mock
def test_healthchecks_ping_success_and_failure() -> None:
    ok = respx.get("https://hc.test/abc").mock(return_value=httpx.Response(200))
    fail = respx.get("https://hc.test/abc/fail").mock(return_value=httpx.Response(200))
    ping_healthchecks("https://hc.test/abc", failed=False)
    ping_healthchecks("https://hc.test/abc/", failed=True)
    assert ok.called and fail.called


@respx.mock
def test_healthchecks_ping_never_breaks_the_job() -> None:
    respx.get("https://hc.test/abc").mock(side_effect=httpx.ConnectError("down"))
    ping_healthchecks("https://hc.test/abc", failed=False)  # no exception
    ping_healthchecks("", failed=False)  # no URL: nothing sent
