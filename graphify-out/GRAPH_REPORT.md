# Graph Report - app_sport  (2026-11-06)

## Corpus Check
- 313 files · ~138,429 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 12 file(s) not represented in the graph (top: (none) 5, .example 1, .ini 1)

## Summary
- 3600 nodes · 10476 edges · 137 communities (119 shown, 18 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 654 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `cd92ebbd`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- client.ts
- format.ts
- test_coach.py
- activity_map.py
- test_garmin_activities.py
- services/goals.py
- models/__init__.py
- HealthPage.tsx
- sqlalchemy
- run.py
- api/strava.py
- Activity
- test_api_strength.py
- App.tsx
- ProfilePage.tsx
- repositories/profile.py
- ToolContext
- test_evals.py
- seed.py
- test_coach_gemini.py
- with
- test_coach_longevity_plan.py
- vitest
- api/coach.py
- api/strength.py
- WorkoutEditor.tsx
- DataSource
- CLAUDE.md
- api/auth.py
- main.py
- test_dashboards.py
- maps.py
- health_data.py
- test_plan_workouts.py
- api/goals.py
- test_location.py
- test_strava_oauth.py
- services/longevity.py
- SmokeFreeSection.tsx
- RacePage.tsx
- test_longevity.py
- api/race.py
- FakeGarmin
- jobs.py
- test_strava_sync.py
- GarminConnectProvider
- StrengthPage.tsx
- Category
- pytest
- file_import.py
- workouts.py
- session.py
- api/sync.py
- garmin_connect.py
- test_backup.py
- test_race.py
- package.json
- GoalsPage.tsx
- repositories/activities.py
- test_auth.py
- dashboards.py
- Settings
- repositories/coach.py
- utc_now
- HomePage.tsx
- predictor.py
- plan_workouts.py
- api/places.py
- StravaClient
- RateLimiter
- test_security_headers.py
- api/smoking.py
- api/activities.py
- TokenSet
- LongevitySection.tsx
- compilerOptions
- HealthProviderError
- respx
- summarize
- test_api_strava.py
- garmin_push.py
- conftest.py
- compilerOptions
- local_today
- Ouvrir l'app sur ton téléphone avec Tailscale (phase 6b)
- tools/race.py
- garmin_workouts.py
- logging
- test_migrations.py
- test_weights.py
- countries.py
- Feuille de route
- prompts/__init__.py
- add_run
- GarminActivitySyncService
- @playwright/test
- updates
- race/plan.py
- dependencies
- scripts
- repositories/smoking.py
- 2026_10_18_1320-5974acb22aa2_daily_intensity_minutes.py
- Architecture
- GitHub pour ce projet, pas à pas
- month_budget
- Règles communes aux deux coachs
- save_target
- vite.config.ts
- ADR 0001 : stack et outils
- Règles
- Les outils du projet, simplement
- Connecter ton compte Strava
- Clé API pour les coachs IA (Gemini, ou Claude)
- Évaluer les coachs IA (`make eval`)
- .oxlintrc.json
- App Sport
- Récupérer tes données Garmin
- .prettierrc.json
- pull_request_template.md
- decide_plan
- autostart.sh
- start-app.sh
- _plan_ids
- vite-env.d.ts
- tsconfig.json
- app-sport-backend

## God Nodes (most connected - your core abstractions)
1. `Settings` - 118 edges
2. `Activity` - 89 edges
3. `DataSource` - 50 edges
4. `ToolContext` - 49 edges
5. `request()` - 47 edges
6. `get_settings()` - 46 edges
7. `Base` - 45 edges
8. `UTCDateTime` - 42 edges
9. `utc_now()` - 42 edges
10. `formatNumber()` - 39 edges

## Surprising Connections (you probably didn't know these)
- `Données de santé` --references--> `HealthDataProvider`  [INFERRED]
  docs/architecture.md → backend/app/integrations/health/provider.py
- `Security rules (non-negotiable)` --references--> `SecretRedactingFilter`  [INFERRED]
  CLAUDE.md → backend/app/logging_config.py
- `Smoke-free tracking` --references--> `SmokeFreeSection()`  [INFERRED]
  CLAUDE.md → frontend/src/components/SmokeFreeSection.tsx
- `Race predictor (phase 4)` --references--> `RacePage()`  [INFERRED]
  CLAUDE.md → frontend/src/pages/RacePage.tsx
- `AI coaches (phase 5a)` --references--> `LLM`  [INFERRED]
  CLAUDE.md → backend/app/coach/llm.py

## Import Cycles
- None detected.

## Communities (137 total, 18 thin omitted)

### Community 0 - "client.ts"
Cohesion: 0.04
Nodes (94): addMemory(), API_BASE_URL, ApiError, askCoach(), AuthStatus, BodyMetricInput, CategoryResult, CigaretteDay (+86 more)

### Community 1 - "format.ts"
Cohesion: 0.05
Nodes (85): leaflet@^1.9.4, react-leaflet@^5.0.0, ActivityRow, ActivitySeries, Bounds, fetchActivity(), fetchMapRoutes(), MapPlace (+77 more)

### Community 2 - "test_coach.py"
Cohesion: 0.08
Nodes (38): _Answer, AnthropicLLM, Final, TextDelta, ToolStart, Usage, FakeLLM, text_turn() (+30 more)

### Community 3 - "activity_map.py"
Cohesion: 0.07
Nodes (37): _add_point(), _add_to_place(), _evenly_spaced(), map_routes(), MapFilters, MapPlace, MapPoint, MapResult (+29 more)

### Community 4 - "test_garmin_activities.py"
Cohesion: 0.06
Nodes (24): get_health(), HealthResponse, activity_fields(), details_to_series(), GarminActivitySummary, GarminActivityType, _latlng(), _metric_indexes() (+16 more)

### Community 5 - "services/goals.py"
Cohesion: 0.06
Nodes (28): sessions_between(), activities_in_week(), _amount(), compute_progress(), counted_goals(), GoalProgress, goals_for_week(), load_function() (+20 more)

### Community 6 - "models/__init__.py"
Cohesion: 0.09
Nodes (14): upgrade(), Base, ActivityStream, AuthSession, CoachConversation, CoachMessage, CoachPlan, SourceCredential (+6 more)

### Community 7 - "HealthPage.tsx"
Cohesion: 0.08
Nodes (56): recharts@^3.10.1, fetchHealthMetrics(), fetchIntensityMinutes(), fetchStepsAndFloors(), HealthDay, HealthMetrics, IntensityMinutes, Smoking (+48 more)

### Community 8 - "sqlalchemy"
Cohesion: 0.05
Nodes (19): upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), _fill_from_raw_payloads(), _location(), _number() (+11 more)

