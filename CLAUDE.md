# CLAUDE.md

Project memo for anyone (human or AI) working on this repository. Keep it up to date at each phase.

## What this is

A single-user sport app (PWA for PC and Android) that ingests Strava activities and Garmin health data,
tracks weekly goals, shows an activity map, predicts race times and offers two AI coaches.
Full product spec: kept outside the repo; roadmap and phases in `docs/roadmap.md`.

The owner is learning Python, React and GitHub: **comment code generously** (explain the *why*),
keep functions short, and explain important choices in PR descriptions.

## Stack

- **Backend** (`backend/`): Python 3.12+, `uv`, FastAPI, Pydantic v2, pydantic-settings,
  SQLAlchemy 2.x + Alembic (SQLite, PostgreSQL-compatible), httpx (sync client), cryptography (Fernet).
  APScheduler 3 (in-process scheduled syncs), garminconnect (unofficial Garmin library).
- **Frontend** (`frontend/`): React 19, Vite, TypeScript strict, `vite-plugin-pwa`, react-router,
  Recharts (lazy-loaded with `React.lazy`). Coming later: react-leaflet (OpenStreetMap).
- **Tests**: pytest + pytest-asyncio; Vitest + Testing Library; Playwright (E2E, desktop + Pixel 7).
- **Quality**: ruff (lint + format) and mypy `--strict` for Python; oxlint + Prettier + `tsc` for TS.

## Commands (run from the repo root, in WSL2 or Linux)

| Command | What it does |
|---|---|
| `make install` | Install all dependencies, create `.env` from `.env.example` if missing |
| `make dev` | Backend on :8000 (docs at `/docs`) + frontend on :5173 |
| `make test` | Backend and frontend unit tests |
| `make test-e2e` | Playwright E2E (run `make e2e-install` once first) |
| `make lint` / `make format` / `make typecheck` | Quality checks / auto-format / types |
| `make check` | Everything CI runs (except E2E) |
| `make db-upgrade` | Apply Alembic migrations (also run by `make dev-backend`) |
| `make db-revision m="..."` | Autogenerate a migration after changing a model |
| `make seed` / `make seed-clear` | Create / remove a year of synthetic data (`source="synthetic"`) |

Single backend test: `cd backend && uv run pytest tests/test_health.py -k ok`.
Single frontend test: `cd frontend && npx vitest run src/App.test.tsx`.
Use an existing Chromium for E2E: `PLAYWRIGHT_CHROMIUM_PATH=/path/to/chrome make test-e2e`.

## Conventions

- Code, identifiers, comments and commits in **English**; UI text and coach answers in **French**.
- Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `build:`, `ci:`), one per logical step.
- One branch and one PR per phase; CI must be green before merging.
- Backend layers: `app/api` (thin routes) → `app/services` (logic) → `app/repositories` (DB access);
  `app/integrations/<source>` holds external API clients (HTTP only, no DB).
- DB: SI units, UTC datetimes (`UTCDateTime`), upserts keyed on `(source, external_id)` for idempotency,
  raw API JSON kept in `raw_payload`. Every model change needs a migration (`tests/test_migrations.py`).
- External APIs are never called in tests: use `respx` and the fakes in `tests/fixtures/`.
- Injected `now`/`sleep` callables keep time-dependent code (quotas, token expiry) testable.
- All routes under `/api`. Response shapes are Pydantic models; frontend mirrors them in `src/api/`.
- Settings only via `app.config.get_settings()`; never read `os.environ` directly.
- Timezone `Europe/Luxembourg`, metric units; store datetimes in UTC.

## Security rules (non-negotiable)

- Never commit `.env`, tokens, databases or exported health data (see `.gitignore`).
- Never log secrets: logging goes through `SecretRedactingFilter` (`app/logging_config.py`).
- OAuth tokens are stored encrypted (`app/services/crypto.py`, key `TOKEN_ENCRYPTION_KEY`).
- No third-party telemetry or trackers.

## Architecture decisions

See `docs/adr/`. Current: `0001-stack.md`. Data model: `docs/data-model.md`.

## Ingestion (phase 1)

