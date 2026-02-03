import websocket
import requests
import struct
import time
import math
import logging
import threading
import json
import sys
import os

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("agario_bot")

# Configuration
BASE_URL = 'https://play.hypnos2026.fr'
LOGIN_URL = f'{BASE_URL}/api/auth/login'
WS_URL = 'wss://play.hypnos2026.fr/hypnosio-ws'

EMAIL = os.environ.get("EMAIL")
PASSWORD = os.environ.get("PASSWORD")

if not EMAIL or not PASSWORD:
    raise ValueError("EMAIL and PASSWORD environment variables must be set.")

# Game State
nodes = {}
my_node_ids = []
border = {'minx': -2000, 'miny': -2000, 'maxx': 2000, 'maxy': 2000}
running = True
last_death_time = 0
last_disconnect_reason = ""
conflict_detected = False

def get_authenticated_session():
    session = requests.Session()
    session.headers.update({
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'accept': 'application/json',
        'origin': BASE_URL,
        'referer': f'{BASE_URL}/login'
    })

    logger.info("Retrieving CSRF token...")
    try:
        r = session.get(f'{BASE_URL}/api/csrf-token', timeout=10)
        if r.status_code == 429:
            logger.error("Rate limit hit (CSRF). Waiting 65s...")
            time.sleep(65)
            return None
        csrf_token = r.json().get('csrf_token') if r.ok else session.cookies.get('csrf_token')
        if csrf_token:
            session.headers.update({'x-csrf-token': csrf_token})
    except Exception as e:
        logger.error(f"Error getting CSRF: {e}")

    logger.info(f"Logging in as {EMAIL}...")
    try:
        r = session.post(LOGIN_URL, json={"login": EMAIL, "password": PASSWORD}, timeout=10)
        if r.status_code == 429:
            logger.error("Rate limit hit (Login). Waiting 65s...")
            time.sleep(65)
            return None
        if r.ok:
            logger.info("Login successful.")
            return session
    except Exception as e:
        logger.error(f"Login error: {e}")
    return None

class BinaryReader:
    def __init__(self, data):
        self.data = data
        self.offset = 0
    def read_uint8(self):
        if self.offset + 1 > len(self.data): return 0
        val = self.data[self.offset]; self.offset += 1
        return val
    def read_uint16(self):
        if self.offset + 2 > len(self.data): return 0
        val = struct.unpack_from('<H', self.data, self.offset)[0]; self.offset += 2
        return val
    def read_uint32(self):
        if self.offset + 4 > len(self.data): return 0
        val = struct.unpack_from('<I', self.data, self.offset)[0]; self.offset += 4
        return val
    def read_int32(self):
        if self.offset + 4 > len(self.data): return 0
        val = struct.unpack_from('<i', self.data, self.offset)[0]; self.offset += 4
        return val
    def read_float64(self):
        if self.offset + 8 > len(self.data): return 0.0
        val = struct.unpack_from('<d', self.data, self.offset)[0]; self.offset += 8
        return val
    def read_string_utf8(self):
        end = self.data.find(b'\x00', self.offset)
        if end == -1: return ""
        try: s = self.data[self.offset:end].decode('utf-8')
        except: s = self.data[self.offset:end].decode('latin-1', errors='ignore')
        self.offset = end + 1
        return s

def on_message(ws, message):
    try:
        if isinstance(message, bytes):
            reader = BinaryReader(message)
            packet_id = reader.read_uint8()
            if packet_id == 0x10:
                update_nodes(reader)
            elif packet_id == 0x20:
                node_id = reader.read_uint32()
                if node_id not in my_node_ids:
                    my_node_ids.append(node_id)
            elif packet_id == 0x40:
                border['minx'] = reader.read_float64()
                border['miny'] = reader.read_float64()
                border['maxx'] = reader.read_float64()
                border['maxy'] = reader.read_float64()
                logger.info(f"Border synced: {border}")
    except: pass

def update_nodes(reader):
    global last_death_time
    count = reader.read_uint16()
    for _ in range(count):
        reader.read_uint32() # killer
        killed = reader.read_uint32()
        if killed in nodes: del nodes[killed]
        if killed in my_node_ids:
            my_node_ids.remove(killed)
            if not my_node_ids:
                logger.info("Cell eaten. Entering 3s respawn cooldown...")
                last_death_time = time.time()

    while True:
        node_id = reader.read_uint32()
        if node_id == 0: break
        x, y, size = reader.read_int32(), reader.read_int32(), reader.read_uint16()
        flags = reader.read_uint8()
        if bool(flags & 0x02): reader.offset += 3 # color
        if bool(flags & 0x04): reader.read_string_utf8() # skin
        if bool(flags & 0x08): reader.read_string_utf8() # name
        nodes[node_id] = {'x': x, 'y': y, 'size': size, 'is_virus': bool(flags & 0x01)}

    count = reader.read_uint16()
    for _ in range(count):
        node_id = reader.read_uint32()
        if node_id in nodes: del nodes[node_id]

