import os
import logging
import sys
import json
import requests
import time
import random

# --- Configuration ---
LOGIN_URL = 'https://play.hypnos2026.fr/api/auth/login'
LOGOUT_URL = 'https://play.hypnos2026.fr/api/auth/logout'
BASE_URL = 'https://play.hypnos2026.fr'
SUBMIT_REPLAY_URL = f'{BASE_URL}/api/arg/snake/submit-replay'

EMAIL = os.environ.get("EMAIL")
PASSWORD = os.environ.get("PASSWORD")

if not EMAIL or not PASSWORD:
    raise ValueError("EMAIL and PASSWORD environment variables must be set.")

TILE_COUNT = 20
POINTS_PER_FOOD = 20
INITIAL_SNAKE_LENGTH = 3

# --- Logger ---
def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

logger = setup_logger("snake_solver")

# --- Utils ---
def generate_challenge_id(slug):
    crc = 0xFFFFFFFF
    for char in slug:
        crc ^= ord(char)
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
    return ((~crc) & 0xFFFFFFFF) & 0x7FFFFFFF

# --- Session Management ---
def get_fresh_session():
    session = requests.Session()
    session.headers.update({
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
        'accept': 'application/json',
        'origin': BASE_URL,
        'referer': f'{BASE_URL}/login'
    })

    try:
        logger.info("--- Récupération CSRF via /api/csrf-token ...")
        csrf_url = f"{BASE_URL}/api/csrf-token"
        r_init = session.get(csrf_url, timeout=10)
        
        csrf_token = r_init.json().get('csrf_token') or session.cookies.get('csrf_token')
        if not csrf_token:
            session.get(BASE_URL, timeout=10)
            csrf_token = session.cookies.get('csrf_token')

        if csrf_token:
            session.headers.update({'x-csrf-token': csrf_token})

        logger.info(f"--- Tentative de connexion pour {EMAIL}...")
        r_login = session.post(LOGIN_URL, json={"login": EMAIL, "password": PASSWORD}, timeout=10)
        
        if r_login.status_code == 200:
            logger.info("--- Login réussi !")
            session.headers.update({'x-csrf-token': session.cookies.get('csrf_token', csrf_token)})
            return session
        else:
            logger.error(f"!!! ECHEC LOGIN: {r_login.text}")
            return None
    except Exception as e:
        logger.error(f"!!! Erreur login: {e}")
        return None

