import cv2
import numpy as np
import pyautogui
import time
import ctypes
import mss
import json
import os
from hypnos.lib import setup_logger

logger = setup_logger("breakout_solver")

from importlib import resources
DATA_PATH = resources.files("hypnos.breakout.data")
CONFIG_FILE = DATA_PATH / "config.json"
BALL_FILE = DATA_PATH / "ball.png"

# Touche pour quitter : 'q' (0x51)
VK_Q = 0x51
# Touche pour pause/reprise : 'p' (0x50)
VK_P = 0x50
# Touche pour debug (affichage vision) : 'd' (0x44)
VK_D = 0x44

def is_key_pressed(key_code):
    """Vérifie si une touche est pressée via l'API Windows (sans focus nécessaire)."""
    return ctypes.windll.user32.GetAsyncKeyState(key_code) & 0x8000

def main() -> None:
    logger.info("=== Casse-Brique Bot (v3 - MSS Speed) ===")
    logger.info("Contrôles :")
    logger.info("  [P] : PAUSE / REPRENDRE")
    logger.info("  [D] : Activer/Désactiver le mode VISION (Ralentit le bot !)")
    logger.info("  [Q] : QUITTER")
    
    # Vérification fichiers
    config_exists = CONFIG_FILE.exists()
    ball_exists = BALL_FILE.exists()

    # --- 1. CONFIGURATION ZONE ---
    reconfig_zone = True
    if config_exists:
        logger.info("\nUne configuration de ZONE a été trouvée.")
        if input("Voulez-vous reconfigurer la ZONE ? (o/N) : ").strip().lower() == 'o':
            reconfig_zone = True
        else:
            reconfig_zone = False

    if reconfig_zone:
        logger.info("\n--- 1/2 : CONFIGURATION DE LA ZONE DE JEU ---")
        logger.info("Préparez le jeu. Capture dans 10 secondes...")
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
            logger.error("Sélection invalide. Arrêt.")
            return
            
        with open(CONFIG_FILE, "w") as f:
            json.dump({"x": int(x), "y": int(y), "w": int(w), "h": int(h)}, f)
        logger.info("Zone sauvegardée.")
    else:
    else:
        logger.info("Chargement de la configuration de zone...")
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            x, y, w, h = data["x"], data["y"], data["w"], data["h"]
        logger.info(f"Zone chargée : {x},{y},{w},{h}")

    # --- 2. CONFIGURATION BALLE ---
    reconfig_ball = True
    if ball_exists:
        logger.info("\nUne configuration de BALLE a été trouvée.")
        if input("Voulez-vous reconfigurer la BALLE ? (o/N) : ").strip().lower() == 'o':
            reconfig_ball = True
        else:
            reconfig_ball = False

    if reconfig_ball:
        logger.info("\n--- 2/2 : CONFIGURATION DE LA BALLE ---")
        logger.info("Préparez la balle visible (pause). Capture dans 5 secondes...")
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
            cv2.imwrite(str(BALL_FILE), ball_img)
            logger.info("Image de la balle sauvegardée.")
        else:
            print("Sélection balle invalide.")
            return

    # --- Configuration MSS pour la capture ultra-rapide ---
    monitor = {"top": int(y), "left": int(x), "width": int(w), "height": int(h)}
    sct = mss.mss()

    # 3. Chargement du template
    try:
        # On charge en couleur
        ball_template = cv2.imread(str(BALL_FILE), cv2.IMREAD_COLOR)
        if ball_template is None:
            raise FileNotFoundError(f"{BALL_FILE} introuvable ou illisible.")
    except Exception as e:
        logger.error(f"Erreur : {e}")
        return

    # Dimensions du template
    ball_h, ball_w = ball_template.shape[:2]
    
    # --- OPTIMISATION CRITIQUE ---
    # Par défaut, pyautogui attend 0.1s après chaque commande. On le désactive.
    pyautogui.PAUSE = 0
    pyautogui.MINIMUM_DURATION = 0
    
    # Préparation du template en Gris pour accélérer le matching (3x moins de données)
    ball_template_gray = cv2.cvtColor(ball_template, cv2.COLOR_BGR2GRAY)

    logger.info("\n--> BOT PRÊT. Mode PRO (Prediction + Anti-Teleport). En PAUSE (Appuyez sur P).")
    
    paused = True 
    debug_mode = False
    
    # Variables pour la physique
    prev_x = None
    max_jump_dist = w * 0.3 # Si mouvement > 30% de la largeur en 1 frame -> Erreur
    prediction_factor = 2.5 # Nombre de "frames" à anticiper (Ajuster si ça overshoot)

    while True:
        # --- Gestion des touches ---
        if is_key_pressed(VK_Q):
            logger.info("\nArrêt demandé.")
            break
        
        if is_key_pressed(VK_P):
            paused = not paused
            logger.info(f"\n[MODE] : {'PAUSE' if paused else 'ACTIF'}")
            time.sleep(0.5)

        if is_key_pressed(VK_D):
            debug_mode = not debug_mode
            logger.info(f"\n[DEBUG] : {'ACTIVÉ (Lent)' if debug_mode else 'DÉSACTIVÉ (Rapide)'}")
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
    logger.info("\nFin du programme.")

if __name__ == "__main__":
    main()
