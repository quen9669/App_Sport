# Feuille de route

| Phase | Contenu | État |
|---|---|---|
| 0 | Cadrage et squelette : monorepo, outils, tests, CI | ✅ Terminé |
| 1a | Modèle de données, connexion et synchro Strava | ✅ Terminé |
| 1b | Garmin (bibliothèque + import de fichiers), synchro planifiée, données synthétiques, écran Sources | ✅ Terminé |
| 2a | Profil, poids, classification des activités, objectifs et tableau de bord | ✅ Terminé |
| 2b | Saisie des séances de musculation, historique des semaines | ✅ Terminé |
| 3a | Activités Garmin (Strava en complément), écran Santé, charge d'entraînement | ✅ Terminé |
| 3b | Carte interactive, heatmap, détail d'une activité, lieux des séances sans GPS | 🟡 En revue |
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

## Phase 2b : critères d'acceptation

- [x] Saisie des séances en salle : catalogue de 32 exercices en français ou saisie libre,
      dernière charge proposée, « Répéter la série » en un tap, brouillon conservé si l'app se ferme
- [x] Pas de double comptage avec une activité Strava de musculation (liée, ou à moins de 3 h)
- [x] Historique des 12 dernières semaines (barres en % de la cible, avec tableau) et série de
      semaines réussies

## Phase 3a : critères d'acceptation

- [x] Activités importées depuis Garmin Connect (FC, GPS, courbes), historique importé petit à petit
- [x] Strava en complément : une copie d'une activité Garmin n'est comptée qu'une fois, les cas
      douteux restent visibles avec « Masquer » en un tap
- [x] Correction de catégorie et séance de muscu liée suivent l'activité gardée
- [x] Écran Santé : sommeil (durée, score, régularité), FC repos, HRV, poids sur 7, 30 ou 90 jours
- [x] Charge par semaine (TRIMP avec la FC, sinon durée × effort estimé) et ratio aigu/chronique
      avec mise en garde
- [x] Vérifié sur tes vraies données Garmin (FC, sommeil, HRV, poids, minutes d'intensité) ; l'id
      Garmin dans l'`external_id` Strava reste à vérifier quand Strava sera connecté

## Phase 3b : critères d'acceptation

- [x] Carte de tous les tracés (Leaflet, rendu canvas, fond OpenStreetMap), couleur par sport
- [x] Filtres par sport, période et distance ; seuls les tracés visibles sont envoyés, simplifiés
      (Douglas-Peucker) selon le zoom
- [x] Un tap sur un tracé : résumé et lien vers le détail ; liste des activités de la zone affichée
- [x] Heatmap des zones les plus fréquentées
- [x] Séances sans GPS placées sur un lieu : muscu à Jims Gare, le reste à Jims Gasperich par défaut,
      modifiable par séance et dans « Mes lieux »
- [x] Détail d'une activité : carte, profil d'altitude, allure (ou vitesse) et FC ; le curseur des
      graphiques déplace un point sur la carte

## Points à surveiller

- **Garmin** : la bibliothèque `garminconnect` n'est pas officielle et peut casser. L'import de
  fichiers FIT/CSV sera toujours disponible en plan B.
- **Strava** : les conditions de l'API encadrent l'usage des données par des outils d'IA. À
  revérifier avant la phase 5.
- **Quotas Strava** : environ 100 requêtes par 15 minutes et 1 000 par jour ; l'import complet de
  l'historique prendra du temps et reprendra automatiquement.
