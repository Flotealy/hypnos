import requests
import time
import json
import logging
import concurrent.futures
import os
import sys

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("sporcle_solver")

BASE_URL = 'https://play.hypnos2026.fr'

# --- Configuration ---
EMAIL = os.environ.get("EMAIL")
PASSWORD = os.environ.get("PASSWORD")

if not EMAIL or not PASSWORD:
    raise ValueError("EMAIL and PASSWORD environment variables must be set.")

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

THEMES = {
    "bde": [
        "lycan", "aquila", "astro", "atlas", "naga", "kraken", "spectre", "raven",
        "apocalypse", "phoenix", "pandore", "flashback", "shotgun", "showtime",
        "hypnoz", "com'on", "osmoz", "caliente", "fusion", "tempo", "impact",
        "instinct", "intenz", "tentation", "cosa nostra", "sans interdits",
        "adrenalint", "equinox"
    ],
    "clubs": [
        "bde", "asint", "minet", "forum", "promo2tel", "int finance", "intervenir",
        "bda", "hackademint", "emotys", "bpm", "absinthe", "intv", "equallity",
        "intimes", "epicurieux", "kryptosphere", "asphalte", "muslim'int",
        "saint espr'it", "shalom'int", "xtreme", "rock'int", "pomp'int",
        "echec&m'int", "anim'int", "aparte", "band'a michel", "cine club",
        "club jeux", "club zik", "cook'it", "declic", "interlude", "kcrew",
        "model'it", "paint'it", "sing'int", "tell the tale", "trend'int",
        "intech", "bricol'int", "gam'int", "club code", "cell", "int'o space",
        "evryone", "dolph'int", "uni'vert", "epicer'int", "in&act", "welcom'",
        "african'it", "les partenariats d'excellence", "sprint", "marhiphop'int",
        "mun'int", "salsa'int", "southasian'int"
    ],
    "listeux": [
        "theo lauret", "lucie chasse", "victoria oppeneau",
        "hyrrokinne riquelme-honore", "jonathan heilmann", "erwan fournier",
        "alp meunier", "camille perrot", "matthieu viala", "yann miquel-erdmann",
        "manuel brillantes tavares", "amandine linck", "anastasia levillain",
        "mathieu moenne-loccoz", "matteo garnier", "alexandre vial",
        "theo darvoux", "dimitri f", "lucas thuries", "gontran meunier",
        "nikopol markgraf", "titouan jouanot-goupil", "phileas nedelec",
        "yann salauze", "layla gabriel", "solene champion", "adrien lasade",
        "ethan durand", "gabriel sabbah", "dimitri boussion", "nachid raslane"
    ]
}

SAFE_DURATION_SECONDS = 5.5 # Minimum duration to avoid 5s ban

def send_guess(session, game_id, word):
    try:
        resp = session.post(f"{BASE_URL}/api/arg/sporcle/{game_id}/guess", json={"word": word})
        if not resp.ok:
            logger.warning(f"Request failed for '{word}': {resp.status_code}")
        else:
            data = resp.json()
            if not data.get("correct"):
                logger.warning(f"Incorrect guess for '{word}': {data.get('message')}")
    except Exception as e:
        logger.error(f"Exc sending '{word}': {e}")

def solve_theme(session, slug, words):
    logger.info(f"=== Starting Theme: {slug.upper()} ===")
    
    # 1. Start New Game
    resp = session.post(f"{BASE_URL}/api/arg/sporcle/new-game", json={"theme_slug": slug})
    
    if not resp.ok:
        logger.error(f"Failed to start game: {resp.text}")
        return
        
    game_data = resp.json().get("game")
    game_id = game_data.get("game_id")
    logger.info(f"Game started! ID: {game_id}")
    
    start_time = time.time()
    
    # 2. Parallel submit all EXCEPT the last one
    words_to_send_fast = words[:-1]
    final_word = words[-1]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(send_guess, session, game_id, w) for w in words_to_send_fast]
        concurrent.futures.wait(futures)
        
    # 3. Wait for safety
    elapsed = time.time() - start_time
    if elapsed < SAFE_DURATION_SECONDS:
        sleep_needed = SAFE_DURATION_SECONDS - elapsed
        logger.info(f"Waiting {sleep_needed:.2f}s for safety buffer...")
        time.sleep(sleep_needed)
    
    # 4. Final word
    send_guess(session, game_id, final_word)
        
    final_elapsed = time.time() - start_time
    logger.info(f"Finished {slug} in {final_elapsed:.2f}s")

def main():
    session = get_fresh_session()
    if not session: return
    for theme, words in THEMES.items():
        solve_theme(session, theme, words)
        time.sleep(1) # Pause between themes

if __name__ == "__main__":
    main()