### Community 9 - "run.py"
Cohesion: 0.07
Nodes (19): ask(), events(), _sse(), log_call(), DoneEvent, Engine, ErrorEvent, PlanEvent (+11 more)

### Community 10 - "api/strava.py"
Cohesion: 0.06
Nodes (14): callback(), connect(), disconnect(), get_status(), OAuthStateStore, StravaStatus, build_strava_oauth(), get_cipher() (+6 more)

### Community 11 - "Activity"
Cohesion: 0.08
Nodes (28): ActivitiesInput, ActivityInput, get_activity_detail(), get_recent_activities(), get_strength_sessions(), get_weekly_volume(), _km_splits(), _local() (+20 more)

### Community 12 - "test_api_strength.py"
Cohesion: 0.08
Nodes (34): add_activity(), add_goal(), test_category_of_unknown_activity(), test_create_list_update_delete_goal(), test_goal_bounds_are_checked(), test_hide_an_activity_removes_it_from_goals(), test_paused_and_future_goals_are_not_counted(), test_progress_defaults_to_current_week() (+26 more)

### Community 13 - "App.tsx"
Cohesion: 0.08
Nodes (40): AUTH_REQUIRED_EVENT, CurrentPlans, fetchAuthStatus(), fetchCurrentPlans(), login(), logout(), ActivityPage, App() (+32 more)

### Community 14 - "ProfilePage.tsx"
Cohesion: 0.09
Nodes (44): BodyMetric, deleteBodyMetric(), fetchBodyMetrics(), fetchProfile(), GoalKind, saveBodyMetric(), saveProfile(), QuickWeight() (+36 more)

### Community 15 - "repositories/profile.py"
Cohesion: 0.07
Nodes (26): age_on(), BodyMetricIn, BodyMetricOut, delete_body_metric(), list_body_metrics(), _profile_out(), ProfileIn, ProfileOut (+18 more)

### Community 16 - "ToolContext"
Cohesion: 0.09
Nodes (28): Coach longévité, Méthode, Tes sujets, Days, NoInput, rounded(), ToolContext, Weeks (+20 more)

### Community 17 - "test_evals.py"
Cohesion: 0.10
Nodes (29): Check, has_number(), normalize(), Outcome, run_checks(), judge(), judge_message(), Judgement (+21 more)

