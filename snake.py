import requests
import os
from dotenv import load_dotenv

# Charge les variables d'environnement depuis le fichier .env
load_dotenv()

auth_token = os.getenv('AUTH_TOKEN')
csrf_token = os.getenv('CSRF_TOKEN')

if not auth_token or not csrf_token:
    print("Erreur: AUTH_TOKEN et/ou CSRF_TOKEN manquants dans le fichier .env")
    exit(1)

cookies = {
    'auth_token': auth_token,
    'csrf_token': csrf_token,
}

headers = {
    'accept': '*/*',
    'accept-language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
    'content-type': 'application/json',
    'origin': 'https://play.hypnos2026.fr',
    'priority': 'u=1, i',
    'referer': 'https://play.hypnos2026.fr/game/snake/',
    'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    'x-csrf-token': csrf_token,
}

# Payload simple avec score 4000
json_data = {
    'score': 4000,
    'completion_time': 27,
    'data': {
        'snake_size': 43,
        'won': False,
        'time_remaining': 93,
    },
}

print(f"Envoi unique d'une requête avec score={json_data['score']}...")

try:
    response = requests.post(
        'https://play.hypnos2026.fr/api/arg/challenges/1366125470/submit',
        cookies=cookies,
        headers=headers,
        json=json_data,
    )

    print(f"Status: {response.status_code}")
    print(response.json())
except Exception as e:
    print(f"Erreur lors de la requête: {e}")
