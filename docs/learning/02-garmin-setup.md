# Récupérer tes données Garmin

Deux possibilités. La première est automatique mais fragile, la seconde est manuelle mais fiable.

## Option 1 : synchronisation automatique (bibliothèque `garminconnect`)

1. Dans `.env`, renseigne ton identifiant Garmin Connect :
   ```bash
   GARMIN_EMAIL=ton.email@exemple.com
   GARMIN_PASSWORD=ton_mot_de_passe
   ```
2. Lance `make dev`, ouvre http://localhost:5173/sources et clique sur « Synchroniser maintenant »
   dans la carte Garmin.
3. La première synchronisation récupère les 90 derniers jours de santé (réglable avec
   `GARMIN_INITIAL_DAYS`), puis chaque synchronisation ne relit que les derniers jours.
4. Les **activités** (avec FC, GPS et courbes) arrivent dans la même synchro : les plus récentes
   d'abord, puis l'historique complet petit à petit (500 activités par passage). Les mêmes séances
   envoyées aussi à Strava ne sont comptées qu'une fois.

Après la première connexion, l'app enregistre une session Garmin dans `~/.app_sport/garmin`
(lisible par toi seul, hors du dépôt) : le mot de passe n'est plus réutilisé tant que la session
reste valide.

**Ce que tu dois savoir** :
- Cette bibliothèque n'est **pas officielle**. Garmin peut la casser à tout moment, par exemple en
  changeant sa page de connexion. Dans ce cas la synchro apparaît en « Échec » dans l'historique,
  et tout le reste de l'app continue de fonctionner.
- Si ton compte active un jour la double authentification (MFA), la synchro automatique échouera ;
  on adaptera alors la connexion.
- Garmin limite les requêtes : un statut « Partielle » veut dire « on reprendra au prochain passage ».

## Option 2 : import de fichiers (plan B, toujours disponible)

Dans la carte « Importer un fichier » de l'écran Sources, tu peux envoyer :

- **Le modèle CSV** [`docs/templates/health-import-template.csv`](../templates/health-import-template.csv) :
  une ligne par jour, les colonnes vides sont acceptées, les virgules décimales aussi. Durées en
  minutes.
- **L'export officiel Garmin** : sur Garmin Connect, *Compte > Gestion des données > Exporter vos
  données*. Garmin t'envoie une archive par e-mail ; importe les fichiers
  `DI_CONNECT/DI-Connect-Wellness/*_sleepData.json`.

⚠️ Le format de l'export Garmin n'est pas documenté par Garmin. Le lecteur a été écrit d'après les
fichiers connus ; dès que tu as ton export, on le testera sur un vrai fichier et on l'ajustera si
besoin. Les lignes illisibles sont signalées en avertissement, jamais importées en silence.

Réimporter le même fichier ne crée pas de doublons : les jours déjà présents sont mis à jour.

## Données de test

Pour développer sans aucun compte : `make seed` crée un an d'activités et de nuits réalistes
(source « Données de test »), et `make seed-clear` les efface sans toucher à tes vraies données.
