import requests
from hypnos.lib.session import get_cookies, get_headers
from hypnos.lib import setup_logger
from hypnos.snake.models import SnakePayload

logger = setup_logger("snake_solver")

import json
from importlib import resources

DATA_PATH = resources.files("hypnos.snake.data")
PAYLOAD_FILE = DATA_PATH / "payload.json"

def main() -> None:
    cookies = get_cookies()
    headers = get_headers('https://play.hypnos2026.fr/game/snake/', cookies['csrf_token'])

    # Charger le payload depuis le fichier
    if PAYLOAD_FILE.exists():
        try:
            with PAYLOAD_FILE.open("r", encoding="utf-8") as f:
                raw_data = json.load(f)
                # Validation Pydantic
                payload = SnakePayload(**raw_data)
                json_data = payload.model_dump()
        except Exception as e:
            logger.error(f"Erreur de validation/chargement du payload: {e}")
            return
    else:
        logger.error(f"Erreur: {PAYLOAD_FILE} introuvable.")
        return

    logger.info(f"Envoi unique d'une requête avec score={json_data['score']}...")

    try:
        response = requests.post(
            'https://play.hypnos2026.fr/api/arg/challenges/1366125470/submit',
            cookies=cookies,
            headers=headers,
            json=json_data,
        )

        logger.info(f"Status: {response.status_code}")
        if response.status_code == 200:
             logger.info(response.json())
        else:
             logger.warning(f"Response: {response.text}")
             
    except Exception as e:
        logger.exception(f"Erreur lors de la requête: {e}")

if __name__ == "__main__":
    main()