def generate_replay(target_score=4000):
    """
    Génère un replay valide en simulant une partie de Snake.
    Synchronisé avec backend/app/routers/snake.py
    """
    # Position initiale imposée par le backend (center=10)
    snake = [(10, 10), (9, 10), (8, 10)]
    direction = "right"
    current_tick = 0
    score = 0
    
    inputs = []
    food_spawns = []
    
    def get_random_food(snake_body):
        while True:
            f = (random.randint(0, TILE_COUNT-1), random.randint(0, TILE_COUNT-1))
            if f not in snake_body:
                return f

    food = get_random_food(snake)
    initial_food = {"x": food[0], "y": food[1]}
    
    # La boucle de simulation du serveur est: for tick in range(replay.ticks_played)
    # Donc tick va de 0 à ticks_played - 1
    
    while score < target_score:
        # 1. Gestion des Inputs (au début du tick)
        head = snake[0]
        desired_dir = direction
        
        # Logique simple de pathfinding
        if head[0] < food[0] and direction != "left": desired_dir = "right"
        elif head[0] > food[0] and direction != "right": desired_dir = "left"
        elif head[1] < food[1] and direction != "up": desired_dir = "down"
        elif head[1] > food[1] and direction != "down": desired_dir = "up"
            
        if desired_dir != direction:
            direction = desired_dir
            inputs.append({"tick": current_tick, "direction": direction})
        
        # 2. Mouvement (calcul de la nouvelle tête)
        dx, dy = (0, 0)
        if direction == "up": dy = -1
        elif direction == "down": dy = 1
        elif direction == "left": dx = -1
        elif direction == "right": dx = 1
        
        new_head = (head[0] + dx, head[1] + dy)
        
        # 3. Collision (Mur ou Soi-même)
        if not (0 <= new_head[0] < TILE_COUNT and 0 <= new_head[1] < TILE_COUNT) or new_head in snake:
            # Tentative de sauvetage basique
            possible_dirs = ["up", "down", "left", "right"]
            # random.shuffle(possible_dirs) # On évite le random pour le debug si possible, mais bon
            found = False
            for d in possible_dirs:
                if (d == "up" and direction == "down") or (d == "down" and direction == "up") or \
                   (d == "left" and direction == "right") or (d == "right" and direction == "left"):
                    continue
                ndx, ndy = 0, 0
                if d == "up": ndy = -1
                elif d == "down": ndy = 1
                elif d == "left": ndx = -1
                elif d == "right": ndx = 1
                
                temp_head = (head[0] + ndx, head[1] + ndy)
                if 0 <= temp_head[0] < TILE_COUNT and 0 <= temp_head[1] < TILE_COUNT and temp_head not in snake:
                    direction = d
                    # On enregistre le input à ce tick
                    inputs.append({"tick": current_tick, "direction": direction})
                    new_head = temp_head
                    found = True
                    break
            if not found:
                logger.warning(f"Mort simulée au tick {current_tick} (Score: {score})")
                break

        # 4. Mise à jour du serpent
        snake.insert(0, new_head)
        
        # 5. Manger la pomme
        if new_head == food:
            score += POINTS_PER_FOOD
            
            # Le serveur vérifie: if tick in food_spawn_by_tick OR if tick + 1 in food_spawn_by_tick
            # On va fournir le spawn pour le PROCHAIN tick (ou le tick actuel si on est précis)
            # Pour être safe vis-à-vis de la logique du serveur, donnons lui à 'tick + 1'
            # car le serveur consomme le spawn APRES avoir détecté la collision.
            
            if score < target_score:
                food = get_random_food(snake)
                # Note: Le serveur consomme food_spawn_by_tick[tick] ou [tick+1]
                # On va le mettre à tick + 1 pour être sûr qu'il soit disponible pour le tour d'après
                # ou considéré comme le spawn "conséquent" à ce repas.
                food_spawns.append({"tick": current_tick + 1, "x": food[0], "y": food[1]})
        else:
            snake.pop()
        
        current_tick += 1
        if current_tick > 20000: # Sécurité anti-boucle infinie
            break

    return {
        "initial_snake": [{"x": 10, "y": 10}, {"x": 9, "y": 10}, {"x": 8, "y": 10}],
        "initial_food": initial_food,
        "inputs": inputs,
        "food_spawns": food_spawns,
        "final_score": score,
        "final_length": len(snake),
        "ticks_played": current_tick,
        "game_duration_ms": current_tick * 100
    }

def submit_score_simple(session, score=4000):
    challenge_id = generate_challenge_id("snake")
    url = f"{BASE_URL}/api/arg/challenges/{challenge_id}/submit"
    payload = {
        "score": score,
        "completion_time": 30,
        "data": {
            "snake_size": 50,
            "won": True,
            "time_remaining": 90
        }
    }
    logger.info(f"Envoi score simple: {score}")
    r = session.post(url, json=payload, timeout=10)
    logger.info(f"Status: {r.status_code}")
    if r.ok: logger.info(f"Réponse: {r.json()}")
    else: logger.warning(f"Erreur: {r.text}")

def submit_replay(session, target_score=4000):
    logger.info("Génération du replay...")
    replay = generate_replay(target_score=target_score)
    logger.info(f"Envoi replay: score={replay['final_score']}")
    r = session.post(SUBMIT_REPLAY_URL, json=replay, timeout=15)
    logger.info(f"Status: {r.status_code}")
    if r.ok: logger.info(f"Réponse: {r.json()}")
    else: logger.warning(f"Erreur: {r.text}")

def main():
    session = get_fresh_session()
    if not session: return

    # Le mode par défaut est 'replay' pour plus de sécurité (anti-cheat)
    # Mais on peut facilement basculer sur 'simple' pour tester.
    mode = os.environ.get("SNAKE_MODE", "replay")
    
    if mode == "simple":
        submit_score_simple(session)
    else:
        submit_replay(session, target_score=4000)

if __name__ == "__main__":
    main()
