# Connecter ton compte Strava

À faire une seule fois. Compte environ 5 minutes.

## 1. Créer l'application Strava

1. Connecte-toi sur https://www.strava.com, puis ouvre https://www.strava.com/settings/api.
2. Remplis le formulaire :
   - **Application Name** : `App Sport perso` (ce que tu veux)
   - **Category** : `Training`
   - **Website** : `http://localhost:5173`
   - **Authorization Callback Domain** : `localhost`
3. Ajoute une icône (n'importe quelle image), accepte les conditions et valide.
4. Strava affiche ton **Client ID** (un nombre) et ton **Client Secret** (clique sur « Show »).

## 2. Mettre les clés dans `.env`

Ouvre le fichier `.env` à la racine du projet (créé par `make install`) et complète :

```bash
STRAVA_CLIENT_ID=123456
STRAVA_CLIENT_SECRET=ton_secret_ici
```

Ne partage jamais le secret et ne le colle dans aucun message : `.env` reste sur ta machine, il est
ignoré par git.

## 3. Autoriser l'application

1. Lance `make dev`.
2. Ouvre http://localhost:8000/api/strava/connect (en phase 1b, un bouton « Connecter Strava » le
   fera pour toi).
3. Sur la page Strava, **laisse cochée** la case « Voir les données de vos activités privées » :
   l'app en a besoin pour importer toutes tes séances.
4. Tu reviens sur l'app. Vérifie sur http://localhost:8000/api/strava/status que `connected` vaut
   `true`.

## 4. Lancer la première synchronisation

Depuis http://localhost:8000/docs, ouvre `POST /api/sync/strava` puis « Try it out » et
« Execute ». Suis l'avancement avec `GET /api/sync/logs`.

L'import de tout l'historique se fait par morceaux pour respecter les quotas Strava (environ 100
requêtes par quart d'heure et 1 000 par jour). Un statut `partial` est normal : la synchro suivante
reprend où la précédente s'est arrêtée.

## Ce que fait l'app avec ton accès

- Lecture seule : elle ne publie ni ne modifie rien sur Strava.
- Les tokens sont chiffrés avant d'être stockés, et jamais écrits dans les journaux.
- `DELETE /api/strava/connection` révoque l'accès côté Strava et efface les tokens.