### Community 18 - "seed.py"
Cohesion: 0.09
Nodes (24): SleepNight, BodyMetric, StrengthSession, StrengthSet, bad_week(), base(), bench_plateau(), injected_activity() (+16 more)

### Community 19 - "test_coach_gemini.py"
Cohesion: 0.08
Nodes (26): get_llm(), contents(), _error(), function_declarations(), GeminiLLM, _json(), _part(), _read_chunk() (+18 more)

### Community 20 - "with"
Cohesion: 0.06
Nodes (46): defaults, name, runs-on, steps, concurrency, cancel-in-progress, group, run (+38 more)

### Community 21 - "test_coach_longevity_plan.py"
Cohesion: 0.08
Nodes (24): _inline_refs(), resolve(), run_tool(), Tool, tools_for(), MemoryInput, propose_memory(), create_conversation() (+16 more)

### Community 22 - "vitest"
Cohesion: 0.09
Nodes (32): ActivityDetail, OFFLINE_MESSAGE, Place, Profile, Race, StrengthSessionInput, longevity, renderSection() (+24 more)

### Community 23 - "api/coach.py"
Cohesion: 0.11
Nodes (30): add_memory(), BudgetOut, CoachName, _conversation_out(), ConversationDetailOut, ConversationOut, create_conversation(), CurrentPlansOut (+22 more)

### Community 24 - "api/strength.py"
Cohesion: 0.09
Nodes (21): _check_activity(), create_session(), delete_session(), ExerciseOut, _get(), list_exercises(), list_sessions(), read_session() (+13 more)

### Community 25 - "WorkoutEditor.tsx"
Cohesion: 0.08
Nodes (39): CoachPlan, PaceKey, PaceRange, PlanSessionKind, removeSessionFromGarmin(), RunWorkout, sendSessionToGarmin(), sessionPath() (+31 more)

### Community 26 - "DataSource"
Cohesion: 0.10
Nodes (26): DataSource, get_cursor(), _carry_over(), DedupeResult, DuplicateStatus, find_twin(), _GarminIndex, reconcile_duplicates() (+18 more)

### Community 27 - "CLAUDE.md"
Cohesion: 0.07
Nodes (34): Architecture decisions, Commands (run from the repo root, in WSL2 or Linux), Conventions, graphify, Hosting on the owner's PC (phase 6b), Interface (design pass before phase 6), Map and activity detail (phase 3b), Race predictor (phase 4) (+26 more)

### Community 28 - "api/auth.py"
Cohesion: 0.10
Nodes (14): AuthStatus, get_status(), login(), LoginRequest, logout(), set_session_cookie(), get_login_throttle(), create_session() (+6 more)

### Community 29 - "main.py"
Cohesion: 0.06
Nodes (9): get_now(), require_auth(), _cache_headers(), mount_frontend(), frontend(), check_production(), create_app(), lifespan() (+1 more)

### Community 30 - "test_dashboards.py"
Cohesion: 0.09
Nodes (21): _best_by_day(), health_days(), minutes_from_midnight(), _priority(), Regularity, sleep_regularity(), _weights_carried_forward(), banister_trimp() (+13 more)

### Community 31 - "maps.py"
Cohesion: 0.09
Nodes (16): read_progress(), WeekActivityOut, BoundsOut, MapPlaceOut, MapPointOut, MapRouteOut, MapRoutesOut, _parse_bbox() (+8 more)

### Community 32 - "health_data.py"
Cohesion: 0.09
Nodes (19): garmin_status(), GarminStatus, import_health_file(), ImportResult, count_days(), count_nights(), latest_day(), latest_night() (+11 more)

### Community 33 - "test_plan_workouts.py"
Cohesion: 0.10
Nodes (18): PlanInput, PlanSession, propose_weekly_plan(), add_message(), decide_plan(), propose_plan(), _accepted_plan(), FakeGarmin (+10 more)

### Community 34 - "api/goals.py"
Cohesion: 0.11
Nodes (22): _check_goal(), create_goal(), delete_goal(), _get_goal(), GoalIn, GoalOut, GoalPatch, GoalProgressOut (+14 more)

### Community 35 - "test_location.py"
Cohesion: 0.09
Nodes (17): activity_fields(), garmin_id_from_external_id(), parse_timezone(), _start_point(), StravaActivitySummary, StravaMap, streams_to_series(), country_at() (+9 more)

