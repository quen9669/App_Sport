# Architecture

## Vue d'ensemble

```mermaid
flowchart LR
    subgraph Appareil["PC ou téléphone Android"]
        PWA["Frontend PWA<br/>React + Vite + TypeScript"]
    end
    subgraph Serveur["Backend (ta machine)"]
        API["API FastAPI<br/>/api/..."]
        DB[("SQLite<br/>(PostgreSQL plus tard)")]
        SCHED["Synchros planifiées<br/>APScheduler"]
    end
    STRAVA["API Strava"]
    GARMIN["Garmin Connect<br/>ou fichiers FIT/CSV"]
    CLAUDE["API Anthropic<br/>(coachs, phase 5)"]

    PWA -- "HTTP JSON" --> API
    API --> DB
    SCHED --> DB
    SCHED --> STRAVA
    SCHED --> GARMIN
    API --> CLAUDE
```

Le **frontend** est une seule base de code pour PC et Android : c'est une application web
installable (PWA). Il ne parle qu'au **backend**, jamais directement à Strava ou Garmin, pour que
les clés secrètes restent côté serveur.

## Backend (`backend/`)

Le code est découpé en couches. Chaque couche ne parle qu'à celle d'en dessous :

| Couche | Dossier | Rôle |
|---|---|---|
| Routes | `app/api/` | Reçoit la requête HTTP, valide les entrées, renvoie la réponse. Aucune logique métier. |
| Services | `app/services/` (phase 1) | La logique : synchroniser, calculer, décider. |
| Accès aux données | `app/repositories/` (phase 1) | Lire et écrire en base. |
| Intégrations | `app/integrations/` (phase 1) | Clients Strava et Garmin. |

Pourquoi ce découpage : on peut tester la logique sans serveur HTTP, et changer de base de données
ou de source de données sans tout réécrire.

Fichiers transverses :
- `app/config.py` : tous les réglages, lus depuis `.env`.
- `app/logging_config.py` : journaux, avec masquage automatique des secrets.

## Frontend (`frontend/`)

| Dossier | Rôle |
|---|---|
| `src/api/` | Tous les appels au backend, typés |
| `src/styles/` | Thème clair et sombre (variables CSS) |
| `src/App.tsx` | Composant racine |
| `e2e/` | Tests de bout en bout Playwright |

## Qualité

La CI GitHub (`.github/workflows/ci.yml`) lance sur chaque PR : lint, vérification des types,
tests unitaires, build du frontend, puis un test de bout en bout dans Chromium.
