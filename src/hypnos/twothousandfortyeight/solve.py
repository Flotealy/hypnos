import os
import time
import requests
import random
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration ---
LOGIN_URL = 'https://play.hypnos2026.fr/api/auth/login'
LOGOUT_URL = 'https://play.hypnos2026.fr/api/auth/logout'
BASE_URL = 'https://play.hypnos2026.fr'
API_URL = "https://play.hypnos2026.fr/api/arg/2048"

EMAIL = os.environ.get("EMAIL")
PASSWORD = os.environ.get("PASSWORD")

if not EMAIL or not PASSWORD:
    raise ValueError("EMAIL and PASSWORD environment variables must be set.")

# Global session variable
session = None

def get_fresh_session():
    """
    Crée une nouvelle session, récupère le CSRF initial, et se connecte.
    Retourne la session authentifiée.
    """
    s = requests.Session()
    s.headers.update({
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
        'accept': 'application/json',
        'origin': 'https://play.hypnos2026.fr',
        'referer': 'https://play.hypnos2026.fr/login',
        'priority': 'u=1, i'
    })

    try:
        # Etape 1 : Récupérer les cookies initiaux (CSRF)
        print("--- Récupération CSRF via /api/csrf-token ...")
        csrf_url = "https://play.hypnos2026.fr/api/csrf-token"
        r_init = s.get(csrf_url, timeout=10)
        
        csrf_token = None
        try:
            data = r_init.json()
            if 'csrf_token' in data:
                csrf_token = data['csrf_token']
        except:
            pass
            
        if not csrf_token and 'csrf_token' in s.cookies:
            csrf_token = s.cookies['csrf_token']
            
        if not csrf_token:
             print("--- Fallback: Récupération CSRF via l'accueil...")
             s.get(BASE_URL, timeout=10)
             if 'csrf_token' in s.cookies:
                csrf_token = s.cookies['csrf_token']

        if csrf_token:
            s.headers.update({'x-csrf-token': csrf_token})
        else:
            print("!!! ATTENTION: Impossible de trouver un token CSRF")

        # Etape 2 : Login
        print(f"--- Tentative de connexion pour {EMAIL}...")
        payload = {"login": EMAIL, "password": PASSWORD}
        r_login = s.post(LOGIN_URL, json=payload, timeout=10)
        
        if r_login.status_code == 200:
            print("--- Login réussi !")
            if 'csrf_token' in s.cookies:
                s.headers.update({'x-csrf-token': s.cookies['csrf_token']})
            return s
        else:
            print(f"!!! ECHEC LOGIN (Code: {r_login.status_code})")
            print(f"    Réponse: {r_login.text}")
            return None

    except Exception as e:
        print(f"!!! Erreur lors du login : {e}")
        return None

# --- 2048 Game Logic for Simulation ---

def transpose(board):
    return [list(row) for row in zip(*board)]

def invert(board):
    return [row[::-1] for row in board]

def merge_row(row):
    new_row = [i for i in row if i != 0]
    for i in range(len(new_row) - 1):
        if new_row[i] == new_row[i+1]:
            new_row[i] *= 2
            new_row[i+1] = 0
    new_row = [i for i in new_row if i != 0]
    new_row = new_row + [0] * (4 - len(new_row))
    return new_row

def move_left(board):
    new_board = []
    for row in board:
        new_board.append(merge_row(row))
    return new_board

def move_right(board):
    inverted = invert(board)
    moved = move_left(inverted)
    return invert(moved)

def move_up(board):
    transposed = transpose(board)
    moved = move_left(transposed)
    return transpose(moved)

def move_down(board):
    transposed = transpose(board)
    moved = move_right(transposed)
    return transpose(moved)

MOVES = {
    'up': move_up,
    'down': move_down,
    'left': move_left,
    'right': move_right
}

def get_empty_cells(board):
    cells = []
    for r in range(4):
        for c in range(4):
            if board[r][c] == 0:
                cells.append((r, c))
    return cells

def boards_equal(b1, b2):
    for r in range(4):
        for c in range(4):
            if b1[r][c] != b2[r][c]:
                return False
    return True

# --- AI Solver (Expectimax) ---

# Snake Pattern: Force les grosses tuiles vers le bas-droite (3,3)
# Note: Ton 1024 est en bas à gauche actuellement, mais l'IA devrait s'adapter grâce à la profondeur.
SNAKE_WEIGHTS = [
    [2,   3,  4,  5],
    [9,   8,  7,  6],
    [10, 11, 12, 13],
    [20, 19, 18, 17]
]
EXP_WEIGHTS = [[4**val for val in row] for row in SNAKE_WEIGHTS]

