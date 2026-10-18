# Les outils du projet, simplement

Chaque outil a un seul rôle. Tu n'as pas besoin de tous les maîtriser : `make` les lance pour toi.

## Côté Python (`backend/`)

| Outil | À quoi il sert | Fichier où il est réglé |
|---|---|---|
| **uv** | Installe Python et les bibliothèques. `uv run X` lance X dans l'environnement du projet. | `pyproject.toml`, `uv.lock` |
| **FastAPI** | Le framework web : transforme des fonctions Python en routes HTTP. | `app/main.py` |
| **Pydantic** | Décrit la forme des données et la vérifie (« ce champ est un nombre entre 30 et 250 »). | modèles dans le code |
| **uvicorn** | Le serveur qui fait tourner l'application FastAPI. | commande `make dev-backend` |
| **pytest** | Lance les tests : toute fonction `test_...` dans `tests/`. | `pyproject.toml` |
| **ruff** | Linter (repère les erreurs et le code douteux) et formateur (met en forme). | `pyproject.toml` |
| **mypy** | Vérifie les types : signale par exemple qu'on passe un texte là où un nombre est attendu. | `pyproject.toml` |

## Côté web (`frontend/`)

| Outil | À quoi il sert | Fichier |
|---|---|---|
| **Node.js / npm** | Node exécute le JavaScript hors navigateur ; npm installe les bibliothèques. | `package.json`, `package-lock.json` |
| **React** | Construit l'interface en composants (`App.tsx`). | `src/` |
| **TypeScript** | JavaScript avec des types, vérifiés par `tsc`. | `tsconfig*.json` |
| **Vite** | Serveur de développement ultra rapide et outil de build. | `vite.config.ts` |
| **vite-plugin-pwa** | Rend l'app installable et utilisable hors ligne. | `vite.config.ts` |
| **Vitest + Testing Library** | Tests unitaires des composants, comme un utilisateur les verrait. | `src/*.test.tsx` |
| **Playwright** | Pilote un vrai navigateur pour tester l'app de bout en bout. | `playwright.config.ts`, `e2e/` |
| **oxlint / Prettier** | Lint et mise en forme du code TypeScript. | `.oxlintrc.json`, `.prettierrc.json` |

## Les commandes à retenir

```bash
make dev     # lancer l'app
make test    # lancer les tests
make format  # remettre le code en forme automatiquement
make check   # tout vérifier avant de proposer une modification
```

## Lire un test

```python
def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")          # 1. on fait l'action

    assert response.status_code == 200            # 2. on vérifie le résultat
    assert response.json() == {"status": "ok", "version": "0.1.0"}
```

Un test suit presque toujours ce schéma : préparer, agir, vérifier. Si une ligne `assert` est
fausse, pytest affiche le test en rouge avec la valeur obtenue et la valeur attendue.
