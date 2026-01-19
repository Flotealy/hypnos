import os
import requests
import time
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
    # 'cookie': 'auth_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NSIsImV4cCI6MTc2OTUxNzIzOSwidHlwZSI6ImFjY2VzcyIsImlhdCI6MTc2ODMwNzYzOSwianRpIjoiWHl1elU0QkZUWmc4VWpOalhnN3NkWUJ1UzZhUDdGT0g4U3hRVU1UenY0YyJ9.7JAXicQXnkpj0fZ7WbEaOgzhD6NZgAj1HVvG6io4snI; csrf_token=ZjCjxt37Ger88MoaNlenE6c2oTicSZABirCRX5g8dz8',
}


# Use a session for connection pooling (faster)
session = requests.Session()
session.cookies.update(cookies)
session.headers.update(headers)

json_data = {
    'theme_slug': 'bde',
}

# Start game
response = session.post('https://play.hypnos2026.fr/api/arg/sporcle/new-game', json=json_data)
game_data = response.json()
game_id = game_data['game']['game_id']
print(f"Game started with ID: {game_id}")

words = [
    "equinox",
    "sans interdits",
    "cosa nostra",
    "tentation",
    "intenz",
    "instinct",
    "impact",
    "tempo",
    "fusion",
    "caliente",
    "osmoz",
    "com'on",
    "hypnoz",
    "showtime",
    "shotgun",
    "flashback",
    "pandore",
    "phoenix",
    "apocalypse",
    "raven",
    "spectre",
    "kraken",
    "naga",
    "atlas",
    "astro",
    "aquila",
    "lycan",
    "adrenalint"
]

import concurrent.futures

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
        time.sleep(0.02)