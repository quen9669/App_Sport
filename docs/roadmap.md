# Feuille de route

> **Le référentiel prime** : `quen9669/Referentiel-Portfolio` (`REGLES.md`, fiche `apps/app-sport.md`,
> section 4 « Écarts à corriger »). Tout ce qui ci-dessous le contredit est remplacé par l'écart
> `SPT-xx` indiqué. Code d'expédition `EXP-04`, ligne dominante 🟣 `ML`, état dans `expedition.yaml`.

| Phase | Contenu | État |
|---|---|---|
| 0 | Cadrage et squelette : monorepo, outils, tests, CI | ✅ Terminé |
| 1a | Modèle de données, connexion et synchro Strava | ✅ Terminé |
| 1b | Garmin (bibliothèque + import de fichiers), synchro planifiée, données synthétiques, écran Sources | ✅ Terminé |
| 2a | Profil, poids, classification des activités, objectifs et tableau de bord | ✅ Terminé |
| 2b | Saisie des séances de musculation, historique des semaines | ✅ Terminé |
| 3a | Activités Garmin (Strava en complément), écran Santé, charge d'entraînement | ✅ Terminé |
| 3b | Carte interactive, heatmap, détail d'une activité, lieux des séances sans GPS | ✅ Terminé |
| 4 | Prédicteur de course et allures | ✅ Terminé |
| 5a | Moteur des coachs IA, coach musculation/cardio, écran de discussion | ✅ Terminé |
| 5b | Coach longévité, plan de semaine proposé, banc d'évaluation | ✅ Terminé |
| 6a | Connexion par mot de passe, durcissement, sauvegardes, PWA hors ligne | ✅ Terminé |
| 6b | Mise en ligne (PC + Tailscale) et installation sur le téléphone | ✅ Terminé |
| 6c | Hébergement sur le VPS (Coolify, projet à part, SQLite), alignement sur le socle commun | 🚧 En cours |
| 7a | Écarts P1 : coach via OmniRoute (SPT-01), plus de budget dans le code (SPT-02) | ✅ Fusionné, vérification sur le VPS à faire |
| 7b | Écarts P2 : sauvegarde commune (SPT-09), coffre (SPT-10), charte Lignes (SPT-03, SPT-04), gouvernance visible (SPT-11) | ⏳ À faire |
| 7c | Scène 3D d'accueil « la semaine » (SPT-05), après la bibliothèque (LIB-03) | ⏳ À faire |
| 7d | Écarts P3 : `/health` commun, `/vitrine.json`, `obs-net` (SPT-06) ✅, badge Longévité (SPT-08) | ⏳ SPT-08 à définir |

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
      (remplacée par un pictogramme + libellé, traces en violet `--line-ml` : SPT-04)
- [x] Filtres par sport, période et distance ; seuls les tracés visibles sont envoyés, simplifiés
      (Douglas-Peucker) selon le zoom
- [x] Un tap sur un tracé : résumé et lien vers le détail ; liste des activités de la zone affichée
- [x] Heatmap des zones les plus fréquentées
- [x] Séances sans GPS placées sur un lieu : muscu à Jims Gare, le reste à Jims Gasperich par défaut,
      modifiable par séance et dans « Mes lieux »
- [x] Détail d'une activité : carte, profil d'altitude, allure (ou vitesse) et FC ; le curseur des
      graphiques déplace un point sur la carte

## Phase 4 : critères d'acceptation

- [x] VDOT (Jack Daniels) et Riegel, testés sur les tables VDOT publiées (40, 50, 60 : à 0,5 % près)
- [x] Forme estimée sur les sorties des 120 derniers jours (sorties entières et meilleurs 5/10 km,
      FC par la méthode de Swain), poids divisé par deux tous les 45 jours, avec une fourchette
- [x] Message clair et aucun temps affiché si les données sont insuffisantes
- [x] Temps prédits (5 km, 10 km, semi, marathon) avec fourchette, zones d'allure d'entraînement
- [x] Course visée : plan d'allure (négative split, dénivelé), passages au km, faisabilité
- [x] Une sortie peut être exclue du calcul à la main

## Phase 5a : critères d'acceptation

- [x] Moteur d'agent : le coach lit les données par des outils (13 outils typés, entrées validées),
      jamais l'export complet ; aucune position GPS envoyée
