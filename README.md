# Hypnos Bots

Ce dépôt contient des scripts d'automatisation (bots) pour les jeux de la plateforme Hypnos 2026.

## Installation

1. Assurez-vous d'avoir **Python 3.x** installé.
2. Installez les dépendances requises via `pip` :

```bash
pip install -r requirements.txt
```

## Configuration (.env)

Pour que le bot Wordle fonctionne, vous devez configurer vos identifiants de session dans un fichier `.env`. Ce fichier permet de ne pas exposer vos secrets dans le code.

1. Créez un fichier nommé `.env` à la racine du projet (au même niveau que les scripts `.py`).
2. Ouvrez ce fichier et collez-y les tokens suivants (récupérables dans les cookies de votre navigateur sur le site du jeu) :

```ini
AUTH_TOKEN=votre_auth_token_ici
CSRF_TOKEN=votre_csrf_token_ici
```

***Attention :** Ne committez jamais ce fichier `.env`. Il est déjà ignoré par le fichier `.gitignore`.*

## Scripts et Modules

Voici la liste des scripts principaux et des modules Python associés (externes) nécessaires à leur fonctionnement (inclus dans `requirements.txt`).

### 1. Bot Wordle (`auto_wordle.py`)

Ce script résout automatiquement les parties de Wordle en communiquant directement avec l'API.

- **Description** : Analyse les réponses du serveur pour filtrer une liste de candidats et trouver le mot secret. Il apprend et enrichit sa base de données locale (`wordle_db.json`) à chaque partie.
- **Dépendances principales** :
  - `requests` : Pour effectuer les appels API HTTP (GET/POST).
  - `python-dotenv` : Pour charger les variables sensibles (`AUTH_TOKEN`, `CSRF_TOKEN`) depuis le fichier `.env`.

### 2. Bot Casse-Brique (`casse_brique_bot.py`)

Ce script utilise la vision par ordinateur pour jouer au Casse-Brique en temps réel.

- **Description** : Capture l'écran, détecte la balle par reconnaissance d'image (Template Matching) et déplace la souris pour intercepter la balle.
- **Dépendances principales** :
  - `opencv-python` (`cv2`) : Pour le traitement d'image et la détection de la balle.
  - `mss` : Pour la capture d'écran haute performance (bien plus rapide que les méthodes natives).
  - `numpy` : Pour les calculs matriciels sur les images.
  - `pyautogui` : Pour les interactions système (initialisation).
