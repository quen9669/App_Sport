"""Smoke-free tracking: counters, streaks, months and the API."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.services.smoking import DEFAULT_QUIT_DATE, CigaretteDay, summarize
from app.services.weeks import local_today

QUIT = date(2026, 9, 1)


def test_no_cigarette_since_quitting() -> None:
    summary = summarize(QUIT, date(2026, 9, 30), [])
    assert summary.days_since_quit == 30  # 1st to 30th, both included
    assert summary.smoke_free_days == 30
    assert summary.current_streak == summary.longest_streak == 30
    assert summary.cigarettes == 0


def test_cigarette_days_break_the_streak() -> None:
    entries = [
        CigaretteDay(date(2026, 9, 10), 2),  # 9 smoke-free days before it
        CigaretteDay(date(2026, 9, 25), 1),  # 14 days between the two
        CigaretteDay(date(2026, 8, 20), 5),  # before quitting: ignored
    ]
    summary = summarize(QUIT, date(2026, 10, 5), entries)
    assert summary.days_since_quit == 35
    assert summary.cigarette_days == 2
    assert summary.smoke_free_days == 33
    assert summary.cigarettes == 3
    assert summary.current_streak == 10  # 26 September to 5 October
    assert summary.longest_streak == 14


def test_cigarette_today_resets_the_current_streak() -> None:
    today = date(2026, 10, 18)
    summary = summarize(QUIT, today, [CigaretteDay(today, 1)])
    assert summary.current_streak == 0
    assert summary.longest_streak == (today - QUIT).days


def test_months_cover_the_period() -> None:
    entries = [CigaretteDay(date(2026, 9, 10), 2), CigaretteDay(date(2026, 10, 2), 1)]
    months = summarize(date(2026, 9, 15), date(2026, 10, 3), entries).months
    assert [(m.month, m.days, m.smoke_free_days, m.cigarettes) for m in months] == [
        ("2026-09", 16, 16, 0),  # the 10th is before the quit date
        ("2026-10", 3, 2, 1),
    ]


def test_quit_date_in_the_future_counts_nothing() -> None:
    summary = summarize(date(2026, 12, 1), date(2026, 10, 18), [])
    assert summary.days_since_quit == summary.current_streak == summary.longest_streak == 0
    assert summary.months == []


def test_api_default_quit_date_then_saved(client: TestClient) -> None:
    body = client.get("/api/smoking").json()
    assert body["quit_date"] == DEFAULT_QUIT_DATE.isoformat()
    assert body["quit_date_is_default"] is True

    today = local_today("Europe/Luxembourg")
    start = today - timedelta(days=9)
    saved = client.put("/api/smoking/quit-date", json={"quit_date": start.isoformat()}).json()
    assert saved["quit_date_is_default"] is False
    assert saved["days_since_quit"] == 10
    assert saved["current_streak"] == 10

    future = (today + timedelta(days=5)).isoformat()
    assert client.put("/api/smoking/quit-date", json={"quit_date": future}).status_code == 422


def test_api_write_correct_and_delete_a_cigarette_day(client: TestClient) -> None:
    today = local_today("Europe/Luxembourg")
    client.put(
        "/api/smoking/quit-date", json={"quit_date": (today - timedelta(days=9)).isoformat()}
    )
    day = (today - timedelta(days=3)).isoformat()

    body = client.put(f"/api/smoking/days/{day}", json={"cigarettes": 2, "note": " soirée "}).json()
    assert body["cigarette_days"] == 1
    assert body["current_streak"] == 3
    assert body["entries"] == [{"day": day, "cigarettes": 2, "note": "soirée"}]

    # Writing the same day again corrects it, it does not add a second day.
    body = client.put(f"/api/smoking/days/{day}", json={"cigarettes": 1}).json()
    assert body["cigarettes"] == 1
    assert len(body["entries"]) == 1

    body = client.delete(f"/api/smoking/days/{day}").json()
    assert body["cigarette_days"] == 0
    assert client.delete(f"/api/smoking/days/{day}").status_code == 404


def test_api_rejects_bad_days(client: TestClient) -> None:
    future = (date.today() + timedelta(days=5)).isoformat()
    assert client.put(f"/api/smoking/days/{future}", json={"cigarettes": 1}).status_code == 422
    assert client.put("/api/smoking/days/2026-10-01", json={"cigarettes": 0}).status_code == 422
    assert client.put("/api/smoking/days/2026-10-01", json={"cigarettes": 61}).status_code == 422
    assert client.put("/api/smoking/days/not-a-day", json={"cigarettes": 1}).status_code == 422
