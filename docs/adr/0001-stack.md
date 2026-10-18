# ADR 0001 : stack et outils

- **Date** : 2026-10-18
- **Statut** : accepté

Un ADR (Architecture Decision Record) est une fiche courte qui garde la trace d'une décision et
de sa raison, pour ne pas se reposer la question dans six mois.

## Contexte

Application mono-utilisateur, PC et Android, développée sous Windows avec WSL2 par un débutant
qui veut apprendre Python, React et GitHub.

## Décision

| Besoin | Choix | Pourquoi |
|---|---|---|
| Backend | Python + FastAPI + Pydantic v2 | Typage clair, documentation d'API automatique, très répandu en IA |
| Dépendances Python | `uv` | Une commande installe Python et tout le reste, versions figées dans `uv.lock` |
| Base de données | SQLite, code compatible PostgreSQL (SQLAlchemy) | Un simple fichier pour commencer, migrable plus tard |
| Frontend | React + Vite + TypeScript strict | Écosystème le plus documenté ; TypeScript strict attrape les erreurs avant l'exécution |
| PC + Android | PWA (`vite-plugin-pwa`) | Une seule base de code, installable sans store |
| Dépendances JS | `npm` | Livré avec Node : un outil de moins à apprendre |
| Qualité Python | ruff + mypy `--strict` | ruff remplace plusieurs outils (lint et format) ; mypy a des messages pédagogiques |
| Qualité TypeScript | oxlint + Prettier + `tsc` | oxlint est le linter fourni par le modèle Vite actuel, très rapide ; Prettier formate |
| Tests | pytest, Vitest + Testing Library, Playwright | Les standards de chaque écosystème |
| Commandes | `make` | Une porte d'entrée unique, disponible sous WSL2 |

## Écart par rapport au plan

Le plan prévoyait ESLint. Le modèle officiel Vite fournit désormais oxlint, qui couvre les mêmes
règles React et TypeScript utiles ici en beaucoup plus rapide. On garde oxlint ; ESLint pourra être
ajouté si une règle manque.

## Conséquences

- Il faut Node 22 et `uv` sur la machine (voir README).
- Les deux moitiés du projet ont chacune leurs outils, mais `make` les unifie.