### Community 36 - "test_strava_oauth.py"
Cohesion: 0.15
Nodes (17): generate_key(), TokenCipher, TokenEncryptionError, StravaCredentialService, test_decrypt_with_another_key_fails_clearly(), test_encrypt_then_decrypt_returns_original(), test_missing_or_invalid_key_is_rejected(), make_oauth() (+9 more)

### Community 37 - "services/longevity.py"
Cohesion: 0.12
Nodes (18): HealthDay, _average(), _band(), Comparison, Indicator, intensity_indicator(), _present(), resting_hr_indicator() (+10 more)

### Community 38 - "SmokeFreeSection.tsx"
Cohesion: 0.11
Nodes (30): createPlace(), deleteCigaretteDay(), deletePlace(), fetchPlaces(), fetchSmoking(), PlaceRole, saveCigaretteDay(), saveQuitDate() (+22 more)

### Community 39 - "RacePage.tsx"
Cohesion: 0.12
Nodes (31): deleteRaceTarget(), Feasibility, fetchRace(), PaceZoneKey, RaceForm, RaceTarget, RaceTargetInput, saveRaceTarget() (+23 more)

### Community 40 - "test_longevity.py"
Cohesion: 0.14
Nodes (20): ComparisonOut, IndicatorOut, LongevityOut, read_longevity(), SmokeFreeOut, DailyHealth, Evidence, Overview (+12 more)

### Community 41 - "api/race.py"
Cohesion: 0.13
Nodes (21): _current(), delete_target(), _effort_out(), EffortOut, ExcludedRunOut, ExclusionIn, FeasibilityOut, FormOut (+13 more)

### Community 42 - "FakeGarmin"
Cohesion: 0.13
Nodes (13): activity_details(), FakeGarmin, GarminConnectConnectionError, GarminConnectTooManyRequestsError, test_garmin_provider_logs_in_only_when_used(), login(), nights(), run() (+5 more)

### Community 43 - "jobs.py"
Cohesion: 0.12
Nodes (10): get_settings(), SyncKind, build_scheduler(), run_garmin_sync(), run_nightly_backup(), run_scheduled_syncs(), run_strava_sync(), test_one_failing_source_does_not_stop_the_others() (+2 more)

### Community 44 - "test_strava_sync.py"
Cohesion: 0.20
Nodes (16): SyncStatus, SyncLimits, FakeStravaApi, make_activity(), make_history(), count(), mock_router(), run_sync() (+8 more)

### Community 45 - "GarminConnectProvider"
Cohesion: 0.10
Nodes (10): FileImportProvider, call_garmin(), GarminConnectProvider, HealthBatch, HealthDataProvider, HealthRateLimitedError, test_garmin_provider_fetches_each_day(), Ingestion (phase 1) (+2 more)

### Community 46 - "StrengthPage.tsx"
Cohesion: 0.16
Nodes (29): createStrengthSession(), deleteStrengthSession(), Exercise, fetchExercises(), fetchStrengthSessions(), StrengthSession, StrengthSet, StrengthSetInput (+21 more)

### Community 47 - "Category"
Cohesion: 0.11
Nodes (16): activity_automatic_category(), automatic_category(), Category, is_motorized(), PlaceBook, parse_week(), test_garmin_types_are_classified(), test_automatic_category() (+8 more)

### Community 48 - "pytest"
Cohesion: 0.10
Nodes (18): _pace_at(), PaceZone, race_time(), speed_for_oxygen(), sustainable_fraction(), training_paces(), vdot(), riegel_time() (+10 more)

### Community 49 - "file_import.py"
Cohesion: 0.13
Nodes (14): _add_csv_row(), _minutes_to_s(), _optional_float(), _optional_int(), parse_csv(), parse_garmin_sleep_export(), _parse_garmin_time(), _whole_number() (+6 more)

### Community 50 - "workouts.py"
Cohesion: 0.11
Nodes (14): _block(), _Counter, estimated_duration_s(), garmin_payload(), pace_targets(), RunWorkout, _step(), WorkoutBlock (+6 more)

### Community 51 - "session.py"
Cohesion: 0.10
Nodes (9): _configure(), _database_url(), _render_item(), run_migrations_offline(), run_migrations_online(), build_engine(), get_db(), get_session_factory() (+1 more)

### Community 52 - "api/sync.py"
Cohesion: 0.13
Nodes (15): _garmin_in_background(), get_logs(), start_garmin_sync(), start_strava_sync(), _strava_in_background(), SyncLogOut, SyncStarted, GarminActivitySyncAlreadyRunningError (+7 more)

