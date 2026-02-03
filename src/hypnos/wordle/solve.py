import requests
import json
import time
import random
import os
import unicodedata
import sys
import logging
from typing import List, Dict, Set, Any, Optional

# --- Configuration ---
LOGIN_URL = 'https://play.hypnos2026.fr/api/auth/login'
LOGOUT_URL = 'https://play.hypnos2026.fr/api/auth/logout'
BASE_URL = 'https://play.hypnos2026.fr'
API_URL = "https://play.hypnos2026.fr/api/arg/wordle"

from pathlib import Path

# --- Configuration ---
EMAIL = os.environ.get("EMAIL")
PASSWORD = os.environ.get("PASSWORD")

if not EMAIL or not PASSWORD:
    raise ValueError("EMAIL and PASSWORD environment variables must be set.")

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
DICT_FILE = DATA_DIR / "mots.txt"
DATA_FILE = DATA_DIR / "wordle_db.json"

# --- Logger ---
def setup_logger(name: str) -> logging.Logger:
    """Sets up a simple logger that writes to stdout."""
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

logger = setup_logger("wordle_solver")

# --- Session Management ---
session = None

def get_fresh_session():
    """
    Crée une nouvelle session, récupère le CSRF initial, et se connecte.
    Retourne la session authentifiée.
    """
    s = requests.Session()
    s.headers.update({
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
        'accept': 'application/json',
        'origin': 'https://play.hypnos2026.fr',
        'referer': 'https://play.hypnos2026.fr/login',
        'priority': 'u=1, i'
    })

    try:
        # Etape 1 : Récupérer les cookies initiaux (CSRF)
        logger.info("--- Récupération CSRF via /api/csrf-token ...")
        csrf_url = "https://play.hypnos2026.fr/api/csrf-token"
        r_init = s.get(csrf_url, timeout=10)
        
        csrf_token = None
        try:
            data = r_init.json()
            if 'csrf_token' in data:
                csrf_token = data['csrf_token']
        except:
            pass
            
        if not csrf_token and 'csrf_token' in s.cookies:
            csrf_token = s.cookies['csrf_token']
            
        if not csrf_token:
             logger.info("--- Fallback: Récupération CSRF via l'accueil...")
             s.get(BASE_URL, timeout=10)
             if 'csrf_token' in s.cookies:
                csrf_token = s.cookies['csrf_token']

        if csrf_token:
            s.headers.update({'x-csrf-token': csrf_token})
        else:
            logger.warning("!!! ATTENTION: Impossible de trouver un token CSRF")

        # Etape 2 : Login
        logger.info(f"--- Tentative de connexion pour {EMAIL}...")
        payload = {"login": EMAIL, "password": PASSWORD}
        r_login = s.post(LOGIN_URL, json=payload, timeout=10)
        
        if r_login.status_code == 200:
            logger.info("--- Login réussi !")
            if 'csrf_token' in s.cookies:
                s.headers.update({'x-csrf-token': s.cookies['csrf_token']})
            return s
        else:
            logger.error(f"!!! ECHEC LOGIN (Code: {r_login.status_code})")
            logger.error(f"    Réponse: {r_login.text}")
            return None

    except Exception as e:
        logger.error(f"!!! Erreur lors du login : {e}")
        return None

def robust_request(method: str, url: str, **kwargs) -> Optional[requests.Response]:
    global session
    if not session:
        session = get_fresh_session()
        if not session: return None

    """Sends a request with simple retry logic."""
    for attempt in range(3):
        try:
            response = session.request(method, url, timeout=10, **kwargs)
            
            # Re-auth on 401
            if response.status_code == 401:
                 logger.warning("Session expired, logging in again...")
                 session = get_fresh_session()
                 if session:
                     response = session.request(method, url, timeout=10, **kwargs)
                 else:
                     return None

            if response.status_code == 429:
                logger.warning("Rate limit hit (429). Waiting 60s...")
                time.sleep(60)
                continue
            if response.status_code >= 500:
                logger.warning(f"Server error {response.status_code}. Retrying ({attempt+1}/3)...")
                time.sleep(1)
                continue
            return response
        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
            time.sleep(1)
    return None

def remove_accents(input_str: str) -> str:
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).upper()

