import os
import requests
import time
import random
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# --- Configuration ---
LOGIN_URL = 'https://play.hypnos2026.fr/api/auth/login'
LOGOUT_URL = 'https://play.hypnos2026.fr/api/auth/logout'
BASE_URL = 'https://play.hypnos2026.fr'
API_URL = "https://play.hypnos2026.fr/api/arg/minesweeper"

EMAIL = os.environ.get("EMAIL")
PASSWORD = os.environ.get("PASSWORD")

if not EMAIL or not PASSWORD:
    raise ValueError("EMAIL and PASSWORD environment variables must be set.")

def get_fresh_session():
    """
    Crée une nouvelle session, récupère le CSRF initial, et se connecte.
    Retourne la session authentifiée.
    """
    session = requests.Session()
    session.headers.update({
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
        'accept': 'application/json',
        'origin': 'https://play.hypnos2026.fr',
        'referer': 'https://play.hypnos2026.fr/login'
    })

    try:
        # Etape 1 : Récupérer les cookies initiaux (CSRF)
        print("--- Récupération CSRF via /api/csrf-token ...")
        csrf_url = "https://play.hypnos2026.fr/api/csrf-token"
        r_init = session.get(csrf_url, timeout=10)
        
        csrf_token = r_init.json().get('csrf_token') or r_init.cookies.get('csrf_token')
            
        if not csrf_token:
             print("--- Fallback: Récupération CSRF via l'accueil...")
             session.get(BASE_URL, timeout=10)
             csrf_token = session.cookies.get('csrf_token')

        if csrf_token:
            session.headers.update({'x-csrf-token': csrf_token})
        else:
            print("!!! ATTENTION: Impossible de trouver un token CSRF")

        # Etape 2 : Login
        print(f"--- Tentative de connexion pour {EMAIL}...")
        payload = {"login": EMAIL, "password": PASSWORD}
        r_login = session.post(LOGIN_URL, json=payload, timeout=10)
        
        if r_login.status_code == 200:
            print("--- Login réussi !")
            # Sync CSRF token again after login
            new_csrf = session.cookies.get('csrf_token')
            if new_csrf:
                session.headers.update({'x-csrf-token': new_csrf})
            return session
        else:
            print(f"!!! ECHEC LOGIN (Code: {r_login.status_code})")
            print(f"    Réponse: {r_login.text}")
            return None

    except Exception as e:
        print(f"!!! Erreur lors du login : {e}")
        return None

