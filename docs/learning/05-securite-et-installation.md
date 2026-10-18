# Sécuriser l'app et l'installer (phase 6a)

Ce guide explique, sans jargon, ce que la phase 6a a ajouté et les quelques commandes à connaître.
Tant que l'app reste sur ton PC et que tu ne choisis pas de mot de passe, rien ne change pour toi.

## 1. Choisir un mot de passe

Dans le terminal Ubuntu, à la racine du projet :

```bash
make set-password
```

Tape ton mot de passe deux fois (au moins 10 caractères ; rien ne s'affiche, c'est normal), puis
relance l'app. L'app n'enregistre pas ton mot de passe : elle garde seulement son **empreinte**
(Argon2), une sorte de code calculé à partir de lui, impossible à inverser. À la connexion, l'app
recalcule l'empreinte de ce que tu tapes et compare.

- Tu restes connecté **30 jours** sur chaque appareil.
- Après **5 mauvais mots de passe**, il faut attendre **15 minutes** : personne ne peut essayer des
  milliers de mots de passe.
- Pour retirer l'écran de connexion (sur le PC seulement), vide la ligne `APP_PASSWORD_HASH=` du
  fichier `.env`, puis relance l'app. En production, l'app refuse de démarrer sans mot de passe.

## 2. Le mode « production »

```bash
make prod
```

Cette commande prépare l'interface, puis lance **un seul serveur** sur le port 8000, qui sert à la
fois les pages et les données. C'est ce mode qui sera mis en ligne en phase 6b. Il ajoute aussi
des protections pour le navigateur : aucune ressource ne peut venir d'un autre site (sauf le fond
de carte OpenStreetMap), et l'app ne peut pas être affichée à l'intérieur d'un autre site.

## 3. Les sauvegardes

Chaque nuit à 3 h 30, l'app copie la base de données dans `backend/data/backups/` et garde les 14
dernières copies. Ce dossier n'est jamais envoyé sur GitHub (données de santé).

```bash
make backup                              # une copie tout de suite
make restore                             # la liste des copies
make restore f=app_sport-20261018-033000.db   # remettre une copie (app arrêtée)
```

La base remplacée n'est jamais perdue : elle est gardée à côté, avec `.before-restore` à la fin.

## 4. Installer l'app et l'utiliser hors ligne

- Sur la page **Profil**, la carte « Cet appareil » affiche un bouton **Installer l'app** quand
  Chrome le permet. Sinon : menu de Chrome, puis « Installer l'application » ou « Ajouter à l'écran
  d'accueil ».
- **Hors ligne**, l'app s'ouvre quand même avec les dernières données vues, et une bannière dit de
  quand elles datent. Les modifications attendent le retour du réseau ; le coach a besoin d'Internet.
- Quand une nouvelle version est prête, une bannière propose **Recharger** : rien ne change par
  surprise pendant que tu t'en sers.
- **Se déconnecter** (page Profil) ferme la session et efface les données gardées sur l'appareil.

## 5. Ce que GitHub vérifie maintenant

À chaque PR, une étape « Security » cherche :

- des failles connues dans les bibliothèques utilisées (Python et npm) ;
- une clé ou un mot de passe enregistré par erreur dans l'historique.

Chaque semaine, **Dependabot** ouvre une PR pour mettre les bibliothèques à jour. Si les
vérifications sont vertes, tu peux la fusionner.
