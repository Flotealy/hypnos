import requests
import time
import json
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("score_spammer")

import os

# --- Configuration ---
EMAIL = os.environ.get("EMAIL")
PASSWORD = os.environ.get("PASSWORD")

if not EMAIL or not PASSWORD:
    raise ValueError("EMAIL and PASSWORD environment variables must be set.")
BASE_URL = 'https://play.hypnos2026.fr'
url = f'{BASE_URL}/api/sibreak/submit-score'

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

data = {
    "score": 500,
    "bricks_destroyed": 99,
    "max_combo": 99,
    "game_duration_ms": 180000,
    "won": True
}

def main():
    session = get_fresh_session()
    if not session: return

    logger.info("Starting score submitter loop (10 times)...")
    for _ in range(10):
        try:
            response = session.post(url, json=data)
            if response.status_code == 200:
                logger.info(f"SUCCESS - Status: {response.status_code}")
            else:
                logger.warning(f"FAILED - Status: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Error occurred: {e}")
        time.sleep(0.5)

if __name__ == "__main__":
    main()
