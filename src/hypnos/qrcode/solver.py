import requests
import time
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("qrhunt_solver")

BASE_URL = 'https://play.hypnos2026.fr'
SUBMIT_URL = f'{BASE_URL}/api/arg/qr-hunt/submit'

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
        # Try both direct response and cookies for CSRF
        csrf_token = r_init.json().get('csrf_token') or r_init.cookies.get('csrf_token')
        if csrf_token:
            session.headers.update({'x-csrf-token': csrf_token})
        
        r_login = session.post(f"{BASE_URL}/api/auth/login", json={"login": EMAIL, "password": PASSWORD}, timeout=10)
        if r_login.ok:
            logger.info("Login successful.")
            # Sync CSRF token again after login as it might have changed
            new_csrf = session.cookies.get('csrf_token')
            if new_csrf:
                session.headers.update({'x-csrf-token': new_csrf})
            return session
    except Exception as e:
        logger.error(f"Login error: {e}")
    return None


# Valid passwords found in hypnos_code/challenges/qr-hunt/codes.json
PASSWORDS = [
    "CETAIT-FACILE",
    "MERCI-YANN",
    "HYPNUM-7118",
    "HOW-DID-YOU-FIND-THIS",
    "RANGEZ-CAAAA"
]

def solve():
    session = get_fresh_session()
    if not session:
        return

    logger.info(f"Démarrage de la soumission de {len(PASSWORDS)} codes...")

    for password in PASSWORDS:
        payload = {"password": password}
        try:
            logger.info(f"Soumission de : {password}")
            response = session.post(SUBMIT_URL, json=payload, timeout=10)
            
            # Gestion Rate Limit
            if response.status_code == 429:
                logger.warning(f"!!! RATE LIMIT (429) sur {password}. Pause de 5 secondes...")
                time.sleep(5)
                # Retry once
                response = session.post(SUBMIT_URL, json=payload, timeout=10)

            try:
                data = response.json()
                success = data.get('success')
                message = data.get('message', '')
                already_found = data.get('already_found')

                if success is True:
                    logger.info(f"!!! SUCCÈS pour {password} !!!")
                    logger.info(f"    Message: {message}")
                elif already_found:
                    logger.info(f"Code {password} : DÉJÀ TROUVÉ")
                else:
                    logger.info(f"Code {password} : ÉCHEC - {message} (Code: {response.status_code})")

            except ValueError:
                logger.error(f"Erreur Parsing JSON pour {password} (Code: {response.status_code})")

            # Petite pause entre chaque soumission pour être safe
            time.sleep(1)

        except Exception as e:
            logger.error(f"Erreur requête pour {password} : {e}")
            time.sleep(1)

    logger.info("Terminé !")

if __name__ == "__main__":
    solve()
