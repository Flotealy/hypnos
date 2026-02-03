import requests
import time
import random
import math
import logging
import json
import os

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("typing_solver")

# Configuration
BASE_URL = 'https://play.hypnos2026.fr'
LOGIN_URL = f'{BASE_URL}/api/auth/login'
START_URL = f'{BASE_URL}/api/arg/typing/start'
SUBMIT_URL = f'{BASE_URL}/api/arg/typing/submit'

EMAIL = os.environ.get("EMAIL")
PASSWORD = os.environ.get("PASSWORD")

if not EMAIL or not PASSWORD:
    raise ValueError("EMAIL and PASSWORD environment variables must be set.")

# Targets
TARGET_WPM = 192  # Max is 200, staying very close for max points
MIN_CV = 0.15     # Server requires CV >= 0.15

class TypingBot:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'accept': 'application/json',
            'origin': BASE_URL,
            'referer': f'{BASE_URL}/'
        })

    def sync_csrf(self):
        # Handle cases where multiple cookies with the same name might exist
        token = None
        for cookie in self.session.cookies:
            if cookie.name == 'csrf_token':
                token = cookie.value
                # Usually we want the last one (most specific) or we can filter by domain
        
        if token:
            self.session.headers.update({'x-csrf-token': token})
            return True
        return False

    def authenticate(self):
        logger.info("Retrieving CSRF token...")
        try:
            r = self.session.get(f'{BASE_URL}/api/csrf-token', timeout=10)
            if r.status_code == 429:
                logger.error("Rate limit hit. Wait 65s.")
                time.sleep(65)
                return False
            
            # CSRF token is in JSON and should be in cookies too
            data = r.json()
            token = data.get('csrf_token')
            if token:
                # Manually set the cookie if it somehow failed to auto-set
                self.session.cookies.set('csrf_token', token, domain='play.hypnos2026.fr', path='/')
                self.sync_csrf()
                logger.info("Initial CSRF token obtained and synced.")
            else:
                logger.error("No token in response.")
                return False
        except Exception as e:
            logger.error(f"Error getting CSRF: {e}")
            return False

        logger.info(f"Logging in as {EMAIL}...")
        try:
            # Sync before login just in case, though login is usually exempt
            self.sync_csrf()
            r = self.session.post(LOGIN_URL, json={"login": EMAIL, "password": PASSWORD}, timeout=10)
            
            if r.status_code == 429:
                logger.error("Login Rate limit hit. Wait 60s.")
                return False
                
            if r.ok:
                logger.info("Login successful.")
                # Sync again after login as credentials might set new cookies
                self.sync_csrf()
                return True
            else:
                logger.error(f"Login failed: {r.status_code} - {r.text}")
                return False
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    def generate_timings(self, text, target_wpm):
        char_count = len(text)
        total_time_ms = 60000 * (char_count / 5) / target_wpm
        avg_interval_ms = total_time_ms / char_count
        
        # Target CV ~ 0.22 to be safe
        std_dev = avg_interval_ms * 0.22
        
        intervals = []
        for _ in range(char_count - 1):
            interval = random.gauss(avg_interval_ms, std_dev)
            interval = max(25, interval) # Min 15 in backend, use 25 for safety
            intervals.append(interval)
            
        # Scale to match total_time_ms
        scale = total_time_ms / sum(intervals)
        intervals = [i * scale for i in intervals]
        
        timestamps = [0]
        curr = 0
        for i in intervals:
            curr += i
            timestamps.append(int(curr))
            
        # Internal verify
        mean = sum(intervals) / len(intervals)
        cv = (sum((x - mean)**2 for x in intervals)/len(intervals))**0.5 / mean
        logger.info(f"Stats: CV={cv:.3f}, WPM={target_wpm}, Time={timestamps[-1]/1000:.1f}s")
        
        if cv < 0.16: return self.generate_timings(text, target_wpm)
        return timestamps

    def solve(self):
        if not self.authenticate():
            return

        logger.info("Starting game session...")
        self.sync_csrf()
        try:
            r = self.session.post(START_URL, timeout=10)
            if not r.ok:
                logger.error(f"Start failed ({r.status_code}): {r.text}")
                if "CSRF" in r.text or r.status_code == 403:
                    logger.info("Attempting to refresh CSRF and retry...")
                    self.session.get(f'{BASE_URL}/api/csrf-token')
                    self.sync_csrf()
                    r = self.session.post(START_URL, timeout=10)
                    if not r.ok: return
                else:
                    return
            
            data = r.json()
            sid = data['session_id']
            quote = data['quote']
            logger.info(f"Session: {sid}, Quote Length: {len(quote)}")
        except Exception as e:
            logger.error(f"Session error: {e}")
            return

        timings = self.generate_timings(quote, TARGET_WPM)
        sleep_dur = (timings[-1] / 1000) + 1.0 # Add small buffer
        logger.info(f"Simulating human typing speed... ({sleep_dur:.2f}s)")
        time.sleep(sleep_dur)

        payload = {
            "session_id": sid,
            "typed_text": quote,
            "keystroke_timings": timings
        }

        logger.info("Submitting results...")
        self.sync_csrf()
        try:
            r = self.session.post(SUBMIT_URL, json=payload, timeout=10)
            if r.ok:
                res = r.json()
                logger.info(f"Result: {res['message']}")
                if res.get('cheater_detected'):
                    logger.error("FLAGGED AS CHEATER!")
            else:
                logger.error(f"Submit error ({r.status_code}): {r.text}")
        except Exception as e:
            logger.error(f"Submit exception: {e}")

if __name__ == "__main__":
    bot = TypingBot()
    bot.solve()