### Community 53 - "garmin_connect.py"
Cohesion: 0.12
Nodes (9): GarminApi, _int(), login_with_library(), map_daily(), _ms_to_datetime(), _number(), _vo2max(), garmin_login_once() (+1 more)

### Community 54 - "test_backup.py"
Cohesion: 0.17
Nodes (11): backup_database(), list_backups(), restore_database(), sqlite_path(), main(), make_db(), read(), test_backup_copies_the_database_and_keeps_only_the_last_ones() (+3 more)

### Community 55 - "test_race.py"
Cohesion: 0.19
Nodes (17): oxygen_cost(), best_per_activity(), estimate_form(), heart_rate_vdot(), HeartRate, Method, RunEffort, score() (+9 more)

### Community 56 - "package.json"
Cohesion: 0.10
Nodes (27): devDependencies, jsdom@^30.1.3, oxlint@^1.81.0, @playwright/test@^1.64.1, prettier@^3.9.10, @testing-library/jest-dom@^7.0.1, @testing-library/react@^16.3.3, @testing-library/user-event@^14.6.8 (+19 more)

### Community 57 - "GoalsPage.tsx"
Cohesion: 0.13
Nodes (24): createGoal(), deleteGoal(), fetchGoalHistory(), fetchGoals(), Goal, GoalHistory, GoalInput, GoalSport (+16 more)

### Community 58 - "repositories/activities.py"
Cohesion: 0.14
Nodes (10): activities_between(), activities_missing_streams(), count_activities(), highest_max_heartrate(), latest_start_time(), mark_no_streams(), not_duplicate(), save_stream() (+2 more)

### Community 59 - "test_auth.py"
Cohesion: 0.16
Nodes (15): Clock, clock(), login(), make_client(), build(), test_a_broken_fingerprint_never_lets_anyone_in(), test_a_session_expires_after_30_days(), test_failed_sign_in_logs_never_contain_the_password() (+7 more)

### Community 60 - "dashboards.py"
Cohesion: 0.18
Nodes (16): _goal_target(), HealthDayOut, HealthMetricsOut, HeartRateParamsOut, IntensityMinutesOut, read_health_metrics(), read_intensity_minutes(), read_steps_and_floors() (+8 more)

### Community 61 - "Settings"
Cohesion: 0.11
Nodes (5): cost_eur(), ModelDefaults, Settings, test_cost_estimate(), AI coaches (phase 5a)

### Community 62 - "repositories/coach.py"
Cohesion: 0.15
Nodes (16): CoachCall, CoachMemory, accepted_memories(), accepted_plan(), add_memory(), delete_conversation(), delete_memory(), get_conversation() (+8 more)

### Community 63 - "utc_now"
Cohesion: 0.12
Nodes (7): SyncCursor, SyncLog, utc_now(), finish_log(), is_cursor_completed(), list_logs(), start_log()

### Community 64 - "HomePage.tsx"
Cohesion: 0.14
Nodes (22): Category, fetchHealth(), fetchTrainingLoad(), fetchWeekProgress(), GoalProgress, setActivityCategory(), setActivityHidden(), WeekActivity (+14 more)

### Community 65 - "predictor.py"
Cohesion: 0.14
Nodes (14): best_segment(), FormEstimate, pace_variation(), _comparable(), efforts_of(), _heart_rate(), Prediction, predictions_for() (+6 more)

### Community 66 - "plan_workouts.py"
Cohesion: 0.16
Nodes (9): PlanOut, _garmin_failed(), get_garmin_workout_login(), _plan(), remove_session_from_garmin(), _require_login(), send_session_to_garmin(), update_session_workout() (+1 more)

### Community 67 - "api/places.py"
Cohesion: 0.18
Nodes (11): create_place(), delete_place(), _get(), list_places(), _out(), PlaceIn, PlaceOut, PlaceUpdate (+3 more)

### Community 68 - "StravaClient"
Cohesion: 0.15
Nodes (3): StravaClient, _Counters, StravaSyncService

### Community 69 - "RateLimiter"
Cohesion: 0.13
Nodes (10): DailyLimitReachedError, RateLimiter, seconds_until_next_window(), make_limiter(), test_malformed_headers_are_ignored(), test_next_window_is_next_quarter_hour(), test_no_wait_when_far_from_limits(), test_stops_near_daily_limit() (+2 more)