def load_db() -> Dict[str, List[str]]:
    if DATA_FILE.exists():
        try:
            with DATA_FILE.open('r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load DB from {DATA_FILE}: {e}")
    return {"solutions": [], "invalid_words": []}

def load_dictionary(length: int) -> List[str]:
    words = set()
    if not DICT_FILE.exists():
        logger.error(f"Dictionary file {DICT_FILE} not found.")
        return []

    try:
        with DICT_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                w = line.strip()
                if w:
                    w_clean = remove_accents(w)
                    if len(w_clean) == length:
                        words.add(w_clean)
    except (FileNotFoundError, UnicodeDecodeError) as e:
        logger.warning(f"Error reading dictionary utf-8: {e}. Trying latin-1.")
        try:
            with open(target_path, "r", encoding="latin-1") as f:
                for line in f:
                    w = line.strip()
                    if w:
                        w_clean = remove_accents(w)
                        if len(w_clean) == length:
                            words.add(w_clean)
        except Exception as e2:
             logger.error(f"Failed to load dictionary: {e2}")
    return list(words)

def filter_words(candidates: List[str], guess: str, result: List[str]) -> List[str]:
    new_candidates = []
    for word in candidates:
        possible = True
        for i, (letter, status) in enumerate(zip(guess, result)):
            if status == 'correct':
                if word[i] != letter:
                    possible = False
                    break
            elif status == 'absent':
                if letter in word:
                    is_elsewhere = False
                    for j, (l2, s2) in enumerate(zip(guess, result)):
                        if l2 == letter and (s2 == 'correct' or s2 == 'present'):
                            is_elsewhere = True
                            break
                    if not is_elsewhere:
                        if letter in word:
                            possible = False
                            break
                    else:
                        if word[i] == letter:
                            possible = False
                            break
            elif status == 'present':
                if letter not in word:
                    possible = False
                    break
                if word[i] == letter:
                    possible = False
                    break
        if possible:
            new_candidates.append(word)
    return new_candidates

def get_active_game() -> Optional[Dict[str, Any]]:
    try:
        url = f"{API_URL}/active-game"
        response = robust_request('GET', url)
        if response and response.status_code == 200:
            return response.json()
        logger.error(f"Error getting active game")
        return None
    except Exception as e:
        logger.exception(f"Exception getting active game: {e}")
        return None

def start_new_game() -> Optional[Dict[str, Any]]:
    try:
        url = f"{API_URL}/new-game"
        response = robust_request('POST', url)
        if response and response.status_code == 200:
            return response.json()
        logger.error(f"Error creating new game")
        return None
    except Exception as e:
        logger.exception(f"Exception creating new game: {e}")
        return None

def submit_guess(game_id: str, word: str) -> Optional[Dict[str, Any]]:
    url = f"{API_URL}/{game_id}/guess"
    json_data = {'guess': word}
    response = robust_request('POST', url, json=json_data)
    
    if not response:
        return None

    if response.status_code == 400:
        try:
            err = response.json()
            if err.get('detail') in ["Not a valid word", "Guess must be X letters"]:
                return {"status": "invalid_word"}
        except:
            pass
            
    if response.status_code == 200:
        return response.json()
    
    logger.error(f"Error guessing: {response.status_code} - {response.text}")
    return None

def run_single_game(db):
    game_data = get_active_game()
    if game_data and not game_data.get('has_active_game'):
        print("No active game found. Creating a new one...")
        game_data = start_new_game()
    if not game_data:
        print("Could not retrieve or create game.")
        return False, 0
    game_id = game_data.get('game_id')
    if not game_id:
        print("No game_id found in game data.")
        return False, 0
    word_length = game_data.get('word_length') or 5
    attempts = game_data.get('attempts') or 0
    print(f"\n--- Game: {game_id} (Length: {word_length}) ---")
    all_words = load_dictionary(word_length)
    if not all_words:
        print(f"No dictionary words found for length {word_length} from {DICT_FILE}!")
        return False, 0
    candidates = [w for w in all_words if w not in db["invalid_words"]]
    solutions_candidates = [w for w in db["solutions"] if len(w) == word_length and w not in db["invalid_words"]]
    sol_set = set(solutions_candidates)
    dictionary_candidates = [w for w in all_words if w not in db["invalid_words"] and w not in sol_set]
    random.shuffle(dictionary_candidates)
    candidates = solutions_candidates + dictionary_candidates
    print(f"Prioritizing {len(solutions_candidates)} known solution(s).")
    board = game_data.get('board', [])
    if board:
        print(f"Resuming with {len(board)} existing guesses...")
        for turn in board:
            guess_word = "".join([x['letter'] for x in turn])
            result_list = [x['status'] for x in turn]
            candidates = filter_words(candidates, guess_word, result_list)
    while attempts < 6:
        if not candidates:
            print("No more strict candidates! Relaxing constraints to find ANY valid word...")
            fallback_words = load_dictionary(word_length)
            fallback_words = [w for w in fallback_words if w not in db["invalid_words"]]
            if not fallback_words:
                print("Critical: All dictionary words marked invalid!")
                break
            guess_word = random.choice(fallback_words)
            print(f"Fallback guess: {guess_word}")
        else:
            guess_word = candidates[0]
        print(f"Attempt {attempts+1}/6: Guessing {guess_word} (Candidates: {len(candidates)})")
        res = submit_guess(game_id, guess_word)
        if not res:
            break
        if res.get('status') == "invalid_word":
            print(f"Invalid word: {guess_word}")
            continue
        attempts = res.get('attempts', attempts + 1)
        if res.get('game_over'):
            is_won = res.get('won')
            correct_word = res.get('word')
            if is_won:
                print(f"!!! VICTORY !!! Answer: {correct_word}")
            else:
                print(f"GAME OVER (LOST). Answer revealed: {correct_word}")
            return True, res.get("score", 0)
        if 'result' in res:
            new_candidates = filter_words(candidates, guess_word, res['result'])
            if not new_candidates:
                print("Warning: Filtering eliminated all candidates. Ignoring last filter result.")
            else:
                candidates = new_candidates
        time.sleep(0.5)
    return True, 0

def main():
    db = load_db()
    TARGET_SCORE = 10000
    
    while True:
        success, current_score = run_single_game(db)
        if not success:
            print("Error or interruption, retrying in 5s...")
            time.sleep(5)
        else:
            print(f"Game finished. Current Score: {current_score}")
            if current_score >= TARGET_SCORE:
                print(f"Target score of {TARGET_SCORE} reached! Stopping.")
                break
                
            if os.environ.get("SOLVE_ONCE") == "1":
                break
            print("Starting new one in 2s...")
            time.sleep(2)

if __name__ == "__main__":
    main()
