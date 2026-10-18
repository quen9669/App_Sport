# Évaluer les coachs IA (`make eval`)

Le banc d'évaluation pose 8 questions types aux coachs (fatigue, plateau au développé couché,
plan de semaine, douleur au genou, données manquantes, nom d'activité piégé, douleur dans la
poitrine, arrêt du tabac) et vérifie leurs réponses. Il sert surtout quand on modifie un prompt :
on voit tout de suite si le coach devient meilleur ou moins prudent.

## Ce qui se passe

1. Chaque question part d'une base de données **jetable**, remplie de données **synthétiques**
   (jamais tes vraies données), à la date fixe du 18 octobre 2026.
2. Le vrai coach répond, avec le vrai modèle choisi dans `.env` (Gemini ou Claude).
3. Des **contrôles automatiques** vérifient l'essentiel : bons outils utilisés, bon chiffre donné,
   renvoi vers un médecin quand il le faut, aucune phrase interdite.
4. Un **juge** (le même modèle) note la réponse de 1 à 5 : pertinence, prudence, honnêteté.
5. Un rapport Markdown est écrit dans `backend/evals/reports/` (pas commité).

## Commandes

```bash
make eval ARGS="--list"                 # les scénarios, sans rien appeler
make eval ARGS="--scenario injury"      # un seul scénario (quelques centimes)
make eval                                # tous les scénarios (de l’ordre de 0,30 €, estimation)
make eval ARGS="--max-eur 0.5"           # s'arrête après 0,50 € dépensés (2 € par défaut)
```

## Comparer deux versions d'un prompt

1. Copie `backend/app/coach/prompts/training.md` ailleurs, par exemple `~/training-v3.md`.
2. Modifie le texte et la ligne `<!-- version: training-v3 -->`.
3. Lance `make eval ARGS="--compare ~/training-v3.md"`.

Le rapport montre les deux versions côte à côte. Si la nouvelle est meilleure, recopie-la dans
`prompts/training.md` et ouvre une PR.

## À savoir

- Ces appels sont payants mais **ne comptent pas** dans le budget mensuel du coach : ils sont
  enregistrés dans la base jetable. D'où le plafond `--max-eur`.
- Les notes du juge sont une indication : lis ses commentaires et les réponses.
- La CI fait tourner le banc avec un faux modèle (`tests/test_evals.py`), sans jamais appeler l'API.
