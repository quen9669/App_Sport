# CLAUDE.md

Project memo for anyone (human or AI) working on this repository. Keep it up to date at each phase.

## What this is

A single-user sport app (PWA for PC and Android) that ingests Strava activities and Garmin health data,
tracks weekly goals, shows an activity map, predicts race times and offers two AI coaches.
Full product spec: kept outside the repo; roadmap and phases in `docs/roadmap.md`.

The owner is learning Python, React and GitHub: **comment code generously** (explain the *why*),
keep functions short, and explain important choices in PR descriptions.

## Stack

- **Backend** (`backend/`): Python 3.12+, `uv`, FastAPI, Pydantic v2, pydantic-settings.
  Coming in phase 1: SQLAlchemy 2.x, Alembic, SQLite (PostgreSQL-compatible), APScheduler, httpx.
- **Frontend** (`frontend/`): React 19, Vite, TypeScript strict, `vite-plugin-pwa`.
  Coming later: react-leaflet (OpenStreetMap), Recharts.
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

Single backend test: `cd backend && uv run pytest tests/test_health.py -k ok`.
Single frontend test: `cd frontend && npx vitest run src/App.test.tsx`.
Use an existing Chromium for E2E: `PLAYWRIGHT_CHROMIUM_PATH=/path/to/chrome make test-e2e`.

## Conventions

- Code, identifiers, comments and commits in **English**; UI text and coach answers in **French**.
- Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `build:`, `ci:`), one per logical step.
- One branch and one PR per phase; CI must be green before merging.
- Backend layers: `app/api` (thin routes) → `app/services` (logic) → `app/repositories` (DB access).
- All routes under `/api`. Response shapes are Pydantic models; frontend mirrors them in `src/api/`.
- Settings only via `app.config.get_settings()`; never read `os.environ` directly.
- Timezone `Europe/Luxembourg`, metric units; store datetimes in UTC.

## Security rules (non-negotiable)

- Never commit `.env`, tokens, databases or exported health data (see `.gitignore`).
- Never log secrets: logging goes through `SecretRedactingFilter` (`app/logging_config.py`).
- No third-party telemetry or trackers.

## Architecture decisions

See `docs/adr/`. Current: `0001-stack.md`.