- [x] Réponse affichée au fil de l'eau (SSE), avec les données consultées (« lit ton sommeil… »)
- [x] Coût de chaque appel journalisé (jetons, cache, latence), budget mensuel (10 € par défaut ; **retiré** par SPT-02, le budget se pilote dans OmniRoute) :
      alerte à 80 %, arrêt net à 100 %
- [x] Cache de prompt, résumés par le modèle léger, historique compacté
- [x] Mémoire : le coach propose, FRANKS accepte, corrige ou oublie
- [x] Prompts versionnés dans des fichiers, garde-fous santé (pas de diagnostic, renvoi au médecin)
- [x] Tout est testé sans clé API (faux modèle) ; sans clé, l'écran explique quoi faire

## Phase 5b : critères d'acceptation

- [x] Coach longévité (page « Longévité ») : pas, étages, minutes d'intensité, VO2max, zones
      cardio, sommeil, jours sans cigarette ; distingue le bien établi de l'incertain, aucun
      complément alimentaire, pas un avis médical
- [x] Plan de semaine proposé par le coach muscu/cardio sous forme de carte (Accepter, Modifier,
      Refuser) ; le plan accepté s'affiche sur l'Accueil
- [x] Banc d'évaluation : 8 scénarios « golden » sur données synthétiques, contrôles automatiques,
      LLM-juge (pertinence, prudence, honnêteté), rapport comparant deux versions de prompt
- [x] `make eval` se lance à la main (appels payants, plafond `--max-eur`) ; la CI le teste avec
      le faux modèle, sans jamais appeler l'API

## Phase 6a : critères d'acceptation

- [x] Un mot de passe (`make set-password`, seule son empreinte Argon2 va dans `.env`), écran de
      connexion en français, session gardée 30 jours par appareil (cookie `HttpOnly`, `Secure` en
      production, `SameSite=Strict`), « Se déconnecter » efface aussi les données hors ligne
- [x] Après 5 mauvais mots de passe, connexion bloquée 15 minutes ; tentatives journalisées sans le
      mot de passe ; toutes les routes `/api` protégées sauf la santé du serveur, la connexion et le
      retour de Strava
- [x] `make prod` : un seul serveur sert l'interface et l'API ; refuse de démarrer sans mot de passe
- [x] En-têtes de sécurité (CSP stricte sans script tiers, HSTS en production, pas d'intégration
      dans un autre site), documentation de l'API masquée en production