Health sources implement `HealthDataProvider` (`app/integrations/health/provider.py`):
`GarminConnectProvider` (unofficial lib, imported lazily, errors → `HealthProviderError`, sync marked
failed, app unaffected) and `FileImportProvider` (CSV template in `docs/templates/`, Garmin export
`*_sleepData.json`). Everything is stored through `services/health_sync.store_batch` (upserts,
plausibility bounds in `validation.py`). Jobs outside requests live in `services/jobs.py`; the
scheduler (`app/scheduler.py`) runs them every `SYNC_INTERVAL_HOURS` and is disabled in tests.

### Strava sync

`app/services/strava_sync.py`, one run = new activities (7-day overlap) → a few history pages
(cursor `strava_backfill` in `sync_cursor`) → missing streams. Quotas: `integrations/strava/rate_limit.py`
waits for the next 15-min window, stops the run as `partial` near the daily limit.

## Goals and categories (phase 2)

- `app/services/classification.py` is the single place mapping Strava `sport_type` to
  strength / cardio / other. Group classes (`Workout`, `Crossfit`, `HighIntensityIntervalTraining`)
  count as strength (owner's decision). `Activity.category_override` (manual) always wins and is never
  touched by syncs; `effective_category()` is what every count must use.
- Weeks are ISO weeks (Monday-Sunday) in `APP_TIMEZONE`: `app/services/weeks.py` converts local
  boundaries to UTC separately, so DST weeks are 167/169 h. Labels look like `2026-W42`.
- `app/services/goals.py` computes progress; only `active` goals overlapping the week count.
- Validation bounds live in the Pydantic models (`app/api/profile.py`, `app/api/goals.py`) and are
  mirrored in `frontend/src/utils/bounds.ts`: change both together.
- `body_metric` has one row per day (upsert on `measured_on`) and a `source` column so `make seed`
  weigh-ins can be removed without touching manual ones.
- Frontend tests use `src/test/fakeBackend.ts` (fake `fetch` by "METHOD /path").
- Typed strength sessions (`strength_session` / `strength_set`, `app/api/strength.py`) count for
  strength and minute goals only when not already recorded on Strava: linked by `activity_id`, or
  a strength activity within 3 h (`app/services/strength.py`). Never count both.
- History and streak: `weeks_history()` loads a whole period in 3 queries; the current week never
  breaks the streak. "Done" goals still count for past weeks, paused ones never do.
- The gym draft lives in `localStorage` (`src/utils/strengthDraft.ts`) until "Terminer la séance".
- Chart series colors are CSS variables `--series-1..4` (fixed order, validated for color
  blindness, separate light/dark steps); legend and labels stay in text colors.

## Garmin activities, health screen, load (phase 3a)

- Garmin Connect is the **main activity source**; Strava only complements it (owner's decision).
  `services/garmin_activity_sync.py` mirrors the Strava sync (new pages, offset-paged history with
  cursor `garmin_activities_backfill`, missing details). Mapping in
  `integrations/health/garmin_activities.py` (field names from `garminconnect`, unverified on real data).
- `services/dedupe.py` runs after both syncs: Strava rows that duplicate a Garmin row get
  `duplicate_status="confirmed"` and are excluded by `activities_repo.not_duplicate()`; "possible"
  ones stay visible. `hidden` (manual) is never touched by syncs and never counted. Every new list or
  count of activities must use `activities_repo.activities_between()` (or `not_duplicate()`) and skip
  `hidden`.
- Training load: `services/training_load.py` (Banister TRIMP, else minutes × effort per category);
  no ACWR before 5 weeks of history. Max HR: profile, else the highest activity `max_heartrate`
  of the last year (120-230 bpm, hidden and duplicates skipped), else 220 - age. Health series: `services/health_dashboard.py` (one row per day,
  Garmin preferred over other sources). Routes in `api/dashboards.py`; page `HealthPage` (`/sante`).
- Weight: Garmin weigh-ins (`get_body_composition`, grams, a year looked back at each sync) go to
  `body_metric` with `source="garmin"`, never over a weigh-in typed in the app. The Santé page
  carries the last weigh-in forward until the next one (owner's choice: no smoothing, no invented values).
