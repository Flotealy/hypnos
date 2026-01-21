import os
import requests
import time
import random
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

API_URL = "https://play.hypnos2026.fr/api/arg/minesweeper"

class MinesweeperSmartSolver:
    def __init__(self):
        self.auth_token = os.getenv("AUTH_TOKEN")
        self.csrf_token = os.getenv("CSRF_TOKEN")
        
        if not self.auth_token or not self.csrf_token:
            print("❌ Erreur : AUTH_TOKEN ou CSRF_TOKEN manquants (.env)")
            exit(1)

        self.session = requests.Session()
        self._configure_headers()

        # État du jeu
        self.game_id = None
        self.rows = 0
        self.cols = 0
        self.grid = {}  # (r, c) -> dict
        self.game_over = False
        self.won = False
        self.mines_remaining_counter = 0

    def _configure_headers(self):
        self.session.headers.update({
            'accept': 'application/json',
            'content-type': 'application/json',
            'origin': 'https://play.hypnos2026.fr',
            'referer': 'https://play.hypnos2026.fr/game/minesweeper/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/143.0.0.0 Safari/537.36',
            'x-csrf-token': self.csrf_token
        })
        self.session.cookies.set('auth_token', self.auth_token)
        self.session.cookies.set('csrf_token', self.csrf_token)

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
            print(f"⚠️ Erreur API {endpoint}: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"⚠️ Exception API {endpoint}: {e}")
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
        print(f"🔍 Reveal ({r}, {c})")
        data = self._api_call(f"{self.game_id}/reveal", {"row": r, "col": c})
        if data: self.update_grid(data)
        return bool(data)

    def action_flag(self, r, c):
        print(f"🚩 Flag ({r}, {c})")
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
                            print(f"💡 Logique Ensemble: ({r1},{c1}) ⊂ ({r2},{c2}) => Diff safe")
                            for dr, dc in diff: moves.add(('reveal', dr, dc))
                        
                        # Si le nombre de mines == taille diff -> TOUT MINES
                        elif diff_val == len(diff):
                            print(f"💡 Logique Ensemble: ({r1},{c1}) ⊂ ({r2},{c2}) => Diff mines")
                            for dr, dc in diff: moves.add(('flag', dr, dc))

                # Cas B: Set2 est un sous-ensemble de Set1 (inverse)
                elif set2.issubset(set1):
                    diff = set1 - set2
                    diff_val = eff_val1 - eff_val2
                    
                    if len(diff) > 0:
                        if diff_val == 0:
                            print(f"💡 Logique Ensemble: ({r2},{c2}) ⊂ ({r1},{c1}) => Diff safe")
                            for dr, dc in diff: moves.add(('reveal', dr, dc))
                        elif diff_val == len(diff):
                            print(f"💡 Logique Ensemble: ({r2},{c2}) ⊂ ({r1},{c1}) => Diff mines")
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
            print(f"🎲 Guess (Corner): {choice}")
        else:
            choice = random.choice(hidden)
            print(f"🎲 Guess (Random): {choice}")
            
        return self.action_reveal(choice[0], choice[1])

    def start(self):
        print("🚀 Démarrage du solver intelligent...")
        while True:
            # Nouvelle partie
            data = self._api_call("new-game", {})
            if not data:
                time.sleep(5)
                continue
            
            self.grid = {}
            self.update_grid(data)
            print(f"🎮 Partie {self.game_id} ({self.rows}x{self.cols})")
            
            # Premier coup au centre
            mid_r, mid_c = self.rows // 2, self.cols // 2
            self.action_reveal(mid_r, mid_c)

            # Boucle de résolution
            while not self.game_over:
                if not self.solve_step():
                    print("🤔 Bloqué. Tentative de guess...")
                    if not self.guess():
                        break # Plus rien à faire
            
            if self.won:
                print("🏆 VICTOIRE !")
            else:
                print("💥 PERDU")
            
            time.sleep(2)

if __name__ == "__main__":
    solver = MinesweeperSmartSolver()
    try:
        solver.start()
    except KeyboardInterrupt:
        print("\n🛑 Arrêt demandé.")