import time
import concurrent.futures
import sys
from typing import Dict, List, Any
from hypnos.lib.session import get_session
from hypnos.lib import setup_logger

logger = setup_logger("trivia_solver")

import json
from importlib import resources

DATA_PATH = resources.files("hypnos.trivia.data")
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
                f'https://play.hypnos2026.fr/api/arg/sporcle/{game_id}/guess',
                json=json_data,
            )
            # Log debug or info depending on verbosity desired
            logger.info(f"Sent: {word}, Status: {response.status_code}")
            
            if response.status_code >= 500:
                logger.warning(f"Received {response.status_code} for {word}, retrying...")
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
    session = get_session('https://play.hypnos2026.fr/game/sporcle/')
    
    try:
        response = session.post('https://play.hypnos2026.fr/api/arg/sporcle/new-game', json={'theme_slug': theme_slug})
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
    if len(sys.argv) > 2:
        theme = sys.argv[2].lower()
        solve_theme(theme)
    else:
        logger.info("No theme specified. Solving all themes...")
        for theme in THEMES:
            solve_theme(theme)

if __name__ == "__main__":
    main()
