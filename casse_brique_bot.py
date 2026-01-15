import cv2
import numpy as np
import pyautogui
import time
import ctypes
import mss
import json
import os

# --- Configuration ---
# Touche pour quitter : 'q' (0x51)
VK_Q = 0x51
# Touche pour pause/reprise : 'p' (0x50)
VK_P = 0x50
# Touche pour debug (affichage vision) : 'd' (0x44)
VK_D = 0x44

def is_key_pressed(key_code):
    """Vérifie si une touche est pressée via l'API Windows (sans focus nécessaire)."""
    return ctypes.windll.user32.GetAsyncKeyState(key_code) & 0x8000

def casse_brique_bot():
    print("=== Casse-Brique Bot (v3 - MSS Speed) ===")
    print("Contrôles :")
    print("  [P] : PAUSE / REPRENDRE")
    print("  [D] : Activer/Désactiver le mode VISION (Ralentit le bot !)")
    print("  [Q] : QUITTER")
    
    CONFIG_FILE = "config.json"
    
    # Vérification si une config existe déjà
    config_exists = os.path.exists(CONFIG_FILE) and os.path.exists("ball.png")
    reconfig = True # Par défaut, on configure
    
    if config_exists:
        print("\nUne configuration (Zone + Balle) a été trouvée.")
        choix = input("Voulez-vous REFAIRE la configuration ? (o/N) : ").strip().lower()
        if choix != 'o':
            reconfig = False

    if reconfig:
        # --- 1. CONFIGURATION ZONE ---
        print("\n--- 1/2 : CONFIGURATION DE LA ZONE DE JEU ---")
        print("Préparez le jeu. Capture dans 10 secondes...")
        for i in range(10, 0, -1):
            print(f"{i}...", end=" ", flush=True)
            time.sleep(1)
        print("\nCapture !")

        screen = pyautogui.screenshot()
        screen_bgr = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)
        
        cv2.namedWindow("Selectionne la zone de jeu", cv2.WINDOW_NORMAL)
        cv2.setWindowProperty("Selectionne la zone de jeu", cv2.WND_PROP_TOPMOST, 1)
        roi = cv2.selectROI("Selectionne la zone de jeu", screen_bgr, showCrosshair=True, fromCenter=False)
        cv2.destroyWindow("Selectionne la zone de jeu")
        
        x, y, w, h = roi
        if w == 0 or h == 0:
            print("Sélection invalide. Arrêt.")
            return
            
        # Sauvegarde JSON
        with open(CONFIG_FILE, "w") as f:
            json.dump({"x": int(x), "y": int(y), "w": int(w), "h": int(h)}, f)
        print("Zone sauvegardée.")

        # --- 2. CONFIGURATION BALLE ---
        print("\n--- 2/2 : CONFIGURATION DE LA BALLE ---")
        print("Préparez la balle visible (pause). Capture dans 5 secondes...")
        for i in range(5, 0, -1):
            print(f"{i}...", end=" ", flush=True)
            time.sleep(1)
            
        screen_ball_bgr = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
        
        cv2.namedWindow("Entourez JUSTE la balle", cv2.WINDOW_NORMAL)
        cv2.setWindowProperty("Entourez JUSTE la balle", cv2.WND_PROP_TOPMOST, 1)
        ball_roi = cv2.selectROI("Entourez JUSTE la balle", screen_ball_bgr, showCrosshair=True, fromCenter=False)
        cv2.destroyWindow("Entourez JUSTE la balle")
        
        bx, by, bw, bh = ball_roi
        if bw > 0 and bh > 0:
            ball_img = screen_ball_bgr[by:by+bh, bx:bx+bw]
            cv2.imwrite("ball.png", ball_img)
            print("Image de la balle sauvegardée.")
        else:
            print("Sélection balle invalide.")
            return
            
    else:
        # Chargement de la config existante
        print("Chargement de la configuration...")
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            x, y, w, h = data["x"], data["y"], data["w"], data["h"]
        print(f"Zone chargée : {x},{y},{w},{h}")

    # --- Configuration MSS pour la capture ultra-rapide ---
    monitor = {"top": int(y), "left": int(x), "width": int(w), "height": int(h)}
    sct = mss.mss()

    # 3. Chargement du template
    try:
        # On charge en couleur
        ball_template = cv2.imread("ball.png", cv2.IMREAD_COLOR)
        if ball_template is None:
            raise FileNotFoundError("ball.png introuvable ou illisible.")
    except Exception as e:
        print(f"Erreur : {e}")
        return

    # --- Configuration MSS pour la capture ultra-rapide ---
    monitor = {"top": int(y), "left": int(x), "width": int(w), "height": int(h)}
    sct = mss.mss()
    
    # Dimensions du template
    ball_h, ball_w = ball_template.shape[:2]
    
    # --- OPTIMISATION CRITIQUE ---
    # Par défaut, pyautogui attend 0.1s après chaque commande. On le désactive.
    pyautogui.PAUSE = 0
    pyautogui.MINIMUM_DURATION = 0
    
    # Préparation du template en Gris pour accélérer le matching (3x moins de données)
    ball_template_gray = cv2.cvtColor(ball_template, cv2.COLOR_BGR2GRAY)

    print("\n--> BOT PRÊT. Mode PRO (Prediction + Anti-Teleport).")
    
    paused = False 
    debug_mode = False
    
    # Variables pour la physique
    prev_x = None
    max_jump_dist = w * 0.3 # Si mouvement > 30% de la largeur en 1 frame -> Erreur
    prediction_factor = 2.5 # Nombre de "frames" à anticiper (Ajuster si ça overshoot)

    while True:
        # --- Gestion des touches ---
        if is_key_pressed(VK_Q):
            print("\nArrêt demandé.")
            break
        
        if is_key_pressed(VK_P):
            paused = not paused
            print(f"\n[MODE] : {'PAUSE' if paused else 'ACTIF'}")
            time.sleep(0.5)

        if is_key_pressed(VK_D):
            debug_mode = not debug_mode
            print(f"\n[DEBUG] : {'ACTIVÉ (Lent)' if debug_mode else 'DÉSACTIVÉ (Rapide)'}")
            if not debug_mode:
                cv2.destroyAllWindows()
            time.sleep(0.5)

        if paused:
            time.sleep(0.01)
            continue

        # --- Logique du bot (Boucle Optimisée) ---
        
        # 1. Capture ultra-rapide avec MSS
        img_mss = sct.grab(monitor)
        frame = np.array(img_mss)
        
        # 2. Conversion N&B direct pour la vitesse (mss donne du BGRA)
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
        
        # 3. Recherche
        res = cv2.matchTemplate(frame_gray, ball_template_gray, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        
        # --- Affichage Debug (Optionnel) ---
        if debug_mode:
            print(f"\rConfidence: {max_val:.2f}   ", end="")
            debug_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            if max_val > 0.4:
                top_left = max_loc
                bottom_right = (top_left[0] + ball_w, top_left[1] + ball_h)
                cv2.rectangle(debug_frame, top_left, bottom_right, (0, 0, 255), 2)
            cv2.imshow("Vision Bot", debug_frame)
            cv2.waitKey(1)

        # 4. Action Physique
        if max_val > 0.60:
            ball_x_in_roi = max_loc[0] + ball_w // 2
            current_x = x + ball_x_in_roi
            
            # --- Système Anti-Teleport & Prédiction ---
            if prev_x is None:
                prev_x = current_x
            
            # Calcul du déplacement intantané
            delta_x = current_x - prev_x
            
            # FILTRE : Si le déplacement est absurde (téléportation > 30% écran), on ignore
            # C'est souvent une frame buggée ou une autre balle détectée ailleurs
            if abs(delta_x) < max_jump_dist:
                
                # PREDICTION : On vise là où la balle sera, pas là où elle est
                # Formule : Position + Vitesse * Facteur
                predicted_target = current_x + (delta_x * prediction_factor)
                
                # Clamp pour ne pas sortir de l'écran
                target_x = max(x, min(x + w, predicted_target))
                paddle_y = y + h - 10
                
                # MOUVEMENT SYSTEME (Plus rapide que PyAutoGUI)
                # ctypes permet d'envoyer l'event souris directement au niveau OS
                ctypes.windll.user32.SetCursorPos(int(target_x), int(paddle_y))
                
                # Mise à jour pour la prochaine frame
                prev_x = current_x
            else:
                # Si saut trop grand, on reset pas le prev_x (on considère ce point comme bruit)
                pass 
                
    cv2.destroyAllWindows()
    print("\nFin du programme.")

if __name__ == "__main__":
    casse_brique_bot()