def evaluate_board(board):
    """Score statique : Poids des tuiles + Bonus cases vides."""
    score = 0
    empty_count = 0
    for r in range(4):
        for c in range(4):
            val = board[r][c]
            if val == 0:
                empty_count += 1
            else:
                score += val * EXP_WEIGHTS[r][c]
    
    # Bonus vital pour la survie (augmenté pour favoriser la création d'espace)
    score += empty_count * 5000 
    return score

def expectimax(board, depth, is_player_turn):
    """
    Récursivité optimisée pour éviter le blocage 'no valid moves'.
    """
    # Si profondeur atteinte, on évalue
    if depth == 0:
        return evaluate_board(board)

    if is_player_turn:
        best_score = -float('inf')
        moved = False
        
        for direction, func in MOVES.items():
            new_board = func(board)
            if not boards_equal(new_board, board):
                moved = True
                score = expectimax(new_board, depth - 1, is_player_turn=False)
                if score > best_score:
                    best_score = score
        
        # CORRECTIF CRITIQUE :
        # Si 'moved' est False ici, c'est un Game Over dans la simulation.
        # Au lieu de renvoyer -inf, on renvoie le score actuel du board.
        # Cela permet à l'IA de distinguer une "mauvaise défaite" d'une "défaite honorable"
        # et de choisir le chemin qui mène le plus loin possible.
        return best_score if moved else evaluate_board(board)

    else:
        # Tour du hasard (apparition d'un 2 ou 4)
        empty_cells = get_empty_cells(board)
        
        # Si plus de place, c'est Game Over dans la simulation -> on retourne le score
        if not empty_cells:
            return evaluate_board(board)

        # Optimisation : Echantillonnage si trop de cases vides
        if len(empty_cells) > 5 and depth >= 3:
            empty_cells = random.sample(empty_cells, 5)

        avg_score = 0
        total_weight = 0
        
        for r, c in empty_cells:
            # Simulation 2 (90% proba)
            # Copie manuelle rapide
            b2 = [row[:] for row in board]
            b2[r][c] = 2
            score2 = expectimax(b2, depth - 1, is_player_turn=True)
            avg_score += 0.9 * score2
            
            # Simulation 4 (10% proba)
            b4 = [row[:] for row in board]
            b4[r][c] = 4
            score4 = expectimax(b4, depth - 1, is_player_turn=True)
            avg_score += 0.1 * score4
            
            total_weight += 1
            
        return avg_score / total_weight

def get_best_move(board):
    """Détermine le meilleur mouvement avec fallback de sécurité."""
    empty_len = len(get_empty_cells(board))
    
    # Ajustement dynamique de la profondeur vs vitesse
    if empty_len >= 8:
        search_depth = 2
    elif empty_len >= 4:
        search_depth = 3
    else:
        search_depth = 4 # Mode survie (ton cas actuel)

    best_score = -float('inf')
    best_move = None
    
    legal_moves = []
    for direction, func in MOVES.items():
        outcome = func(board)
        if not boards_equal(outcome, board):
            legal_moves.append((direction, outcome))
    
    if not legal_moves:
        return None

    # CORRECTIF SÉCURITÉ :
    # On initialise best_move avec le premier coup légal valide.
    # Ainsi, si tous les scores renvoyés sont pourris (ex: -inf),
    # l'IA jouera quand même quelque chose au lieu de planter.
    best_move = legal_moves[0][0]
    
    for direction, outcome in legal_moves:
        score = expectimax(outcome, search_depth, is_player_turn=False)
        
        # Debug optionnel pour voir ce que l'IA pense
        # print(f"Dir: {direction}, Score: {score}")
        
        if score > best_score:
            best_score = score
            best_move = direction
            
    return best_move

# --- API Interaction ---

def _handle_request(method, url, **kwargs):
    global session
    if not session:
        session = get_fresh_session()
        if not session: return None

    try:
        response = session.request(method, url, **kwargs)
        if response.status_code == 401:
            print("⚠️ Session expirée, tentative de reconnexion...")
            session = get_fresh_session()
            if session:
                response = session.request(method, url, **kwargs)
            else:
                return None
        
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error Request ({url}): {e}")
        return None

def check_active_game():
    url = f"{API_URL}/active-game"
    print(f"Checking for active game via {url}...")
    return _handle_request('GET', url, timeout=5)

def start_game():
    url = f"{API_URL}/new-game"
    print(f"Starting new game via {url}...")
    return _handle_request('POST', url, timeout=5)

