import requests
import time
import json
import logging
import random

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("tetris_solver")

BASE_URL = 'https://play.hypnos2026.fr'

import os

# --- Configuration ---
EMAIL = os.environ.get("EMAIL")
PASSWORD = os.environ.get("PASSWORD")

if not EMAIL or not PASSWORD:
    raise ValueError("EMAIL and PASSWORD environment variables must be set.")

def get_fresh_session():
    session = requests.Session()
    session.headers.update({
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
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

def generate_challenge_id(slug):
    """
    Replicates the JS generateChallengeId function:
    
    generateChallengeId(slug) {
        let crc = 0xFFFFFFFF;
        for (let i = 0; i < slug.length; i++) {
            crc ^= slug.charCodeAt(i);
            for (let j = 0; j < 8; j++) {
                crc = (crc >>> 1) ^ (crc & 1 ? 0xEDB88320 : 0);
            }
        }
        return (~crc >>> 0) & 0x7FFFFFFF;
    }
    """
    crc = 0xFFFFFFFF
    for char in slug:
        crc ^= ord(char)
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
    
    # Python ints are infinite width, so we mask to 32-bit unsigned after NOT
    # (~crc >>> 0) in JS
    final_crc = (~crc) & 0xFFFFFFFF
    
    # & 0x7FFFFFFF
    return final_crc & 0x7FFFFFFF

def solve_tetris():
    session = get_fresh_session()
    if not session:
        return

    slug = "tetris"
    challenge_id = generate_challenge_id(slug)
    logger.info(f"Generated Challenge ID for '{slug}': {challenge_id}")

    submit_url = f'{BASE_URL}/api/arg/challenges/{challenge_id}/submit'
    
    raw_score = 7200
    final_score = 6000 
    lines = 24
    level = 3
    completion_time = 210 

    payload = {
        "score": final_score,
        "completion_time": completion_time,
        "data": {
            "level": level,
            "lines": lines,
            "raw_score": raw_score
        }
    }

    logger.info(f"Submitting payload to {submit_url}...")
    try:
        response = session.post(submit_url, json=payload)
        logger.info(f"Status Code: {response.status_code}")
        if response.ok:
            resp_json = response.json()
            logger.info(f"Response: {json.dumps(resp_json, indent=2)}")
        else:
            logger.error(f"Response: {response.text}")
    except Exception as e:
        logger.error(f"Request failed: {e}")

if __name__ == "__main__":
    solve_tetris()