### Community 70 - "test_security_headers.py"
Cohesion: 0.12
Nodes (9): hash_password(), main(), write_hash(), dist(), prod_client(), test_every_response_carries_the_security_headers(), test_production_adds_hsts_and_hides_the_api_docs(), test_production_keeps_api_errors_and_never_serves_outside_the_build() (+1 more)

### Community 71 - "api/smoking.py"
Cohesion: 0.19
Nodes (11): CigaretteDayIn, CigaretteDayOut, delete_cigarette_day(), MonthOut, _not_in_future(), QuitDateIn, read_smoking(), save_cigarette_day() (+3 more)

### Community 72 - "api/activities.py"
Cohesion: 0.20
Nodes (13): ActivityDetailOut, ActivityPlaceOut, CategoryIn, CategoryOut, _detail(), HiddenIn, HiddenOut, PlaceChoiceIn (+5 more)

### Community 73 - "TokenSet"
Cohesion: 0.11
Nodes (6): StravaAthlete, TokenSet, delete_credential(), get_credential(), StravaNotConnectedError, test_token_set_repr_hides_tokens()

### Community 74 - "LongevitySection.tsx"
Cohesion: 0.16
Nodes (20): fetchLongevity(), Longevity, LongevityEvidence, LongevityIndicator, LongevityStatus, ComparisonTable(), IndicatorCard(), LongevitySection() (+12 more)

### Community 75 - "compilerOptions"
Cohesion: 0.09
Nodes (21): compilerOptions, allowArbitraryExtensions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection (+13 more)

### Community 76 - "HealthProviderError"
Cohesion: 0.15
Nodes (13): parse_file(), map_sleep(), HealthProviderError, sleep_payload(), test_bad_files_are_rejected(), test_csv_import_reads_rows_and_reports_problems(), test_csv_with_excel_bom_is_accepted(), test_csv_without_date_column_is_rejected() (+5 more)

### Community 77 - "respx"
Cohesion: 0.22
Nodes (10): StravaApiError, make_streams(), rate_limit_headers(), make_client(), test_client_errors_are_not_retried(), test_retries_after_429_once_window_resets(), test_retries_server_errors_with_backoff_then_gives_up(), test_sends_bearer_token_and_params() (+2 more)

### Community 78 - "summarize"
Cohesion: 0.22
Nodes (12): CigaretteDay, _current_streak(), _longest_streak(), _months(), MonthSummary, SmokeFreeSummary, summarize(), test_cigarette_days_break_the_streak() (+4 more)

### Community 79 - "test_api_strava.py"
Cohesion: 0.21
Nodes (12): token_response(), connect(), mock_router(), test_callback_stores_encrypted_tokens(), test_callback_with_unknown_state_is_rejected(), test_callback_without_private_activities_scope(), test_connect_redirects_to_strava_with_state(), test_connect_without_strava_keys_explains_what_to_do() (+4 more)

### Community 80 - "garmin_push.py"
Cohesion: 0.20
Nodes (6): push(), PushError, remove(), _save(), _session(), update_workout()

### Community 81 - "conftest.py"
Cohesion: 0.18
Nodes (7): client(), db(), engine(), fake(), session_factory(), settings(), test_settings()

### Community 82 - "compilerOptions"
Cohesion: 0.11
Nodes (18): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, noEmit, noFallthroughCasesInSwitch (+10 more)

### Community 83 - "local_today"
Cohesion: 0.17
Nodes (8): local_today(), week_of(), test_dashboard_routes(), test_intensity_minutes_route_and_goal(), test_steps_floors_route_and_goals(), test_api_default_quit_date_then_saved(), test_api_rejects_bad_days(), test_api_write_correct_and_delete_a_cigarette_day()

### Community 84 - "Ouvrir l'app sur ton téléphone avec Tailscale (phase 6b)"
Cohesion: 0.12
Nodes (15): 1. Choisir un mot de passe, 2. Le mode « production », 3. Les sauvegardes, 4. Installer l'app et l'utiliser hors ligne, 5. Ce que GitHub vérifie maintenant, Sécuriser l'app et l'installer (phase 6a), 1. Installer Tailscale sur le PC (Windows), 2. Choisir le mot de passe de l'app (+7 more)

### Community 85 - "tools/race.py"
Cohesion: 0.18
Nodes (9): Coach musculation et cardio, Méthode, Plan de la semaine, Ton rôle, _clock(), DistanceInput, get_pace_zones(), get_race_predictions() (+1 more)

### Community 86 - "garmin_workouts.py"
Cohesion: 0.19
Nodes (4): create_and_schedule(), GarminWorkoutApi, _id(), remove()