def send_play(ws):
    if time.time() - last_death_time < 3: return
    logger.info("Spawning...")
    ws.send(struct.pack('<B', 0) + "HypnosBot".encode('utf-8') + b'\x00', opcode=websocket.ABNF.OPCODE_BINARY)

def send_move(ws, x, y):
    ws.send(struct.pack('<BII', 0x10, int(x), int(y)) + b'\x00\x00\x00\x00', opcode=websocket.ABNF.OPCODE_BINARY)

def bot_loop(ws):
    last_log_time = 0
    while running:
        if not my_node_ids:
            if ws.sock and ws.sock.connected: send_play(ws)
            time.sleep(1); continue
        
        my_x = my_y = my_mass = 0
        my_cells = []
        for nid in my_node_ids:
            if nid in nodes:
                n = nodes[nid]
                my_x += n['x']; my_y += n['y']; my_mass += n['size']**2/100
                my_cells.append(n)
        
        if not my_cells: time.sleep(0.1); continue
        my_x /= len(my_cells); my_y /= len(my_cells); my_size = math.sqrt(my_mass * 100)

        if time.time() - last_log_time > 5:
            logger.info(f"STATUS: Mass={int(my_mass)} | Pos=({int(my_x)}, {int(my_y)})")
            last_log_time = time.time()

        best_target = None; best_score = -float('inf')
        threat_x = threat_y = threat_count = 0

        for nid, node in nodes.items():
            if nid in my_node_ids: continue
            dist = math.sqrt((node['x'] - my_x)**2 + (node['y'] - my_y)**2)
            if dist > 2000: continue
            if node['size'] > my_size * 1.15 or (node['is_virus'] and my_size > node['size'] * 1.15):
                threat_x -= (node['x'] - my_x) / (dist + 1) * 2000
                threat_y -= (node['y'] - my_y) / (dist + 1) * 2000
                threat_count += 1
            elif node['size'] * 1.15 < my_size or node['size'] < 25:
                score = (node['size']**2) / (dist**2 + 1)
                if node['size'] > 20: score *= 10
                if score > best_score: best_score = score; best_target = node
        
        tx, ty = (my_x+threat_x, my_y+threat_y) if threat_count > 0 else (best_target['x'], best_target['y']) if best_target else ((border['minx']+border['maxx'])/2, (border['miny']+border['maxy'])/2)
        send_move(ws, max(border['minx'], min(border['maxx'], tx)), max(border['miny'], min(border['maxy'], ty)))
        time.sleep(0.05)

def on_error(ws, error):
    global last_disconnect_reason; last_disconnect_reason = str(error)
    logger.error(f"WS Error: {error}")

def on_close(ws, close_status_code, close_msg):
    global running, conflict_detected
    msg = str(close_msg) or last_disconnect_reason
    logger.info(f"WS Closed: {msg}")
    if "New session started" in msg: conflict_detected = True
    running = False

def on_open(ws):
    global running, conflict_detected
    running = True; conflict_detected = False
    logger.info("WS Connected")
    ws.send(struct.pack('<BI', 254, 6), opcode=websocket.ABNF.OPCODE_BINARY)
    ws.send(struct.pack('<BI', 255, 1), opcode=websocket.ABNF.OPCODE_BINARY)
    send_play(ws)
    threading.Thread(target=bot_loop, args=(ws,), daemon=True).start()

def main():
    session = None
    while True:
        if session is None:
            session = get_authenticated_session()
            if not session: time.sleep(10); continue

        cookie_str = "; ".join([f"{k}={v}" for k, v in session.cookies.get_dict().items()])
        headers = {
            'Origin': BASE_URL, 'Cookie': cookie_str, 'Cache-Control': 'no-cache',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        logger.info(f"Connecting to {WS_URL}...")
        try:
            ws = websocket.WebSocketApp(WS_URL, on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close, header=headers)
            ws.run_forever()
        except KeyboardInterrupt: logger.info("Stopping..."); break
        except Exception as e: logger.error(f"Connect error: {e}")
        
        wait_time = 15 if conflict_detected else 5
        if conflict_detected: logger.warning(f"Conflict! Waiting {wait_time}s to allow ghost session to die...")
        time.sleep(wait_time)

if __name__ == "__main__":
    main()