def make_api_move(game_id, direction):
    url = f"{API_URL}/{game_id}/move"
    data = {"direction": direction}
    return _handle_request('POST', url, json=data, timeout=5)

def print_game_board(board_data, score, paused=False, delay=0.0, last_move=None):
    if os.environ.get("EMAIL"):
        print(f"Score: {score}")
        return
    os.system('cls' if os.name == 'nt' else 'clear')
    sidebar = [
        "Controls:",
        "  [P] Pause/Resume",
        "  [+] Increase Speed",
        "  [-] Decrease Speed",
        "  [Arrows/WASD] Manual",
        "  [Q] Quit",
        "",
        f"Status: {'PAUSED' if paused else 'RUNNING'}",
        f"Delay: {delay:.2f}s",
        f"Last Move: {last_move.upper() if last_move else 'None'}"
    ]
    lines = []
    lines.append(f"Score: {score}")
    lines.append("-" * 21)
    for row in board_data:
        lines.append("|" + "|".join(f"{cell:4d}" if cell != 0 else "    " for cell in row) + "|")
        lines.append("-" * 21)
    
    max_len = max(len(lines), len(sidebar))
    for i in range(max_len):
        l = lines[i] if i < len(lines) else " " * 21
        s = sidebar[i] if i < len(sidebar) else ""
        print(f"{l:<25} {s}")

def run_single_game(session, game_data):
    import msvcrt # Windows only

    if not game_data: return

    game_id = game_data['game_id']
    board = game_data['board']
    score = game_data['score']

    # Speed settings
    delay = 0.0
    paused = False
    last_ai_move_time = 0
    last_move = None

    print_game_board(board, score, paused, delay, last_move)
    print("Game started!")

    while True:
        manual_move = None
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key in (b'\x00', b'\xe0'):
                key = msvcrt.getch()
                if key == b'H': manual_move = 'up'
                elif key == b'P': manual_move = 'down'
                elif key == b'K': manual_move = 'left'
                elif key == b'M': manual_move = 'right'
            else:
                try:
                    char = key.decode('utf-8').lower()
                    if char == 'q': return False # Stopped by user
                    elif char == 'p': 
                        paused = not paused
                        print_game_board(board, score, paused, delay, last_move)
                    elif char == '+': 
                        delay = max(0.0, delay - 0.1)
                        print_game_board(board, score, paused, delay, last_move)
                    elif char == '-': 
                        delay += 0.1
                        print_game_board(board, score, paused, delay, last_move)
                    elif char == 'w': manual_move = 'up'
                    elif char == 's': manual_move = 'down'
                    elif char == 'a': manual_move = 'left'
                    elif char == 'd': manual_move = 'right'
                except: pass

        if manual_move:
            move_to_execute = manual_move
        elif not paused and (delay <= 0 or (time.time() - last_ai_move_time >= delay)):
            move_to_execute = get_best_move(board)
            if not move_to_execute:
                print("AI found no valid moves. Game might be over.")
                break # Game corrupted or bugged
            last_ai_move_time = time.time()
        else:
            move_to_execute = None

        if move_to_execute:
            last_move = move_to_execute
            new_state = make_api_move(game_id, move_to_execute)
            if new_state:
                board = new_state['board']
                score = new_state['score']
                print_game_board(board, score, paused, delay, last_move)
                if new_state.get('game_over'):
                    print("\nGAME OVER!")
                    print("YOU WON!" if new_state.get('won') else f"Final Score: {score}")
                    time.sleep(2) # Little pause before next game
                    return True # Completed game, continue loop
            else:
                print("Sync error, retrying...")

        time.sleep(0.001)
    return True

def main():
    import msvcrt # Windows only

    global session
    session = get_fresh_session()
    if not session:
        return

    # Check for existing game first
    active_check = check_active_game()
    if active_check and active_check.get("has_active_game"):
        print(f"Found active game! ID: {active_check['game']['game_id']}, Score: {active_check['game']['score']}")
        print("Resuming...")
        time.sleep(1)
        if not run_single_game(session, active_check['game']):
            return # User quit

    while True:
        print("\nStarting new game...")
        game_data = start_game()
        if not game_data:
            print("Failed to start game. Retrying in 5s...")
            time.sleep(5)
            continue
            
        if not run_single_game(session, game_data):
            break # User quit
            
        if os.environ.get("SOLVE_ONCE") == "1":
            print("SOLVE_ONCE set, exiting.")
            break

    print("Exiting...")

if __name__ == "__main__":
    main()