- [x] Sauvegarde de la base chaque nuit (14 gardées), `make backup` et `make restore`
      (**retirées** par SPT-09 : seule l'archive commune de la nuit sauvegarde le volume)
- [x] CI : audit des dépendances Python et npm, recherche de secrets ; Dependabot chaque semaine
- [x] PWA : bouton « Installer l'app », ouverture hors ligne avec les dernières données et la date,
      modifications refusées hors ligne avec un message clair, bannière « Nouvelle version »

## Phase 6b : critères d'acceptation

Remplacée par la phase 6c (VPS). Hébergement choisi alors par FRANKS : son PC et Tailscale (guide `docs/learning/06-telephone-tailscale.md`).

- [x] `make autostart` : l'app démarre en mode production à chaque ouverture de session Windows,
      sans fenêtre, journal dans `backend/data/prod.log` ; refuse sans mot de passe
- [x] L'app s'ouvre en HTTPS depuis le téléphone (`tailscale serve`), visible seulement de ses
      appareils, jamais publique
- [x] Retour Strava sur l'adresse Tailscale (`STRAVA_REDIRECT_URI`, domaine de rappel Strava)
- [x] L'app installée sur son Android, ouverture hors ligne avec les dernières données

## En plus (demandes de FRANKS)

- [x] Catégorie « Déplacement » : marche et vélo de moins de 5 km, hors objectifs de sport mais
      dans la charge d'entraînement
- [x] Suivi des jours sans cigarette (depuis le 1er septembre 2026, date modifiable) : jours avec
      cigarette saisis à la main, séries et bilan par mois, gardés pour la future partie longévité
- [x] Pas et étages montés/descendus (Garmin) sur la page Santé, avec les objectifs « Pas par
      jour » (moyenne de la semaine) et « Étages montés » (par semaine)
- [x] Nouvelle interface épurée, esprit Garmin Connect en rouge, avec le logo QF (rouge, Barlow et
      logo **remplacés** par la charte Lignes : SPT-03) : menu en 3
      dossiers (Entraînement, Santé, Coach) et leurs onglets, Réglages derrière la roue dentée,
      barre du bas sur téléphone et barre latérale sur PC, Santé découpée en onglets
- [x] Séances de course du plan détaillées en étapes (échauffement, fractions, récupération,
      retour au calme) avec allures cibles calculées par l'app, modifiables, et envoyées une par
      une sur la montre Garmin depuis Mon plan
- [x] Onglet Santé › Bilan longévité : un bilan par levier (minutes d'intensité, muscu, VO2max, pas,
      sommeil, FC au repos, poids, IMC) comparé aux repères publics avec le niveau de preuve,
      repères OMS après l'arrêt de la cigarette et comparaison avant / depuis l'arrêt des données
      Garmin ; le coach longévité lit le même bilan

## Phase 6c : critères d'acceptation

Hébergement sur le VPS (Coolify 4.7.5, projet `app-sport`, voir `docs/learning/07-vps-coolify.md`).

- [x] `docker-compose.yml` : conteneur `sport-app` durci (non root, lecture seule, 512 Mo), sidecar
      Tailscale (https://app-sport.<tailnet>.ts.net), aucun port publié, SQLite dans le volume nommé
      `app-sport-data`
- [x] Page Réglages › Monitoring et tableau de bord Grafana en JSON dans le dépôt
      (`deploy/grafana/app-sport.json`, copié dans le socle par la session Référentiel)
- [x] Pointeur vers le référentiel en tête de `CLAUDE.md` et `expedition.yaml` à la racine (SPT-07)
- [x] Sidecar de sauvegarde `sport-backup` retiré : voir SPT-09 (phase 7b)
- [ ] Secrets reçus uniquement du coffre OpenBao : voir SPT-10 (phase 7b)

## Phase 7a : écarts P1 (urgent)

- [x] **SPT-01** (R-05, R-06) : le coach passe uniquement par OmniRoute. Les anciennes clés
      Anthropic et Gemini ont été révoquées le 2026-11-17, le coach est peut-être en panne.
      `OMNIROUTE_API_KEY: ${OMNIROUTE_API_KEY}` déclarée dans le compose (valeur déjà dans le coffre,
      `apps/app-sport/OMNIROUTE_API_KEY`), `OMNIROUTE_BASE_URL=http://omniroute:20128/v1`,
      service sur le réseau externe `llm-net` ; un seul client compatible OpenAI remplace
      `gemini.py` et `AnthropicLLM` ; outils, streaming SSE et cache de prompt testés à travers
      OmniRoute ; `GEMINI_API_KEY` et `ANTHROPIC_API_KEY` retirées de `.env.example` et de Coolify.
      Le modèle ne conserve pas les prompts (R-08, données de santé). Le banc d'évaluation
      (`make eval`) passe aussi par OmniRoute.
- [x] **SPT-02** (R-07) : le plafond de 10 €/mois codé dans l'app est supprimé (alerte 80 %, arrêt
      à 100 %, `COACH_MONTHLY_BUDGET_EUR`, carte budget du Monitoring). La clé OmniRoute est payante
      avec un quota fixé par FRANKS dans OmniRoute. Si OmniRoute refuse (quota atteint, clé
      bloquée), le coach passe en ◆ Dégradé avec un message clair, et le reste de l'app
      fonctionne. Le coût par appel peut rester journalisé, sans plafond.
- [ ] Vérifié sur le VPS à travers OmniRoute : outils, streaming SSE, cache de prompt (le modèle est imposé dans OmniRoute, l'app n'en nomme aucun) ;
      `GEMINI_API_KEY`, `ANTHROPIC_API_KEY` et `COACH_MONTHLY_BUDGET_EUR`
      supprimées de Coolify (et du coffre si elles y sont).

## Phase 7b : écarts P2

- [x] **SPT-09** (R-11) : retirer `sport-backup` (rclone vers Drive) et `deploy/backup/` du
      compose, ainsi que la copie de nuit à 03:30 (`services/backup.py`, `make backup` /
      `make restore`) : l'archive commune de la nuit couvre le volume `app-sport-data` (7 jours sur
      Drive, restauration testée le 2026-11-17). Le Monitoring ne surveille plus de « copie de nuit ».
      Le dossier Drive « App Sport » peut ensuite être supprimé par FRANKS.
