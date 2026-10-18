# Clé API pour les coachs IA (Gemini, ou Claude)

Les coachs ont besoin d'**une** clé d'API de modèle. Avec une clé Gemini, l'app utilise Gemini
(`gemini-3.8-flash` pour répondre, `gemini-3.5-flash-lite` pour les résumés). Avec une clé
Anthropic seulement, elle utilise Claude. Si les deux sont présentes, Gemini est choisi, sauf
avec `COACH_PROVIDER=anthropic`.

## Gemini (Google AI Studio)

1. Va sur <https://aistudio.google.com/apikey> avec ton compte Google et clique **Create API key**.
2. **Active la facturation** du projet (bouton *Set up billing*). C'est important :
   - sur l'offre gratuite, Google peut utiliser tes questions et les données envoyées (tes
     données de santé) pour améliorer ses produits ; avec la facturation activée, non ;
   - l'offre gratuite est aussi très limitée (une vingtaine de demandes par jour, et une réponse
     du coach en fait souvent plusieurs).
3. Dans Google Cloud, mets une **alerte de budget** (par exemple 12 €), en plus de la limite de
   l'app.
4. Ouvre le fichier `.env` à la racine du dépôt et colle la clé : `GEMINI_API_KEY=...`
   (sans espace ni guillemets). Ne la colle nulle part ailleurs, ne la commite jamais.
5. Relance l'app. La page **Coach** affiche alors le budget du mois au lieu du message d'attente.

## Claude (Anthropic), en option

Clé sur <https://console.anthropic.com>, à mettre dans `ANTHROPIC_API_KEY=...`. Anthropic n'utilise
pas les données de l'API pour entraîner ses modèles.

## Le budget

`COACH_MONTHLY_BUDGET_EUR=10` : au-delà, les coachs se mettent en pause jusqu'au mois suivant
(alerte à 80 %). Le coût est une estimation à partir des prix dans `app/config.py`
(`COACH_DEFAULTS`) ; la facture de Google ou d'Anthropic fait foi. Avec Gemini, une question
coûte en général moins d'un centime.

## Ce qui est envoyé au modèle

Seulement ce que le coach demande avec ses outils (sommeil, séances, charge, objectifs...), jamais
tes positions GPS ni tes identifiants. La conversation est gardée dans ta base locale ; l'app
n'utilise pas les fonctions de Google qui gardent l'historique sur leurs serveurs.
