# Feuille de route

| Phase | Contenu | État |
|---|---|---|
| 0 | Cadrage et squelette : monorepo, outils, tests, CI | 🟡 En revue |
| 1 | Ingestion : modèle de données, Strava, Garmin, synchros, données synthétiques | ⚪ À faire |
| 2 | Profil, métriques et objectifs hebdomadaires | ⚪ À faire |
| 3 | Carte interactive et tableaux de bord de santé | ⚪ À faire |
| 4 | Prédicteur de course et allures | ⚪ À faire |
| 5 | Coachs IA (musculation/cardio et longévité) | ⚪ À faire |
| 6 | PWA complète, sécurité, déploiement | ⚪ À faire |

## Phase 0 : critères d'acceptation

- [x] `make test` passe sur le squelette
- [x] `make dev` démarre backend et frontend, la page affiche « Backend OK »
- [x] Lint, format et types vérifiés en local et en CI

## Points à surveiller

- **Garmin** : la bibliothèque `garminconnect` n'est pas officielle et peut casser. L'import de
  fichiers FIT/CSV sera toujours disponible en plan B.
- **Strava** : les conditions de l'API encadrent l'usage des données par des outils d'IA. À
  revérifier avant la phase 5.
- **Quotas Strava** : environ 100 requêtes par 15 minutes et 1 000 par jour ; l'import complet de
  l'historique prendra du temps et reprendra automatiquement.
