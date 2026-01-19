# Hypnos Bots

Ce dépôt contient des scripts d'automatisation (bots) pour les jeux de la plateforme Hypnos 2026.

## Installation

1. Assurez-vous d'avoir **Python 3.10** installé (recommandé pour la compatibilité avec `matchTemplate` et `mss` du bot Casse-Brique).
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

#### Initialisation et Utilisation

Au premier lancement, le script vous guidera pour configurer la vision du bot. Cette étape est cruciale mais très assistée :

1.  **Zone de Jeu** : Le bot va prendre une capture d'écran. Sélectionnez avec la souris la zone rectangulaire complète du jeu (murs inclus).
2.  **Balle** : Mettez le jeu en pause quand la balle est visible. Le bot prendra une nouvelle capture. Entourez **strictement** la balle (le carré doit être le plus serré possible autour d'elle).

Une fois configuré, un fichier `config.json` et une image `ball.png` sont créés. Le bot se lancera ensuite automatiquement avec ces paramètres lors des prochaines sessions.

**Contrôles en jeu :**
- `P` : Mettre le bot en Pause / Reprendre.
- `D` : Activer le mode Debug (affiche ce que le bot voit, *peut ralentir l'exécution*).
- `Q` : Quitter proprement.

### 3. Bots Trivia (Sporcle)

Ces scripts automatisent le jeu de trivia (type Sporcle) pour différents thèmes en envoyant rapidement les réponses correctes.

- **Fichiers** :
  - `trivia_bde.py` : Réponses pour le thème "Mandats" (BDE).
  - `trivia_listeux.py` : Réponses pour le thème "Listeux".
  - `trivia_clubs.py` : Réponses pour le thème "Clubs".

- **Fonctionnement** :
  - Utilise les tokens configurés dans `.env` pour l'authentification.
  - Lance automatiquement une nouvelle partie.
  - Envoie les réponses en utilisant le multithreading (`ThreadPoolExecutor`) pour une vitesse optimale.
  - Gère intelligemment les erreurs serveur (retry automatique sur erreur 500) et le rate-limiting pour assurer que tous les mots sont validés.