### Community 87 - "logging"
Cohesion: 0.20
Nodes (5): configure_logging(), redact_secrets(), SecretRedactingFilter, test_filter_redacts_secrets_passed_as_arguments(), test_redact_secrets()

### Community 88 - "test_migrations.py"
Cohesion: 0.19
Nodes (5): test_activity_town_and_start_are_read_back_from_raw_payloads(), test_downgrade_removes_everything(), test_floors_are_read_back_from_raw_payloads(), test_intensity_minutes_are_read_back_from_raw_payloads(), test_migrations_match_models()

### Community 89 - "test_weights.py"
Cohesion: 0.22
Nodes (8): map_weights(), WeightRecord, test_garmin_weight_never_overwrites_a_weigh_in_typed_in_the_app(), test_last_weigh_in_is_carried_forward(), test_no_weigh_in_at_all_means_no_weight(), test_provider_looks_a_year_back_for_weigh_ins(), test_weights_are_converted_and_the_last_of_the_day_wins(), weigh_in()

### Community 90 - "countries.py"
Cohesion: 0.22
Nodes (6): _countries(), Country, _country_at_rounded(), _in_polygon(), _in_ring(), _nearest_coast()

### Community 91 - "Feuille de route"
Cohesion: 0.14
Nodes (14): En plus (demandes de FRANKS), Feuille de route, Phase 0 : critères d'acceptation, Phase 1a : critères d'acceptation, Phase 2a : critères d'acceptation, Phase 2b : critères d'acceptation, Phase 3a : critères d'acceptation, Phase 3b : critères d'acceptation (+6 more)

### Community 92 - "prompts/__init__.py"
Cohesion: 0.23
Nodes (7): load(), parse(), Prompt, system_prompt(), variant(), test_each_coach_has_its_own_tools_and_prompt(), test_prompts_are_versioned_files()

### Community 93 - "add_run"
Cohesion: 0.26
Nodes (9): add_run(), steady_stream(), test_best_segment_finds_the_fast_part(), test_efforts_of_a_run_with_streams(), test_exclude_a_run(), test_heart_rate_from_the_profile_is_used(), test_race_route_insufficient_then_ok(), test_target_race_plan_and_feasibility() (+1 more)

### Community 95 - "@playwright/test"
Cohesion: 0.38
Nodes (3): FolderName, openTab(), @playwright/test

### Community 96 - "updates"
Cohesion: 0.17
Nodes (11): npm, python, patterns, patterns, interval, updates, directory, groups (+3 more)

### Community 97 - "race/plan.py"
Cohesion: 0.25
Nodes (7): feasibility(), FeasibilityResult, hill_allowance(), pace_plan(), PacePlan, Split, test_feasibility()

### Community 98 - "dependencies"
Cohesion: 0.18
Nodes (11): dependencies, country-flag-emoji-polyfill@0.1.10, @fontsource/barlow@^5.3.0, @fontsource/barlow-semi-condensed@^5.3.0, react@^19.2.8, react-dom@^19.2.8, react-router-dom@^7.18.4, country-flag-emoji-polyfill (+3 more)

### Community 99 - "scripts"
Cohesion: 0.18
Nodes (11): scripts, build, dev, format, format:check, lint, preview, test (+3 more)

### Community 100 - "repositories/smoking.py"
Cohesion: 0.31
Nodes (4): SmokingDay, delete_day(), list_days(), upsert_day()

### Community 101 - "2026_10_18_1320-5974acb22aa2_daily_intensity_minutes.py"
Cohesion: 0.33
Nodes (4): _fill_from_raw_payloads(), _minutes(), _stats(), upgrade()

### Community 102 - "Architecture"
Cohesion: 0.25
Nodes (8): Architecture, Backend (`backend/`), Données de santé, Frontend (`frontend/`), Qualité, Synchronisation Strava, Synchronisations planifiées, Vue d'ensemble

### Community 103 - "GitHub pour ce projet, pas à pas"
Cohesion: 0.25
Nodes (7): Fusionner, GitHub pour ce projet, pas à pas, Le vocabulaire en 6 mots, Lire un message de commit, Notre façon de travailler, Relire une PR, Récupérer le code sur ton PC (WSL2)

### Community 105 - "Règles communes aux deux coachs"
Cohesion: 0.29
Nodes (6): Format, Garde-fous (obligatoires), Mémoire, Règles communes aux deux coachs, Sécurité des contenus, Tes données

### Community 106 - "save_target"
Cohesion: 0.43
Nodes (3): delete_target(), get_target(), save_target()