class MinesweeperSmartSolver:
    def __init__(self):
        self.session = get_fresh_session()
        if not self.session:
            # get_fresh_session already prints the specific error
            print("FAILED to initialize session. See log above for details.")
            exit(1)

        # État du jeu
        self.game_id = None
        self.rows = 0
        self.cols = 0
        self.grid = {}  # (r, c) -> dict
        self.game_over = False
        self.won = False
        
        # Stats
        self.wins = 0
        self.losses = 0
        self.games_played = 0

    def _api_call(self, endpoint, payload=None):
        """Wrapper générique pour les appels API"""
        url = f"{API_URL}/{endpoint}"
        try:
            if payload:
                r = self.session.post(url, json=payload)
            else:
                r = self.session.post(url)
            
            if r.status_code == 200:
                return r.json()
            
            # Si token expiré, on tente de se reconnecter une fois
            if r.status_code == 401:
                # Silencieux pour l'affichage
                self.session = get_fresh_session()
                if self.session:
                    # Retry
                    if payload:
                        r = self.session.post(url, json=payload)
                    else:
                        r = self.session.post(url)
                    if r.status_code == 200:
                        return r.json()

            # print(f"⚠️ Erreur API {endpoint}: {r.status_code} - {r.text}")
        except Exception as e:
            pass # print(f"⚠️ Exception API {endpoint}: {e}")
        return None

    def update_grid(self, data):
        """Met à jour la grille locale avec les données du serveur"""
        if not data: return
        self.game_id = data.get("game_id", self.game_id)
        self.rows = data.get("rows", self.rows)
        self.cols = data.get("cols", self.cols)
        self.game_over = data.get("game_over", False)
        self.won = data.get("won", False)
        
        # Mise à jour des cellules
        for cell in data.get("cells", []):
            self.grid[(cell['row'], cell['col'])] = cell

    def get_neighbors(self, r, c):
        """Récupère les coordonnées des voisins"""
        nbs = []
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0: continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    nbs.append((nr, nc))
        return nbs

    def get_cell_info(self, r, c):
        """Retourne (valeur, [voisins_flagged], [voisins_hidden])"""
        cell = self.grid.get((r, c))
        if not cell: return None, [], []
        
        nbs = self.get_neighbors(r, c)
        flagged = []
        hidden = []
        
        for nr, nc in nbs:
            n_cell = self.grid.get((nr, nc))
            if not n_cell: continue # Ne devrait pas arriver si la grille est init
            if n_cell['flagged']:
                flagged.append((nr, nc))
            elif not n_cell['revealed']:
                hidden.append((nr, nc))
                
        return cell['value'], flagged, hidden

    def action_reveal(self, r, c):
        # print(f"🔍 Reveal ({r}, {c})")
        data = self._api_call(f"{self.game_id}/reveal", {"row": r, "col": c})
        if data: self.update_grid(data)
        return bool(data)

    def action_flag(self, r, c):
        # print(f"🚩 Flag ({r}, {c})")
        data = self._api_call(f"{self.game_id}/flag", {"row": r, "col": c})
        if data: self.update_grid(data)
        return bool(data)

    def solve_step(self):
        """Une itération de résolution"""
        moves = set() # Pour éviter les doublons dans une passe
        
        # 1. Identifier la "frontière" : cases révélées avec >0 voisins cachés
        frontier = []
        for coords, cell in self.grid.items():
            if cell['revealed'] and cell['value'] and cell['value'] > 0:
                _, _, hidden = self.get_cell_info(cell['row'], cell['col'])
                if hidden:
                    frontier.append(coords)

        if not frontier:
            return False

        # --- ÉTAPE 1 : Logique Triviale ---
        # Si Flagged == Value -> Reste Safe
        # Si Hidden + Flagged == Value -> Reste Mines
        for r, c in frontier:
            val, flagged, hidden = self.get_cell_info(r, c)
            
            # Tout le reste est safe
            if len(flagged) == val:
                for hr, hc in hidden:
                    moves.add(('reveal', hr, hc))
            
            # Tout le reste est des mines
            elif len(hidden) + len(flagged) == val:
                for hr, hc in hidden:
                    moves.add(('flag', hr, hc))

        if moves:
            return self.execute_batch(moves)

        # --- ÉTAPE 2 : Logique des Ensembles (Subsets) ---
        # Comparer deux cases de la frontière qui partagent des voisins
        # Si Voisins(A) est sous-ensemble de Voisins(B), on peut déduire des infos sur B-A
        
        # On limite la recherche pour la performance (voisins de voisins)
        processed_pairs = set()
        
        for r1, c1 in frontier:
            val1, flag1, hidden1 = self.get_cell_info(r1, c1)
            eff_val1 = val1 - len(flag1) # Mines restantes à trouver
            set1 = set(hidden1)
            
            # Chercher des voisins dans la frontière
            neighbors_of_1 = self.get_neighbors(r1, c1)
            frontier_neighbors = [n for n in neighbors_of_1 if n in frontier] # Optimisation
            
            for r2, c2 in frontier: # Comparaison bruteforce sur la frontière (peut être optimisé par proximité)
                if (r1, c1) == (r2, c2): continue
                
                # Optimisation: ne comparer que si proches (distance < 3 cases)
                if abs(r1-r2) > 2 or abs(c1-c2) > 2: continue

                pair_sig = tuple(sorted(((r1,c1), (r2,c2))))
                if pair_sig in processed_pairs: continue
                processed_pairs.add(pair_sig)

                val2, flag2, hidden2 = self.get_cell_info(r2, c2)
                eff_val2 = val2 - len(flag2)
                set2 = set(hidden2)

                # Cas A: Set1 est un sous-ensemble de Set2
                if set1.issubset(set2):
                    diff = set2 - set1
                    diff_val = eff_val2 - eff_val1
                    
                    if len(diff) > 0:
                        # Si le nombre de mines dans la différence est 0 -> TOUT SAFE
                        if diff_val == 0:
                            # print(f"💡 Logique Ensemble: ({r1},{c1}) ⊂ ({r2},{c2}) => Diff safe")
                            for dr, dc in diff: moves.add(('reveal', dr, dc))
                        
                        # Si le nombre de mines == taille diff -> TOUT MINES
                        elif diff_val == len(diff):
                            # print(f"💡 Logique Ensemble: ({r1},{c1}) ⊂ ({r2},{c2}) => Diff mines")
                            for dr, dc in diff: moves.add(('flag', dr, dc))

                # Cas B: Set2 est un sous-ensemble de Set1 (inverse)
                elif set2.issubset(set1):
                    diff = set1 - set2
                    diff_val = eff_val1 - eff_val2
                    
                    if len(diff) > 0:
                        if diff_val == 0:
                            # print(f"💡 Logique Ensemble: ({r2},{c2}) ⊂ ({r1},{c1}) => Diff safe")
                            for dr, dc in diff: moves.add(('reveal', dr, dc))
                        elif diff_val == len(diff):
                            # print(f"💡 Logique Ensemble: ({r2},{c2}) ⊂ ({r1},{c1}) => Diff mines")
                            for dr, dc in diff: moves.add(('flag', dr, dc))

        if moves:
            return self.execute_batch(moves)
            
        return False

    def execute_batch(self, moves):
        """Exécute les mouvements trouvés. S'arrête si Game Over."""
        did_something = False
        # On trie pour prioriser les reveals (donnent de l'info)
        sorted_moves = sorted(list(moves), key=lambda x: x[0], reverse=True) 
        
        for action, r, c in sorted_moves:
            if self.game_over: break
            
            # Vérifier que l'état n'a pas changé entre temps (ex: déjà révélé)
            cell = self.grid.get((r, c))
            if not cell: continue
            if action == 'reveal' and cell['revealed']: continue
            if action == 'flag' and cell['flagged']: continue
            
            if action == 'reveal':
                self.action_reveal(r, c)
            else:
                self.action_flag(r, c)
            did_something = True
            
        return did_something

    def guess(self):
        """Devinette : préférer les coins ou aléatoire"""
        hidden = [k for k, v in self.grid.items() if not v['revealed'] and not v['flagged']]
        if not hidden: return False
        
        # Priorité aux coins si non révélés (souvent plus sûrs ou ouvrent le jeu)
        corners = [(0,0), (0, self.cols-1), (self.rows-1, 0), (self.rows-1, self.cols-1)]
        valid_corners = [c for c in corners if c in self.grid and not self.grid[c]['revealed']]
        
        if valid_corners:
            choice = random.choice(valid_corners)
            # print(f"🎲 Guess (Corner): {choice}")
        else:
            choice = random.choice(hidden)
            # print(f"🎲 Guess (Random): {choice}")
            
        return self.action_reveal(choice[0], choice[1])

    def print_status(self):
        """Affiche l'état sur une seule ligne."""
        status = "En cours..."
        if self.game_over:
            status = "VICTOIRE" if self.won else "PERDU"
        
        line = f"\r[Wins: {self.wins} | Losses: {self.losses} | Total: {self.games_played}] Game: {self.game_id} | {status}      "
        print(line, end="", flush=True)

    def start(self):
        print("--- Demarrage du solver intelligent (Mode Silence)...")
        print("Stats affichees en temps reel :")
        
        while True:
            self.games_played += 1
            # Nouvelle partie
            data = self._api_call("new-game", {})
            if not data:
                time.sleep(5)
                continue
            
            self.grid = {}
            self.update_grid(data)
            self.print_status()
            
            # Premier coup au centre
            mid_r, mid_c = self.rows // 2, self.cols // 2
            self.action_reveal(mid_r, mid_c)
            self.print_status()

            # Boucle de résolution
            while not self.game_over:
                if not self.solve_step():
                    if not self.guess():
                        break # Plus rien à faire
                self.print_status()
            
            if self.won:
                self.wins += 1
            else:
                self.losses += 1
            
            self.print_status()
            
            if os.environ.get("SOLVE_ONCE") == "1":
                print("\nSOLVE_ONCE set, exiting.")
                break

if __name__ == "__main__":
    solver = MinesweeperSmartSolver()
    try:
        solver.start()
    except KeyboardInterrupt:
        print("\n🛑 Arrêt demandé.")