- [ ] **SPT-10** (R-15) : tout secret vient du coffre OpenBao (`apps/app-sport/`), poussé vers
      Coolify par la synchro ; aucun `.env` réel. Reste à faire par FRANKS : supprimer les `.env`
      réels du PC. Un nouveau secret = une ligne `NOM: ${NOM}` dans le compose, valeur rangée par
      FRANKS dans le coffre.
- [x] **SPT-03** (R-17, R-18, 2026-11-18, icônes PWA comprises) : `styles/theme.css` (rouge `#e20912`, Barlow) remplacé par les
      jetons de `@quen9669/lignes` (ligne dominante `--line-ml`, bouton principal `--action`,
      polices Archivo, IBM Plex Sans, JetBrains Mono auto-hébergées), logo et icônes PWA de la
      bibliothèque. Installation par `.npmrc` sans secret, `NPM_TOKEN` (read:packages) dans le coffre.
- [x] **SPT-04** (2026-11-18, manque : pictogramme « marche », remplacé par `randonnee`) (R-17) : plus de couleur par sport (`--sport-*`) : pictogramme + libellé en neutre
      (pictogrammes manquants à signaler pour la bibliothèque, jamais créés ici), tracés de la
      carte en `--line-ml` seulement, graphiques selon la charte (`--series-*` remplacées).
      Rouge = erreur seulement, ambre ◆ = dégradé, flamme de série en violet.
- [x] **SPT-11** (2026-11-18) (R-23) : la gouvernance se voit : fraîcheur de la synchro Garmin/Strava (🔵 DE),
      complétude des données ✓ (🟢 DG) et source de chaque calcul (TRIMP, ratio aigu/chronique,
      VDOT), avec les composants de la bibliothèque. Carte des couleurs de l'app affichée (légende
      ou page « À propos »).

## Phase 7c : scène 3D d'accueil (après LIB-03)

- [ ] **SPT-05** (R-19) : scène « la semaine » avec `@quen9669/lignes/scene` : carte simple du
      Luxembourg où les tracés se dessinent en violet, pictogrammes course, vélo, musculation,
      randonnée et divers, anneaux d'objectifs, flamme de série, badge « Longévité ». Commence
      quand la bibliothèque a livré le kit 3D (LIB-03).

## Phase 7d : écarts P3

- [x] **SPT-06** (R-16, R-26) : `GET /health` au format commun (● / ◆ / ■ ; coach ◆ si OmniRoute
      refuse) et `GET /vitrine.json` (agrégats seulement : nombre de séances, semaines de série),
      conteneur principal sur le réseau `obs-net` ; son adresse vue depuis `obs-net` est donnée à
      FRANKS pour le blackbox. L'app ne notifie jamais elle-même : un flux planifié pinge son
      contrôle Healthchecks (URL dans le coffre), le bot Telegram « Franks Ops » fait le reste.
- [ ] **SPT-08** : indicateur de longévité (à définir avec FRANKS : VO2max estimée, régularité sur
      12 mois…) avec un badge `ML · Longévité`, en s'appuyant sur le Bilan longévité existant.

## Développements retirés (contraires au référentiel)

- Plafond de budget du coach dans l'app (SPT-02) : le budget se pilote dans OmniRoute.
- Appels directs à Gemini et Anthropic, choix du fournisseur dans l'app (SPT-01).
- Sauvegardes propres à l'app : copie de nuit, `make backup` / `make restore`, sidecar rclone (SPT-09).
- Rouge du logo, Barlow, couleurs par sport et par série (SPT-03, SPT-04).

## Points à surveiller

- **Garmin** : la bibliothèque `garminconnect` n'est pas officielle et peut casser. L'import de
  fichiers FIT/CSV sera toujours disponible en plan B.
- **Strava** : les conditions de l'API encadrent l'usage des données par des outils d'IA. À
  revérifier, d'autant que le coach
  passe par OmniRoute (SPT-01).
- **Quotas Strava** : environ 100 requêtes par 15 minutes et 1 000 par jour ; l'import complet de
  l'historique prendra du temps et reprendra automatiquement.
