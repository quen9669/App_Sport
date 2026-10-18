# Feuille de route

| Phase | Contenu | État |
|---|---|---|
| 0 | Cadrage et squelette : monorepo, outils, tests, CI | ✅ Terminé |
| 1a | Modèle de données, connexion et synchro Strava | ✅ Terminé |
| 1b | Garmin (bibliothèque + import de fichiers), synchro planifiée, données synthétiques, écran Sources | ✅ Terminé |
| 2a | Profil, poids, classification des activités, objectifs et tableau de bord | 🟡 En revue |
| 2b | Saisie des séances de musculation, historique des semaines | ⚪ À faire |
| 3 | Carte interactive et tableaux de bord de santé | ⚪ À faire |
| 4 | Prédicteur de course et allures | ⚪ À faire |
| 5 | Coachs IA (musculation/cardio et longévité) | ⚪ À faire |
| 6 | PWA complète, sécurité, déploiement | ⚪ À faire |

## Phase 0 : critères d'acceptation

- [x] `make test` passe sur le squelette
- [x] `make dev` démarre backend et frontend, la page affiche « Backend OK »
- [x] Lint, format et types vérifiés en local et en CI

## Phase 1a : critères d'acceptation

- [x] Modèle de données et migration Alembic, testée contre les modèles
- [x] Connexion Strava OAuth avec tokens chiffrés et rafraîchis automatiquement
- [x] Import incrémental et historique complet avec reprise, respect des quotas
- [x] Resynchroniser ne crée aucun doublon (tests avec API Strava simulée)
- [ ] Vérifié avec ton vrai compte Strava (quand l'application Strava sera créée)

## Phase 1b : critères d'acceptation

- [x] Interface `HealthDataProvider` avec Garmin (`garminconnect`) et import de fichiers (CSV, export Garmin)
- [x] Synchro planifiée (toutes les 3 h) et manuelle, journalisée, sans doublons
- [x] Données synthétiques réalistes (`make seed`) : un an d'activités et de nuits
- [x] Écran « Sources » : connexion Strava, synchros, import, historique
- [ ] Vérifié avec tes vrais comptes Strava et Garmin
- [ ] Lecteur de l'export Garmin vérifié sur un vrai fichier
- [ ] Fichiers FIT : reportés tant qu'on n'a pas de fichier réel (format du sommeil peu documenté)

## Phase 2a : critères d'acceptation

- [x] Profil (taille, FC max et repos, niveau, blessures) validé côté navigateur et côté serveur
- [x] Pesée rapide en 2 taps depuis l'accueil, courbe sur 30, 90 ou 365 jours avec moyenne 7 jours
- [x] Activités classées musculation / cardio / autre, cours collectifs comptés en musculation,
      correction manuelle jamais écrasée par une resynchro
- [x] Objectifs hebdomadaires (séances, minutes, km), semaine du lundi au dimanche à l'heure de
      Luxembourg, y compris aux changements d'heure
- [x] « 3 muscu + 3 cardio » en un tap, anneaux de progression sur l'accueil (test E2E)

## Points à surveiller

- **Garmin** : la bibliothèque `garminconnect` n'est pas officielle et peut casser. L'import de
  fichiers FIT/CSV sera toujours disponible en plan B.
- **Strava** : les conditions de l'API encadrent l'usage des données par des outils d'IA. À
  revérifier avant la phase 5.
- **Quotas Strava** : environ 100 requêtes par 15 minutes et 1 000 par jour ; l'import complet de
  l'historique prendra du temps et reprendra automatiquement.
