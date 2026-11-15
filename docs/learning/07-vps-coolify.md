# L'app sur ton VPS (Coolify), sans toucher au reste

L'app quitte ton PC pour ton VPS. Elle y vit dans **son propre projet Coolify, `app-sport`**,
avec son propre réseau Docker. Les projets `jobradar` et `supervision`, le pare-feu,
`docker-private-ports` et le Tailscale du VPS ne sont pas modifiés.

```
Tes appareils ──Tailscale (HTTPS)──► sport-tailscale ──► sport-app ──► volume app-sport-data
                                                                            │ (lecture seule)
                                                          sport-backup ◄────┘ ──► Google Drive (chiffré)
```

| Conteneur | Rôle | Mémoire max |
|---|---|---|
| `sport-app` | l'API et l'interface, comme `make prod` | 512 Mo |
| `sport-tailscale` | la porte d'entrée : un appareil Tailscale à part, `https://app-sport.<tailnet>.ts.net` | 128 Mo |
| `sport-backup` | envoie les copies de nuit, chiffrées, dans le dossier Drive « App Sport » | 128 Mo |

Les fichiers : `Dockerfile` (l'app), `docker-compose.yml` (les 3 conteneurs),
`deploy/tailscale/` et `deploy/backup/`.

## Pourquoi aucun port n'est ouvert

Docker contourne le pare-feu `ufw` : un port publié serait joignable depuis Internet tant
qu'il n'est pas ajouté à `docker-private-ports`, un service partagé par tous tes projets.
Ici, **aucun port n'est publié**. Le conteneur `sport-tailscale` rejoint ton tailnet comme
un appareil de plus et sert l'app en HTTPS. Seuls tes appareils la voient.

Le HTTPS est indispensable : en production, le cookie de connexion n'est envoyé qu'en HTTPS,
et la PWA ne s'installe qu'en HTTPS.

## Les données : SQLite dans un volume

Toutes les données tiennent dans un fichier, `app_sport.db`, dans le volume `app-sport-data`
(avec les copies de nuit et les jetons Garmin). Pour migrer depuis le PC, on copie ce fichier.
Le volume est géré par Coolify (pas de « bind mount », qui ne marche pas dans Coolify 4.7.5).

Sauvegardes, deux niveaux :

1. l'app fait une copie chaque nuit à 03:30 dans le volume (14 gardées) ;
2. `sport-backup` envoie toutes les 6 heures les nouvelles copies dans Google Drive,
   **chiffrées** (noms de fichiers compris), et efface celles de plus de 30 jours.

## Ce que toi seul peux faire (une fois)

Ce sont des comptes à toi : personne d'autre ne peut créer ces accès.

1. **Clé Tailscale** : <https://login.tailscale.com/admin/settings/keys> › *Generate auth key*
   (non réutilisable, sans expiration éphémère). Après le premier démarrage, dans *Machines*,
   ouvre `app-sport` › *Disable key expiry*, sinon l'app disparaît du tailnet au bout de 6 mois.
2. **Accès de Coolify au dépôt** : si le dépôt est privé, Coolify affiche une clé publique ;
   ajoute-la sur GitHub › *Settings* › *Deploy keys*, **sans** cocher *Allow write access*.
3. **Google Drive pour rclone** : dans Ubuntu, `rclone authorize "drive" "eyJzY29wZSI6ImRyaXZlLmZpbGUifQ=="`
   ouvre ton navigateur ; tu acceptes, et le jeton affiché va dans la variable `RCLONE_GDRIVE_TOKEN`.

## Les variables à saisir dans Coolify

Jamais dans le dépôt. Copie aussi dans `C:\Users\franc\.jobradar-secrets\app-sport.env`.

| Variable | Valeur |
|---|---|
| `TOKEN_ENCRYPTION_KEY` | **la même que dans le `.env` du PC** (les jetons Strava de la base sont chiffrés avec) |
| `APP_PASSWORD_HASH` | la même que sur le PC (même mot de passe) |
| `FRONTEND_URL` | `https://app-sport.<tailnet>.ts.net` |
| `STRAVA_REDIRECT_URI` | `https://app-sport.<tailnet>.ts.net/api/strava/callback` |
| `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `GARMIN_EMAIL`, `GARMIN_PASSWORD`, `GEMINI_API_KEY` | comme sur le PC |
| `TS_AUTHKEY` | la clé Tailscale (étape 1) |
| `RCLONE_GDRIVE_TOKEN` | le jeton de l'étape 3, ou celui de la sauvegarde JobRadar (ton choix) |
| `RCLONE_GDRIVE_CLIENT_ID`, `RCLONE_GDRIVE_CLIENT_SECRET`, `RCLONE_GDRIVE_SCOPE` | seulement si tu reprends l'accès Drive de JobRadar : les mêmes valeurs que sa configuration rclone (le jeton est lié à ce client Google) |
| `RCLONE_CRYPT_PASSWORD`, `RCLONE_CRYPT_SALT` | deux mots de passe aléatoires passés par `rclone obscure`. **Garde-les hors du VPS** : sans eux, les copies Drive sont illisibles |

## Migrer les données du PC

1. Sur le PC : `make backup`, puis arrêter l'app (Ctrl+C).
2. Copier la copie et le dossier `~/.app_sport/garmin` (jetons Garmin) dans le volume :
   `docker cp` vers le conteneur `sport-app`, à l'emplacement `/data/app_sport.db` et `/data/garmin/`.
3. Redémarrer `sport-app` et comparer le nombre de lignes de chaque table avec le PC.
4. Strava : sur <https://www.strava.com/settings/api>, mettre `app-sport.<tailnet>.ts.net` comme
   *Authorization Callback Domain*.
5. Sur Android : ouvrir la nouvelle adresse, se connecter, réinstaller la PWA.

Garde la copie du PC une semaine. Si Garmin refuse les connexions depuis le VPS (ça arrive
avec les serveurs), on le voit pendant cette semaine.

## Restaurer une sauvegarde

- Depuis le volume : dans le terminal du conteneur `sport-app` (Coolify), `python -m scripts.backup`
  liste les copies ; arrêter l'app avant `python -m scripts.backup --restore <fichier>`.
- Depuis Drive (VPS perdu) : avec les deux mots de passe rclone, `rclone copy` depuis le
  dossier chiffré vers le PC, puis `make restore f=...`.

## Mettre à jour l'app

Une fusion sur `main`, puis *Redeploy* dans Coolify. Les migrations de la base
s'appliquent toutes seules au démarrage du conteneur.
