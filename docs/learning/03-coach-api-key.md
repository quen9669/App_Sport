# Clé pour les coachs IA (OmniRoute)

Depuis l'alignement sur le référentiel (écarts SPT-01 et SPT-02), les coachs ne parlent **qu'à
OmniRoute**, la passerelle IA commune du serveur (`http://omniroute:20128/v1`, réseau Docker
`llm-net`). Il n'y a plus de clé Gemini ni Anthropic dans l'app.

## En production (VPS)

- La clé de l'app est déjà dans le coffre OpenBao : `apps/app-sport/OMNIROUTE_API_KEY`.
- `docker-compose.yml` la déclare (`OMNIROUTE_API_KEY: ${OMNIROUTE_API_KEY}`) ; la synchro du
  coffre la pousse dans Coolify et redémarre l'app en 15 minutes. Rien à saisir à la main.
- Le conteneur `sport-app` rejoint le réseau `llm-net` pour joindre OmniRoute.

## Le budget

Il se règle **uniquement dans OmniRoute** (quota de la clé `app-sport`), jamais dans l'app.
L'app affiche seulement une estimation de ce qui a été dépensé ce mois-ci. Si OmniRoute refuse
(quota atteint, clé bloquée, service injoignable), le coach affiche « ◆ Coach dégradé » avec la
raison, et tout le reste de l'app fonctionne.

## Les modèles

Par défaut `claude-sonnet-5-5` pour répondre et `claude-haiku-5-5` pour les résumés, sous les noms
qu'OmniRoute leur donne. `COACH_MODEL` et `COACH_LIGHT_MODEL` permettent d'en changer. La clé est
payante, donc les données de santé ne servent jamais à entraîner un modèle (règle R-08).

## En développement

Sans `OMNIROUTE_API_KEY`, les coachs sont désactivés et l'écran l'explique. Les tests n'appellent
jamais OmniRoute (faux modèle et `respx`).
