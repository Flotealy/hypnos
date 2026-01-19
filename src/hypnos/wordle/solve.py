"""
Solving logic for auto-wordle: maximize score using current DB.
"""

import requests
import json
import time
import random
import os
import importlib.resources
import unicodedata
from typing import List, Dict, Set, Any, Optional
from hypnos.lib.session import get_cookies, get_headers

from hypnos.lib import setup_logger

logger = setup_logger("wordle_solver")

from importlib import resources
DATA_PATH = resources.files("hypnos.wordle.data")
DATA_FILE = DATA_PATH / "wordle_db.json"
DICT_FILE = "mots.txt"
BASE_URL = "https://play.hypnos2026.fr/api/arg/wordle"

COOKIES = get_cookies()
HEADERS = get_headers('https://play.hypnos2026.fr/game/wordle/', COOKIES['csrf_token'])

def remove_accents(input_str: str) -> str:
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).upper()

def robust_request(method: str, url: str, **kwargs) -> Optional[requests.Response]:
    """Sends a request with simple retry logic."""
    for attempt in range(3):
        try:
            response = requests.request(method, url, timeout=10, **kwargs)
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

def load_db() -> Dict[str, List[str]]:
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load DB: {e}")
            return {"solutions": [], "invalid_words": []}
    return {"solutions": [], "invalid_words": []}

def load_dictionary(length: int) -> List[str]:
    words = set()
    try:
        with (DATA_PATH / DICT_FILE).open("r", encoding="utf-8") as f:
            for line in f:
                w = line.strip()
                if w:
                    w_clean = remove_accents(w)
                    if len(w_clean) == length:
                        words.add(w_clean)
    except (FileNotFoundError, UnicodeDecodeError) as e:
        logger.warning(f"Error reading dictionary utf-8: {e}. Trying latin-1.")
        try:
            with (DATA_PATH / DICT_FILE).open("r", encoding="latin-1") as f:
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
        url = f"{BASE_URL}/active-game"
        response = robust_request('GET', url, cookies=COOKIES, headers=HEADERS)
        if response and response.status_code == 200:
            return response.json()
        logger.error(f"Error getting active game")
        return None
    except Exception as e:
        logger.exception(f"Exception getting active game: {e}")
        return None

def start_new_game() -> Optional[Dict[str, Any]]:
    try:
        url = f"{BASE_URL}/new-game"
        response = robust_request('POST', url, cookies=COOKIES, headers=HEADERS)
        if response and response.status_code == 200:
             return response.json()
        logger.error(f"Error creating new game")
        return None
    except Exception as e:
        logger.exception(f"Exception creating new game: {e}")
        return None

def play_game(db):
    game_data = get_active_game()
    if game_data and not game_data.get('has_active_game'):
        print("No active game found. Creating a new one...")
        game_data = start_new_game()
    if not game_data:
        print("Could not retrieve or create game.")
        return
    game_id = game_data.get('game_id')
    if not game_id:
        print("No game_id found in game data.")
        return
    word_length = game_data.get('word_length') or 5
    attempts = game_data.get('attempts') or 0
    print(f"\n--- Game: {game_id} (Length: {word_length}) ---")
    all_words = load_dictionary(word_length)
    if not all_words:
        print(f"No dictionary words found for length {word_length} from {DICT_FILE}!")
        return
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
            return
        if 'result' in res:
            new_candidates = filter_words(candidates, guess_word, res['result'])
            if not new_candidates:
                print("Warning: Filtering eliminated all candidates. Ignoring last filter result.")
            else:
                candidates = new_candidates
        time.sleep(0.5)

def submit_guess(game_id: str, word: str) -> Optional[Dict[str, Any]]:
    url = f"{BASE_URL}/{game_id}/guess"
    json_data = {'guess': word}
    response = robust_request('POST', url, cookies=COOKIES, headers=HEADERS, json=json_data)
    
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

def main():
    db = load_db()
    play_game(db)