# Modèle de données

Schéma créé par la migration Alembic initiale (`backend/alembic/versions/`). Les modèles Python sont
dans `backend/app/db/models/`. Les tables des phases suivantes (objectifs, musculation, course,
coachs) arriveront avec leur propre migration.

```mermaid
erDiagram
    activity ||--o| activity_stream : "a (0 ou 1)"
    activity {
        int id PK
        string source "strava, file_import..."
        string external_id "id chez la source"
        string sport_type "Run, Ride, WeightTraining, Workout..."
        datetime start_time "UTC"
        string timezone "Europe/Luxembourg"
        int elapsed_time_s
        int moving_time_s
        float distance_m
        float elevation_gain_m
        float average_speed_mps
        float average_heartrate
        float max_heartrate
        text summary_polyline "tracé simplifié"
    }
    activity_stream {
        int id PK
        int activity_id FK
        string stream_types "time,latlng,heartrate..."
        int point_count
        blob data "JSON compressé zlib"
    }
    raw_payload {
        int id PK
        string source
        string kind "activity, activity_streams..."
        string external_id
        json payload "réponse brute de l'API"
    }
    source_credential {
        int id PK
        string source "unique"
        text access_token_encrypted
        text refresh_token_encrypted
        datetime expires_at
        string scope
    }
    sleep_night {
        int id PK
        string source
        date night_date "date du réveil"
        int duration_s
        int score
        int deep_s
        int rem_s
        int resting_heartrate
        float hrv_ms
        int body_battery_wake
    }
    daily_health {
        int id PK
        string source
        date day
        int resting_heartrate
        float hrv_ms
        int stress_avg
        int steps
        float vo2max
    }
    sync_log {
        int id PK
        string source
        string kind "manual, scheduled, backfill"
        string status "running, success, partial, failed"
        datetime started_at
        int items_created
        int items_updated
        text error
    }
    sync_cursor {
        string name PK "strava_backfill"
        string value "position atteinte"
        bool completed
    }
    user_profile {
        int id PK
        string timezone
        string unit_system
    }
```

## Règles

- **Pas de doublons** : contrainte unique `(source, external_id)` sur `activity`, `(source, night_date)`
  sur `sleep_night`, `(source, day)` sur `daily_health`, `(source, kind, external_id)` sur
  `raw_payload`. Les écritures sont des « upserts » (insère ou met à jour).
- **Unités SI** en base (secondes, mètres, m/s). Conversion en km, min/km, km/h à l'affichage.
- **Dates en UTC** (type `UTCDateTime`), affichées en heure de Luxembourg par le frontend.
- **Données brutes** dans `raw_payload`, séparées des tables normalisées : on peut tout reconstruire
  sans rappeler l'API.
- **Tokens chiffrés** (Fernet) dans `source_credential` ; la clé est dans `.env`, jamais en base.
- **Streams compacts** : un seul blob compressé par activité plutôt qu'une ligne par seconde
  (une sortie d'une heure = environ 3 600 points par série).

## Commandes

```bash
make db-upgrade                      # appliquer les migrations
make db-revision m="add goal table"  # générer une migration après avoir modifié un modèle
```

Le test `backend/tests/test_migrations.py` échoue si un modèle change sans migration.
