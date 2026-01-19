import os
import requests
import time
import concurrent.futures
from dotenv import load_dotenv

load_dotenv()

cookies = {
    'auth_token': os.getenv('AUTH_TOKEN'),
    'csrf_token': os.getenv('CSRF_TOKEN'),
}

headers = {
    'accept': '*/*',
    'accept-language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
    'content-type': 'application/json',
    'origin': 'https://play.hypnos2026.fr',
    'priority': 'u=1, i',
    'referer': 'https://play.hypnos2026.fr/game/sporcle/',
    'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    'x-csrf-token': os.getenv('CSRF_TOKEN'),
}

# Use a session for connection pooling (faster)
session = requests.Session()
session.cookies.update(cookies)
session.headers.update(headers)

json_data = {
    'theme_slug': 'clubs',
}

# Start game
response = session.post('https://play.hypnos2026.fr/api/arg/sporcle/new-game', json=json_data)
game_data = response.json()
game_id = game_data['game']['game_id']
print(f"Game started with ID: {game_id}")

words = [
    "bde",
    "absinthe",
    "asphalte",
    "bpm",
    "epicurieux",
    "equallity",
    "evryone",
    "int finance",
    "intimes",
    "intv",
    "kryptosphere",
    "mun'int",
    "muslim'int",
    "saint espr'it",
    "shalom'int",
    "asint",
    "echec&m'int",
    "kcrew",
    "pomp'int",
    "rock'int",
    "salsa'int",
    "xtreme",
    "bda",
    "anim'int",
    "aparte",
    "band'a michel",
    "cine club",
    "club jeux",
    "club zik",
    "cook'it",
    "declic",
    "emotys",
    "interlude",
    "paint'it",
    "model'it",
    "sing'int",
    "tell the tale",
    "trend'int",
    "minet",
    "cell",
    "club code",
    "gam'int",
    "hackademint",
    "int'ospace",
    "les partenariats d'excellence",
    "intervenir",
    "uni'vert",
    "epicer'int",
    "in&act",
    "forum",
    "promo2tel",
    "sprint",
    "welcom'",
    "african'it",
    "southasian'int",
    "intech",
    "bricol'int",
    "dolph'int",
    "marhiphop'int"
]

def send_guess(word):
    json_data = {
        'word': word,
    }
    while True:
        try:
            # Use session to send request (re-uses TCP connection)
            response = session.post(
                f'https://play.hypnos2026.fr/api/arg/sporcle/{game_id}/guess',
                json=json_data,
            )
            print(f"Sent: {word}, Status: {response.status_code}")
            
            if response.status_code >= 500:
                print(f"Received {response.status_code} for {word}, retrying...")
                time.sleep(0.2)
                continue
            
            print(response.json())
            break
            
        except Exception as e:
            print(f"Error sending {word}: {e}")
            time.sleep(0.5)
            continue

# Use ThreadPoolExecutor to send requests in parallel
# Adjust max_workers to control concurrency
with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
    for word in words:
        executor.submit(send_guess, word)
        # Delay between launching requests (does not wait for response)
        time.sleep(0.03)