### Community 107 - "vite.config.ts"
Cohesion: 0.29
Nodes (6): vite@^8.3.0, vite-plugin-pwa@^2.0.0, @vitejs/plugin-react@^6.1.1, vite, vite-plugin-pwa, @vitejs/plugin-react

### Community 109 - "ADR 0001 : stack et outils"
Cohesion: 0.33
Nodes (5): ADR 0001 : stack et outils, Conséquences, Contexte, Décision, Écart par rapport au plan

### Community 110 - "Règles"
Cohesion: 0.33
Nodes (4): Commandes, Modèle de données, Règles, activity()

### Community 111 - "Les outils du projet, simplement"
Cohesion: 0.33
Nodes (5): Côté Python (`backend/`), Côté web (`frontend/`), Les commandes à retenir, Les outils du projet, simplement, Lire un test

### Community 112 - "Connecter ton compte Strava"
Cohesion: 0.33
Nodes (6): 1. Créer l'application Strava, 2. Mettre les clés dans `.env`, 3. Autoriser l'application, 4. Lancer la première synchronisation, Ce que fait l'app avec ton accès, Connecter ton compte Strava

### Community 113 - "Clé API pour les coachs IA (Gemini, ou Claude)"
Cohesion: 0.33
Nodes (5): Ce qui est envoyé au modèle, Claude (Anthropic), en option, Clé API pour les coachs IA (Gemini, ou Claude), Gemini (Google AI Studio), Le budget

### Community 114 - "Évaluer les coachs IA (`make eval`)"
Cohesion: 0.33
Nodes (5): Ce qui se passe, Commandes, Comparer deux versions d'un prompt, À savoir, Évaluer les coachs IA (`make eval`)

### Community 115 - ".oxlintrc.json"
Cohesion: 0.33
Nodes (5): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema

### Community 116 - "App Sport"
Cohesion: 0.33
Nodes (6): App Sport, Configuration des clés, Documentation, Installation (Windows avec WSL2), Lancer l'application, Tests et qualité

### Community 117 - "Récupérer tes données Garmin"
Cohesion: 0.40
Nodes (4): Données de test, Option 1 : synchronisation automatique (bibliothèque `garminconnect`), Option 2 : import de fichiers (plan B, toujours disponible), Récupérer tes données Garmin

### Community 118 - ".prettierrc.json"
Cohesion: 0.40
Nodes (4): printWidth, semi, singleQuote, trailingComma

### Community 119 - "pull_request_template.md"
Cohesion: 0.40
Nodes (4): Comment tester, Pourquoi, Quoi, Vérifications

### Community 122 - "autostart.sh"
Cohesion: 1.00
Nodes (3): ps(), autostart.sh script, start_now()

### Community 123 - "start-app.sh"
Cohesion: 0.50
Nodes (3): NVM_DIR, PATH, start-app.sh script

## Knowledge Gaps
- **3 isolated node(s):** `app-sport-backend`, `PATH`, `NVM_DIR`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1120 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Security and PWA (phase 6a)` connect `CLAUDE.md` to `App.tsx`, `api/auth.py`, `main.py`?**
  _High betweenness centrality (0.097) - this node is a cross-community bridge._
- **Are the 75 inferred relationships involving `Settings` (e.g. with `get_status()` and `login()`) actually correct?**
  _`Settings` has 75 INFERRED edges - model-reasoned connections that need verification._
- **What connects `app-sport-backend`, `PATH`, `NVM_DIR` to the rest of the system?**
  _3 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `client.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.03827483196415235 - nodes in this community are weakly interconnected._
- **Why does `Settings` connect `Settings` to `test_coach.py`, `run.py`, `api/strava.py`, `ToolContext`, `test_evals.py`, `test_coach_gemini.py`, `test_coach_longevity_plan.py`, `api/coach.py`, `api/auth.py`, `main.py`, `maps.py`, `health_data.py`, `test_plan_workouts.py`, `api/goals.py`, `test_longevity.py`, `api/race.py`, `jobs.py`, `api/sync.py`, `garmin_connect.py`, `dashboards.py`, `plan_workouts.py`, `api/smoking.py`, `conftest.py`, `month_budget`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Should `format.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.04846491228070175 - nodes in this community are weakly interconnected._
- **Why does `Garmin activities, health screen, load (phase 3a)` connect `services/goals.py` to `HealthPage.tsx`, `Activity`, `test_evals.py`, `repositories/activities.py`, `CLAUDE.md`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._