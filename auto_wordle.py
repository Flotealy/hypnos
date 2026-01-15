import requests
import json
import time
import random
import os
import unicodedata
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
DATA_FILE = "wordle_db.json"
DICT_FILE = "mots.txt"
BASE_URL = "https://play.hypnos2026.fr/api/arg/wordle"

COOKIES = {
    'auth_token': os.getenv('AUTH_TOKEN'),
    'csrf_token': os.getenv('CSRF_TOKEN'),
}

HEADERS = {
    'accept': 'application/json',
    'accept-language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
    'content-type': 'application/json',
    'origin': 'https://play.hypnos2026.fr',
    'priority': 'u=1, i',
    'referer': 'https://play.hypnos2026.fr/game/wordle/',
    'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    'x-csrf-token': os.getenv('CSRF_TOKEN'),
}

# --- Utils ---
def remove_accents(input_str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).upper()

# --- Data Management ---

def load_db():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"solutions": [], "invalid_words": []}
    return {"solutions": [], "invalid_words": []}

def save_db(db):
    db["solutions"] = list(set(db["solutions"]))
    db["invalid_words"] = list(set(db["invalid_words"]))
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=4)

def load_dictionary(length):
    words = set()
    if os.path.exists(DICT_FILE):
        try:
            with open(DICT_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    w = line.strip()
                    if w:
                        w_clean = remove_accents(w)
                        if len(w_clean) == length:
                            words.add(w_clean)
        except UnicodeDecodeError:
             # Fallback for other encodings
             with open(DICT_FILE, 'r', encoding='latin-1') as f:
                for line in f:
                    w = line.strip()
                    if w:
                        w_clean = remove_accents(w)
                        if len(w_clean) == length:
                            words.add(w_clean)
                            
    return list(words)

# --- API Interaction ---

def create_game():
    try:
        url = f"{BASE_URL}/active-game"
        response = requests.get(url, cookies=COOKIES, headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        print(f"Error creating game: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        print(f"Exception creating game: {e}")
        return None

def submit_guess(game_id, word):
    try:
        url = f"{BASE_URL}/{game_id}/guess"
        json_data = {'guess': word}
        response = requests.post(url, cookies=COOKIES, headers=HEADERS, json=json_data)
        
        if response.status_code == 400:
            try:
                err = response.json()
                if err.get('detail') in ["Not a valid word", "Guess must be X letters"]:
                    return {"status": "invalid_word"}
            except:
                pass
        
        if response.status_code == 200:
            return response.json()
            
        print(f"Error guessing: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        print(f"Exception guessing: {e}")
        return None

# --- Logic ---

def filter_words(candidates, guess, result):
    new_candidates = []
    for word in candidates:
        possible = True
        for i, (letter, status) in enumerate(zip(guess, result)):
            if status == 'correct':
                if word[i] != letter:
                    possible = False
                    break
            elif status == 'absent':
                if letter in word:
                    # Check if this letter is marked correct or present elsewhere
                    is_elsewhere = False
                    for j, (l2, s2) in enumerate(zip(guess, result)):
                        if l2 == letter and (s2 == 'correct' or s2 == 'present'):
                            is_elsewhere = True
                            break
                    
                    if not is_elsewhere:
                         # Strictly excluded
                         if letter in word:
                             possible = False
                             break
                    else:
                        # Present elsewhere, but not here
                        if word[i] == letter:
                            possible = False
                            break
            elif status == 'present':
                if letter not in word:
                    possible = False
                    break
                if word[i] == letter:
                    possible = False
                    break
        if possible:
            new_candidates.append(word)
    return new_candidates

def get_active_game():
    try:
        url = f"{BASE_URL}/active-game"
        response = requests.get(url, cookies=COOKIES, headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        print(f"Error getting active game: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        print(f"Exception getting active game: {e}")
        return None

def start_new_game():
    try:
        url = f"{BASE_URL}/new-game"
        # The user's new_game.py uses POST with empty body (implicit)
        response = requests.post(url, cookies=COOKIES, headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        if response.status_code == 429:
             print("Rate limit reached (429). Waiting 60s...")
             time.sleep(60)
             return None
        print(f"Error creating new game: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        print(f"Exception creating new game: {e}")
        return None

def play_game(db):
    # 1. Check for active game
    game_data = get_active_game()
    
    if game_data and not game_data.get('has_active_game'):
         print("No active game found. Creating a new one...")
         game_data = start_new_game()
    
    if not game_data:
        print("Could not retrieve or create game.")
        return

    # If we just created a game, game_data doesn't have 'has_active_game' key based on new_game.py comment, 
    # it has game_id directly. If we got it from active-game, it might have it.
    # We should check if 'game_id' is present.
    game_id = game_data.get('game_id')
    if not game_id:
        # Maybe active-game returned something but no game_id?
        # If has_active_game was true, it should have game_id.
        # Let's re-verify logic.
        print("No game_id found in game data.")
        return

    word_length = game_data.get('word_length') or 5
    attempts = game_data.get('attempts') or 0
    
    print(f"\n--- Game: {game_id} (Length: {word_length}) ---")

    # Load candidates
    # 1. Start with full dictionary of that length
    all_words = load_dictionary(word_length)
    if not all_words:
        print(f"No dictionary words found for length {word_length} from {DICT_FILE}!")
        return

    # 2. Exclude known invalid words
    # Filter using db['invalid_words']
    candidates = [w for w in all_words if w not in db["invalid_words"]]
    
    # 3. Prioritize known solutions
    # explicitly gather solutions from DB that match length and aren't invalid
    solutions_candidates = [w for w in db["solutions"] if len(w) == word_length and w not in db["invalid_words"]]
    
    # Identify the rest of the candidates from the dictionary
    # They must not be invalid, and we don't want to duplicate what's already in solutions_candidates
    sol_set = set(solutions_candidates)
    dictionary_candidates = [w for w in all_words if w not in db["invalid_words"] and w not in sol_set]
    
    # Shuffle the dictionary words to explore
    random.shuffle(dictionary_candidates)
    
    # Reassemble: Known solutions first, then random others
    candidates = solutions_candidates + dictionary_candidates
    print(f"Prioritizing {len(solutions_candidates)} known solution(s).")
    
    board = game_data.get('board', [])
    if board:
        print(f"Resuming with {len(board)} existing guesses...")
        for turn in board:
             guess_word = "".join([x['letter'] for x in turn])
             result_list = [x['status'] for x in turn]
             candidates = filter_words(candidates, guess_word, result_list)

    while attempts < 6:
        if not candidates:
            print("No more strict candidates! Relaxing constraints to find ANY valid word...")
            # If we are stuck, we might have filtered too aggressively or our dictionary lacks the specific word.
            # We will reload the full dictionary of that length and pick a word we haven't tried in this game yet.
            fallback_words = load_dictionary(word_length)
            # Remove words we already tried in this specific game session (reconstruct from board if needed, but 'candidates' logic handled it)
            # We need to know what we ALREADY guessed.
            # The 'board' in game_data is initial state. We need to track current session guesses.
            # Let's inspect game_data again if possible, or track local guesses.
            # For simplicity, just pick a random word from fallback_words that is NOT in our local 'candidates' (which is empty) 
            # and hopefully wasn't just tried. To be safe, let's just pick random.
            if not fallback_words:
                 print("Critical: Dictionary empty for this length!")
                 break
            
            # Filter out invalid words still
            fallback_words = [w for w in fallback_words if w not in db["invalid_words"]]
            
            if not fallback_words:
                print("Critical: All dictionary words marked invalid!")
                break
                
            guess_word = random.choice(fallback_words)
            print(f"Fallback guess: {guess_word}")
        else:
            guess_word = candidates[0] 

        print(f"Attempt {attempts+1}/6: Guessing {guess_word} (Candidates: {len(candidates)})")
        
        res = submit_guess(game_id, guess_word)
        if not res:
            break
            
        if res.get('status') == "invalid_word":
            print(f"Invalid word: {guess_word}")
            if guess_word not in db['invalid_words']:
                db['invalid_words'].append(guess_word)
                save_db(db)
            # Remove from candidates and current dictionary logic for next run
            if guess_word in candidates:
                candidates.remove(guess_word)
            continue

        attempts = res.get('attempts', attempts + 1)
        
        if res.get('game_over'):
            is_won = res.get('won')
            correct_word = res.get('word')
            
            if is_won:
                 if not correct_word:
                     correct_word = guess_word
                     
                 print(f"!!! VICTORY !!! Answer: {correct_word}")
                 if correct_word:
                    if correct_word not in db["solutions"]:
                        print(f"-> Adding {correct_word} to solutions DB.")
                        db["solutions"].append(correct_word)
                        save_db(db)
            else:
                 print(f"GAME OVER (LOST). Answer revealed: {correct_word}")
                 if correct_word:
                      # Sometimes it reveals the word even if we lost
                      if correct_word not in db["solutions"]:
                            print(f"-> Adding {correct_word} to solutions DB (from loss).")
                            db["solutions"].append(correct_word)
                            save_db(db)
                 else:
                      print("Game lost and answer NOT revealed.")

            return

        if 'result' in res:
             # Standard filtering
             new_candidates = filter_words(candidates, guess_word, res['result'])
             
             # If filtering leads to 0 candidates, don't apply it strictly for next turn, 
             # just remove the word we just guessed.
             if not new_candidates:
                 print("Warning: Filtering eliminated all candidates. Ignoring last filter result.")
                 if guess_word in candidates:
                     candidates.remove(guess_word)
             else:
                 candidates = new_candidates
                 if guess_word in candidates:
                     candidates.remove(guess_word)

        time.sleep(0.5)

def main():
    while True:
        db = load_db()
        play_game(db)
        print("Cooldown 13s...")
        time.sleep(13)

if __name__ == "__main__":
    main()
