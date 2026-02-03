import requests
import time
import json
import logging
import os

from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("kahoot_solver")

BASE_URL = 'https://play.hypnos2026.fr'

# Fix: Use pathlib relative to script location
QUESTIONS_PATH = Path(__file__).resolve().parent.parent.parent.parent / "hypnos_code" / "challenges" / "kahoot" / "data" / "questions.json"

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

def load_answer_map():
    with open(QUESTIONS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    mapping = {}
    for q in data['questions']:
        q_text = q['question']
        correct_answer = next((a['text'] for a in q['answers'] if a.get('correct')), None)
        if correct_answer:
            mapping[q_text] = correct_answer
    return mapping, data.get('time_per_question', 10)

def solve_kahoot():
    logger.info("Loading questions...")
    answer_map, max_time = load_answer_map()
    logger.info(f"Loaded {len(answer_map)} answers.")
    session = get_fresh_session()
    if not session:
        return

    # 1. Start Game
    logger.info("Starting Kahoot session...")
    resp = session.post(f"{BASE_URL}/api/arg/kahoot/new-game", json={})
    
    if not resp.ok:
        logger.error(f"Failed to start game: {resp.text}")
        return

    game_data = resp.json().get("game_state")
    game_id = game_data.get("game_id")
    logger.info(f"Game started! ID: {game_id}")

    # 2. Game Loop
    while game_data and not game_data.get("game_over"):
        question_idx = game_data.get("current_question_index", 0)
        questions_list = game_data.get("questions", [])
        
        if question_idx >= len(questions_list):
            break
            
        question_obj = questions_list[question_idx]
        q_text = question_obj.get("question")
        answers_objs = question_obj.get("answers", [])
        answers_texts = [a.get("text") for a in answers_objs]
        
        correct_text = answer_map.get(q_text)
        if not correct_text:
            logger.error(f"Unknown question: {q_text}")
            break
            
        try:
            ans_idx = answers_texts.index(correct_text)
        except ValueError:
            logger.error(f"Answer '{correct_text}' not found in options: {answers_texts}")
            break
            
        logger.info(f"Q{question_idx+1}: {q_text} -> {correct_text} (Index {ans_idx})")
        
        payload = {"answer_index": ans_idx, "time_remaining": max_time} # Added max_time back
        
        # Sleep a tiny bit to be realistic
        time.sleep(0.5) 
        
        ans_resp = session.post(f"{BASE_URL}/api/arg/kahoot/{game_id}/answer", json=payload)
        
        if not ans_resp.ok:
            logger.error(f"Failed to submit answer: {ans_resp.text}")
            break
            
        res_data = ans_resp.json()
        logger.info(f"  -> Earned {res_data.get('points_earned')} pts. Total: {res_data.get('total_score')}")
        
        if res_data.get("questions_remaining") == 0:
            break
            
        state_resp = session.get(f"{BASE_URL}/api/arg/kahoot/active-game")
        if state_resp.ok:
            game_data = state_resp.json().get("game_state")
            if not game_data: break
        else:
            logger.error("Failed to refresh game state") # Added back error logging
            break

    # 3. Complete Game
    logger.info("Finishing game...")
    comp_resp = session.post(f"{BASE_URL}/api/arg/kahoot/{game_id}/complete")
    if comp_resp.ok:
        final_data = comp_resp.json()
        logger.info(f"GAME COMPLETE! Final Score: {final_data.get('final_score')}")
        logger.info(f"Message: {final_data.get('message')}")
    else:
        logger.error(f"Failed to complete game: {comp_resp.text}") # Added back error logging

if __name__ == "__main__":
    solve_kahoot()
