# App Sport

Application de sport personnelle, utilisable sur PC et sur téléphone Android (PWA). Elle récupérera
mes activités Strava et mes données de santé Garmin, suivra mes objectifs hebdomadaires, affichera
une carte de mes sorties, prédira mes temps de course et proposera deux coachs IA.

> Cette application donne des conseils d'entraînement, pas un avis médical.

**État actuel : phase 1** (ingestion Strava et Garmin, écran Sources). Voir [docs/roadmap.md](docs/roadmap.md).

## Installation (Windows avec WSL2)

Toutes les commandes se tapent dans le terminal **Ubuntu** de WSL2, pas dans PowerShell.

1. **Outils de base** :
   ```bash
   sudo apt update && sudo apt install -y git make curl
   ```
2. **uv** (gère Python et ses dépendances) :
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
   Puis ferme et rouvre le terminal. `uv` installera Python 3.12 tout seul si besoin.
3. **Node.js 22** (pour le frontend), via nvm :
   ```bash
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
   # ferme et rouvre le terminal, puis :
   nvm install 22
   ```
4. **Récupérer le projet et installer les dépendances** :
   ```bash
   git clone https://github.com/quen9669/App_Sport.git
   cd App_Sport
   make install
   ```
   `make install` crée aussi ton fichier `.env` à partir de `.env.example`. Ce fichier contiendra
   tes clés secrètes ; il n'est jamais envoyé sur GitHub.

> Astuce : garde le projet dans le système de fichiers Linux (`~/App_Sport`), pas dans `/mnt/c/...`.
> C'est beaucoup plus rapide sous WSL2.

## Lancer l'application

```bash
make dev
```

- Frontend : http://localhost:5173 (doit afficher « Backend OK »), écran des sources sur
  http://localhost:5173/sources
- API et sa documentation interactive : http://localhost:8000/docs

`Ctrl+C` arrête les deux. Pas encore de compte configuré ? `make seed` remplit la base avec un an
de données de test réalistes (`make seed-clear` pour les retirer).

## Tests et qualité

```bash
make test        # tests unitaires backend et frontend
make e2e-install # une seule fois : télécharge le navigateur des tests E2E
make test-e2e    # test de bout en bout dans un vrai navigateur
make check       # tout ce que la CI vérifie (lint, types, tests)
make help        # liste de toutes les commandes
```

## Configuration des clés

Les clés se mettent dans `.env` (voir les commentaires de `.env.example`). `make install` génère
automatiquement `TOKEN_ENCRYPTION_KEY`, qui chiffre les tokens stockés.

- **Strava** : suis [docs/learning/01-strava-setup.md](docs/learning/01-strava-setup.md).
- **Garmin** : suis [docs/learning/02-garmin-setup.md](docs/learning/02-garmin-setup.md).
- **Anthropic** : guide à venir avec la phase 5.

## Documentation

- [docs/architecture.md](docs/architecture.md) : vue d'ensemble
- [docs/roadmap.md](docs/roadmap.md) : phases et reste à faire
- [docs/adr/](docs/adr/) : décisions d'architecture
- [docs/learning/](docs/learning/) : guides pour apprendre (GitHub, outils)
- [CLAUDE.md](CLAUDE.md) : mémo technique du projet
