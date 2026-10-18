# Ouvrir l'app sur ton téléphone avec Tailscale (phase 6b)

L'app tourne sur ton PC. **Tailscale** crée un petit réseau privé entre tes propres appareils (PC
et téléphone) : ton téléphone peut ouvrir l'app, en HTTPS, où que tu sois, mais personne d'autre
sur Internet ne la voit. Tes données de santé ne quittent jamais ton PC.

Ce qu'il faut savoir :

- l'app n'est joignable que quand le PC est allumé (et la session Windows ouverte) ;
- les synchros Garmin et Strava tournent aussi seulement à ce moment-là ;
- hors connexion, le téléphone garde les dernières données vues (phase 6a).

## 1. Installer Tailscale sur le PC (Windows)

1. Télécharge Tailscale pour Windows sur <https://tailscale.com/download> et installe-le.
2. Clique sur l'icône Tailscale près de l'horloge, puis **Log in**. Choisis un compte (Google,
   Microsoft ou GitHub). Ce compte sert seulement à relier tes appareils entre eux.
3. Sur <https://login.tailscale.com/admin/dns>, vérifie que **MagicDNS** est activé, puis active
   **HTTPS Certificates**. C'est ce qui donne à ton PC une adresse du type
   `https://francky.tailXXXX.ts.net` avec un vrai certificat.

## 2. Choisir le mot de passe de l'app

Indispensable avant d'ouvrir l'app au téléphone. Dans le terminal Ubuntu, à la racine du projet :

```bash
make set-password
```

Voir le guide [05](05-securite-et-installation.md) : seule l'empreinte du mot de passe est gardée.

## 3. Mettre la bonne adresse dans `.env`

Ton adresse Tailscale s'affiche avec cette commande, dans **PowerShell** (Windows) :

```powershell
tailscale status --self --json | Select-String DNSName
```

Le nom affiché finit par un point (`francky.tailXXXX.ts.net.`) : retire-le. Dans le fichier `.env`
du projet, remplace ensuite :

```ini
FRONTEND_URL=https://francky.tailXXXX.ts.net
STRAVA_REDIRECT_URI=https://francky.tailXXXX.ts.net/api/strava/callback
```

`CORS_ORIGINS` peut rester tel quel : en production, l'interface et les données viennent du même
serveur, le navigateur n'en a pas besoin.

Puis, sur <https://www.strava.com/settings/api>, mets **Authorization Callback Domain** à
`francky.tailXXXX.ts.net` (sans `https://`, sans chemin). Sans ça, Strava refuse le retour vers
l'app quand tu reconnectes ton compte.

## 4. Lancer l'app au démarrage de Windows

Arrête d'abord `make dev` s'il tourne (Ctrl+C dans sa fenêtre), puis :

```bash
make autostart
```

Cette commande met un raccourci « App Sport » dans le dossier **Démarrage** de Windows (tout ce
qu'il contient s'ouvre à chaque ouverture de session) et lance l'app tout de suite. L'app démarre
en mode production (`make prod`), sans fenêtre : plus besoin de garder une fenêtre Ubuntu ouverte.

Le démarrage prend une minute (l'interface est reconstruite à chaque fois). Le journal est dans
`backend/data/prod.log` :

```bash
tail -n 30 backend/data/prod.log
```

Pour arrêter le démarrage automatique : `make autostart-off`.

## 5. Publier l'app sur ton réseau Tailscale, en HTTPS

Dans **PowerShell** (Windows) :

```powershell
tailscale serve --bg 8000
```

Tailscale reçoit les connexions HTTPS de tes appareils et les passe à l'app sur le port 8000 du PC.
`--bg` garde ce réglage, même après un redémarrage. `tailscale serve status` montre ce qui est
publié ; `tailscale serve reset` l'arrête.

Ouvre `https://francky.tailXXXX.ts.net` dans Chrome sur le PC : l'écran de connexion doit
s'afficher, avec le cadenas.

> N'utilise **pas** `tailscale funnel` : il rendrait l'app visible de tout Internet.

## 6. Installer l'app sur ton Android

1. Installe **Tailscale** depuis le Play Store, ouvre-le et connecte-toi avec **le même compte**
   que sur le PC. Laisse-le activé (il consomme très peu de batterie).
2. Dans Chrome, ouvre `https://francky.tailXXXX.ts.net` et connecte-toi avec ton mot de passe.
3. Page **Profil**, carte « Cet appareil » : **Installer l'app**. Sinon : menu de Chrome (⋮), puis
   « Ajouter à l'écran d'accueil ».

L'icône QF apparaît sur ton écran d'accueil et l'app s'ouvre en plein écran.

## 7. Mettre à jour l'app plus tard

Dans le terminal Ubuntu, à la racine du projet :

```bash
make backup                          # une copie de la base, par prudence
git pull                             # la nouvelle version
make install                         # les nouvelles bibliothèques, s'il y en a
make prod-restart                    # arrête l'app et la relance (migrations et interface comprises)
```

Sur le téléphone, la bannière « Nouvelle version » propose ensuite de recharger.

## En cas de problème

| Ce que tu vois | Ce qu'il faut regarder |
|---|---|
| Le téléphone n'ouvre rien | Tailscale est-il activé sur le téléphone ? Le PC est-il allumé ? |
| « Bad gateway » ou page d'erreur Tailscale | L'app ne tourne pas : lis `backend/data/prod.log` |
| L'app refuse de démarrer | `prod.log` dit pourquoi (souvent : pas de mot de passe, `make set-password`) |
| Strava refuse la connexion | `STRAVA_REDIRECT_URI` et l'« Authorization Callback Domain » de Strava |
