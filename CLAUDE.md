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
| `make set-password` | Choose the app password (Argon2 fingerprint written to `.env`) |
| `make prod` | Build the interface and run one production server on 127.0.0.1:8000 |
| `make autostart` / `make autostart-off` / `make prod-restart` | Windows: start `make prod` at each log-on / stop that / restart it (phase 6b) |
| `make backup` / `make restore f=...` | Copy the database now / list or restore a copy |

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
- Category `transport` ("Déplacement", owner's decision): walks (Strava `Walk`, Garmin `walking`...)
  and outdoor rides under 5 km. Counts in no session, minute or distance goal, but still in the
  training load. Use `activity_automatic_category(activity)`: the rule needs the distance.
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
  Garmin preferred over other sources). Routes in `api/dashboards.py`; page `HealthPage` (`/sante`,
  one tab per `section`, see "Interface" below).
- Weight: Garmin weigh-ins (`get_body_composition`, grams, a year looked back at each sync) go to
  `body_metric` with `source="garmin"`, never over a weigh-in typed in the app. The Santé page
  carries the last weigh-in forward until the next one (owner's choice: no smoothing, no invented values).
- Goal kinds `training_load` (points, per-activity load from `training_load.activity_load`) and
  `intensity_minutes` (Garmin daily `moderateIntensityMinutes` + 2 × `vigorousIntensityMinutes`,
  summed per week by `health_dashboard.weekly_intensity`). Their targets are drawn as a dashed line
  on the Santé charts (`WeeklyBarChart`); `/api/intensity-minutes` serves the weekly series.
- Steps and floors (owner's request): `daily_health.steps` / `floors_ascended` / `floors_descended`
  (Garmin `totalSteps`, `floorsAscended`, `floorsDescended`, floors rounded; old days refilled from
  `raw_payload` by the migration). `health_dashboard.weekly_steps`; `/api/steps-floors`. Goal kinds
  `steps` (a DAILY target: the week's average day of the days with data must reach it) and `floors`
  (floors climbed per week). Santé cards "Pas" (one bar per day) and "Étages" (per week).

## Map and activity detail (phase 3b)

- `/api/map/routes` (`services/activity_map.py`): filters (sport group run/ride/strength/other,
  days, km), only routes intersecting `bbox` are sent, simplified with Douglas-Peucker
  (`services/geo.py`) for the zoom. `bounds`/`total` cover every match so the map can frame them.
- Activities without a route are grouped on a `place` (`services/places.py`): `activity.place_id`
  (manual, never touched by syncs) else the place whose `role` is `strength_default` (strength) or
  `other_default` (the rest). Owner's defaults (migration): Jims Gare / Jims Gasperich.
- `/api/activities/{id}` returns aligned series thinned to 1,000 points (speed derived from distance
  when the source has none). Frontend: `MapPage` (`/activites`, `/carte` redirects), `ActivityPage` (`/activites/:id`);
  Leaflet components (`RoutesMap`, `ActivityMap`) are lazy-loaded, use `preferCanvas`, and are
  mocked in unit tests (jsdom has no canvas); E2E stubs the OSM tiles.
- The map opens on the last 14 days (owner's choice). Activities with a start point but no route
  yet (Garmin routes come with the details) are dots at their start, never at a gym.
- Activity tables (`components/ActivityTable.tsx`, week list and map list): flag, town, date, name,
  sport (emoji + `--sport-*` colour: red run, green ride, purple walk, yellow strength, orange other),
  distance (empty for strength / no distance), duration, average and max HR (empty without a reading).
  Rows come from `api/rows.py`. The Course page lists each run with its HR too.
- Town: `activity.location_name` (Garmin `locationName`, Strava `location_city`), else the place's
  `city`. Country: `services/countries.py`, offline point-in-polygon on Natural Earth borders
  (`app/geodata/countries.json.gz`), never a web service. Flags on Windows: bundled font
  (`country-flag-emoji-polyfill`, loaded from the app itself).
- Motorcycle trips (`motorcycling_v2`...) are `transport` with zero training load.

## Race predictor (phase 4)

- `app/services/race/`: pure calculations (`daniels.py` VDOT and paces, `riegel.py`, `plan.py` pace
  plan and feasibility, `efforts.py` form estimate) tested against Daniels' published tables;
  `predictor.py` reads the database. Routes in `api/race.py`, page `RacePage` (`/course`).
- Efforts: runs (`RUN_SPORTS`, not hidden, not duplicate, not treadmill, not `excluded_from_race`)
  of the last 120 days, plus their best 5/10 km from the streams; one effort per run (the best).
  Each gives max(race VDOT, Swain heart-rate VDOT); weight halves every 45 days (owner's choice);
  the estimate is the weighted mean of the better half. Fewer than 3 runs or none in 60 days:
  `insufficient`, and no time is shown.
- `race_target` holds one race at most (owner's: 10 km under 50:00 on 2026-12-13); its target time
  includes hills (0.6 s per metre climbed), so feasibility compares the flat-equivalent time.

## Smoke-free tracking

- `smoking_day` stores only the days WITH a cigarette (count + note); every other day since
  `user_profile.smoke_free_since` (default `DEFAULT_QUIT_DATE` = 2026-09-01 in `services/smoking.py`)
  is smoke-free, today included. Vaping is not tracked. Routes in `api/smoking.py` (every write answers
  with the new counters); card `SmokeFreeSection` on the Santé page. Kept for the future longévité coach.

## AI coaches (phase 5a)

- Two providers behind the `LLM` protocol (`app/coach/llm.py`): **Gemini** (`gemini.py`, REST
  `streamGenerateContent` over httpx, faked with respx; owner's choice, used when `GEMINI_API_KEY`
  is set) and Claude (`AnthropicLLM`, SDK on **httpx2**, so tests pass
  `http_client=httpx2.Client(transport=MockTransport)`). Stored messages use Anthropic's block
  format; `gemini.py` translates and keeps Gemini's `thought_signature` in the blocks (stripped
  for Claude). Defaults per provider in `config.COACH_DEFAULTS`; `Settings.provider` picks one.
- Package `app/coach/`: `engine.py` (tool loop, max 8 rounds, logs every call), `costs.py` (cost in EUR, monthly
  budget: warning at 80 %, hard stop at 100 %), `history.py` (summaries by the light model,
  compaction), `prompts/*.md` (versioned with `<!-- version: ... -->`), `tools/` (typed inputs,
  `extra="forbid"`, results capped at 20,000 chars).
- The model only sees data through tools, never GPS positions; tool results are data, not
  instructions. Memories are proposed by the coach and sent to the model only once accepted.
- Settings: `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` (both empty = coach disabled, screen explains
  it), `COACH_PROVIDER`, `COACH_MODEL`,
  `COACH_LIGHT_MODEL`, `COACH_MONTHLY_BUDGET_EUR`, prices per million tokens.
- Routes in `api/coach.py`; the answer is SSE (`text` / `tool` / `done` / `error`) with its own DB
  session. Tests use `tests/fixtures/fake_llm.py`. Page `CoachPage` (`/coach`), answers rendered by
  `CoachText` (mini-Markdown built from React elements, never raw HTML).

## Longevity coach, weekly plan, evaluation (phase 5b)

- Coach `longevity` (page `/longevite`, prompt `prompts/longevity.md`): its own tools in
  `coach/tools/longevity.py` (daily activity, VO2max, heart-rate zones from each activity's
  AVERAGE HR, smoke-free counters without notes). `COACH_TOOLS` in `coach/tools/__init__.py`
  says which coach gets which tool; only the training coach can propose a plan.
- `propose_weekly_plan` (`coach/tools/plan.py`) stores a `coach_plan` row as `proposed` (week
  from this Monday to two weeks ahead); the engine streams it as an SSE `plan` event, shown by
  `PlanCard`. `PATCH /api/coach/plans/{id}` accepts or rejects; accepting replaces the week's
  previous accepted plan. `GET /api/coach/plans/current` feeds `WeekPlanSection` (page `/plan`)
  and `TodayPlan` (today's sessions on "Ma semaine").
- Evaluation in `backend/evals/` (`make eval`, real paid calls, `--max-eur` cap, synthetic data
  only, reports in `evals/reports/`, gitignored): `scenarios.py` (fixed date 2026-10-18 and
  seed), `checks.py`, `judge.py` (JSON grades 1-5), `report.py`. `--compare file.md` runs a
  prompt variant (coach taken from its version line) next to the current one through
  `Engine.prompt`. `tests/test_evals.py` covers it all with FakeLLM. A new prompt behaviour
  deserves a scenario.

## Interface (design pass before phase 6)

- Owner's choice: clean, Garmin Connect look in the red of his "QF" logo (`src/assets/logo.png`,
  PWA icons in `public/icons/`). Tokens in `styles/theme.css`: `--accent` (logo red, fills),
  `--accent-text` (darker red for text), `--success` (reached goals stay green), dark mode redefines
  them. Barlow fonts come from `@fontsource` (bundled, never a font CDN).
- Menu in 3 folders (owner's request), all in `src/navigation.ts`: Entraînement (Ma semaine,
  Activités, Muscu, Course, Objectifs), Santé (Résumé, Sommeil, Récupération, Activité, Poids,
  Tabac), Coach (Muscu et cardio, Longévité, Mon plan); Réglages (Profil, Sources, Mes lieux)
  behind the gear. `AppShell` renders both a phone layout (dark top bar with the folder's tabs,
  bottom bar with the folders) and a PC sidebar (>= 60rem); CSS shows one. In unit tests both are in
  the DOM: scope queries by the nav's `aria-label`. E2E opens tabs through `e2e/nav.ts`.
- Each page keeps its own `h1`. A new page needs a route in `App.tsx` and a tab in `navigation.ts`.

## Security and PWA (phase 6a)

- Sign-in: `services/auth.py` (Argon2 `APP_PASSWORD_HASH`, random session token whose SHA-256 is
  stored in `auth_session`, `LoginThrottle`: 5 failures in 15 min lock 15 min, in memory, global).
  Routes in `api/auth.py` (`status`, `login`, `logout`). `require_auth` (`dependencies.py`) guards
  every router in `main.PROTECTED_ROUTERS` and the Strava routes except `/callback`. No password =
  open (development only: `check_production` refuses to start production without one). A new
  router goes into `PROTECTED_ROUTERS` unless it must be reachable signed out.
- Cookie `app_sport_session`: HttpOnly, SameSite=Strict, Secure in production, 30 days
  (`SESSION_DAYS`). Frontend calls use `credentials: 'include'`; a 401 fires
  `AUTH_REQUIRED_EVENT` and `AuthGate` shows `LoginPage`. Tests inject time through `get_now`.
- `security.py` adds the CSP (scripts `'self'` only, images also from tile.openstreetmap.org,
  inline styles allowed for Leaflet/Recharts), nosniff, frame denial, HSTS in production. A new
  external resource needs a CSP change, never a CDN script. `/docs` is off in production.
- `make prod`: `FRONTEND_DIST` makes `frontend.py` serve the build (SPA fallback, `/api/*` stays
  404, no path escape, `index.html`/`sw.js` not cached). Nightly backups: `services/backup.py`
  (SQLite backup API) scheduled at 03:30 in `scheduler.py`.
- PWA (`vite.config.ts`): `registerType: 'prompt'` (`AppBanners` "Recharger"), app files, logo and
  latin fonts precached, API GETs `NetworkFirst` in `api-cache` (never `/api/auth|coach|strava`).
  Offline: `OfflineBanner` shows the last answer time; non-GET requests fail with
  `OFFLINE_MESSAGE`. "Se déconnecter" (`DeviceSection`, Profil page) empties `api-cache`.
  Install button: `pwa/install.ts` keeps Chrome's `beforeinstallprompt`.
- CI job `security`: pip-audit on the locked export, `npm audit --omit=dev --audit-level=high`,
  gitleaks over the whole history. Dependabot weekly (uv, npm) and monthly (actions).

## Hosting on the owner's PC (phase 6b)

- Owner's choice: the app runs on his Windows PC (WSL2) and is reached through Tailscale only
  (`tailscale serve --bg 8000`, HTTPS on `<machine>.<tailnet>.ts.net`; never `funnel`).
  Guide: `docs/learning/06-telephone-tailscale.md`.
- `make autostart` (`scripts/windows/autostart.sh`) puts an "App Sport" shortcut in the Windows
  Startup folder (no admin rights needed, unlike a log-on scheduled task) that runs, hidden,
  `scripts/windows/start-app.sh` -> `make prod`, log in `backend/data/prod.log`; it refuses
  without `APP_PASSWORD_HASH`. `make autostart-off` removes it, `make prod-restart` restarts the app.
- `FRONTEND_URL` and `STRAVA_REDIRECT_URI` point at the ts.net address; production is same-origin,
  so `CORS_ORIGINS` is not needed there.
