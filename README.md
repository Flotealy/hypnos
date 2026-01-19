# Hypnos Bots

Ce dépôt contient des scripts d'automatisation (bots) pour les jeux de la plateforme Hypnos 2026.

## Structure du projet

- Le code source est dans `src/hypnos/`.
- Chaque jeu est un sous-package :
  - `breakout` : Bot Casse-Brique
  - `wordle` : Bot Wordle
  - `snake` : Bot Snake
  - `trivia` : Bots Trivia (BDE, Clubs, Listeux)
- Les points d'entrée (entry points) sont configurés dans `pyproject.toml`.

## Installation et développement

1. Installez [uv](https://github.com/astral-sh/uv) (gestionnaire de paquets rapide et moderne pour Python).
2. Installez les dépendances et activez le mode édition pour le développement :

```bash
uv pip install -e .
```

Cela vous permet de modifier le code source et de voir les changements immédiatement.

## Configuration (.env)

Placez un fichier `.env` à la racine du projet avec vos tokens d'authentification.
Eg:
```bash
AUTH_TOKEN=your_auth_token
CSRF_TOKEN=your_csrf_token
```

## Utilisation

Exécutez les bots via les scripts d'entrée, par exemple :


```bash
python -m hypnos.wordle.wordle solve   # Résolution (score maximal)
python -m hypnos.wordle.wordle train   # Entraînement de la base de données
```

Ou pour les autres jeux (structure unifiée) :

```bash
python -m hypnos.breakout.breakout
python -m hypnos.snake.snake
python -m hypnos.trivia.bde
python -m hypnos.trivia.clubs
python -m hypnos.trivia.listeux
```

## Données

Les fichiers de données (ex : `wordle_db.json`, `config.json`) doivent être placés dans le dossier `data/` à la racine ou gérés par chaque module selon la documentation interne.

## Bonnes pratiques

- Utilisez des imports absolus partout où c'est possible (ex : `from hypnos.wordle import solve`).
- Modifiez le projet en mode édition (`uv pip install -e .`) pour un développement efficace.
