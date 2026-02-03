import os
import requests
import json
import logging
import time
import concurrent.futures
import sys
from pathlib import Path
from typing import Dict, List, Any

# --- Configuration ---
EMAIL = os.environ.get("EMAIL")
PASSWORD = os.environ.get("PASSWORD")

if not EMAIL or not PASSWORD:
    raise ValueError("EMAIL and PASSWORD environment variables must be set.")
BASE_URL = 'https://play.hypnos2026.fr'

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

logger = setup_logger("trivia_solver")

def get_fresh_session():
    session = requests.Session()
    session.headers.update({
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'accept': 'application/json',
        'origin': BASE_URL,
        'referer': f'{BASE_URL}/login'
    })
    try:
        r_init = session.get(f"{BASE_URL}/api/csrf-token", timeout=10)
        csrf_token = r_init.json().get('csrf_token') or r_init.cookies.get('csrf_token')
        if csrf_token:
            session.headers.update({'x-csrf-token': csrf_token})
        
        r_login = session.post(f"{BASE_URL}/api/auth/login", json={"login": EMAIL, "password": PASSWORD}, timeout=10)
        if r_login.ok:
            logger.info("Login successful.")
            session.headers.update({'x-csrf-token': session.cookies.get('csrf_token', csrf_token)})
            return session
    except Exception as e:
        logger.error(f"Login error: {e}")
    return None

DATA_PATH = Path(__file__).parent / "data"
THEMES_FILE = DATA_PATH / "themes.json"

def load_themes() -> Dict[str, List[str]]:
    if THEMES_FILE.exists():
        try:
            with THEMES_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load themes: {e}")
            return {}
    return {}

THEMES = load_themes()

def send_guess(session: Any, game_id: str, word: str) -> Dict[str, Any]:
    json_data = {'word': word}
    while True:
        try:
            response = session.post(
                f'{BASE_URL}/api/arg/sporcle/{game_id}/guess',
                json=json_data,
            )
            logger.info(f"Sent: {word}, Status: {response.status_code}")
            
            if response.status_code >= 500:
                time.sleep(0.2)
                continue
            return response.json()
        except Exception as e:
             logger.error(f"Error sending {word}: {e}")
             time.sleep(0.5)
             continue

def solve_theme(theme_slug: str) -> None:
    if theme_slug not in THEMES:
        logger.error(f"Unknown theme: {theme_slug}")
        return

    logger.info(f"\n--- Solving Trivia Theme: {theme_slug} ---")
    session = get_fresh_session()
    if not session: return
    
    try:
        response = session.post(f'{BASE_URL}/api/arg/sporcle/new-game', json={'theme_slug': theme_slug})
        if response.status_code != 200:
            logger.error(f"Failed to start game: {response.status_code} - {response.text}")
            return
            
        game_data = response.json()
        game_id = game_data['game']['game_id']
        logger.info(f"Game started with ID: {game_id}")

        words = THEMES[theme_slug]
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            for word in words:
                executor.submit(send_guess, session, game_id, word)
                time.sleep(0.02)
    except Exception as e:
         logger.exception(f"Exception during solve_theme: {e}")

def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "solve":
         theme = sys.argv[2].lower() if len(sys.argv) > 2 else None
         if theme: solve_theme(theme)
         else:
             for theme in THEMES: solve_theme(theme)
    elif len(sys.argv) > 1:
        theme = sys.argv[1].lower()
        solve_theme(theme)
    else:
        logger.info("No theme specified. Solving all themes...")
        for theme in THEMES:
            solve_theme(theme)

if __name__ == "__main__":
    main()
