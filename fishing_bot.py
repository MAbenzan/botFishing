import time
import json
import random
import os
import sys
import warnings
import mss
import numpy as np
import cv2
import pyautogui
import easyocr

# Suprimir advertencia de torch sobre pin_memory (no afecta al funcionamiento)
warnings.filterwarnings("ignore", category=UserWarning, message=".*pin_memory.*")

# Configuración global
CONFIG_FILE = 'config_fishing.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

CONFIG = load_config()

class FishingBrain:
    def __init__(self):
        self.fish_data = {}
        self.history = ""
        self.possible_fish = []
        self.load_data()

    def load_data(self):
        if os.path.exists('fish_data.json'):
            try:
                with open('fish_data.json', 'r', encoding='utf-8') as f:
                    self.fish_data = json.load(f)
            except Exception as e:
                print(f"Error cargando fish_data.json: {e}")

    def reset(self):
        self.history = ""
        self.possible_fish = self.fish_data.get('fish_sequences', [])

    def register_key(self, key):
        self.history += key
        self.filter_fish()

    def register_wrong_key(self, key):
        pass

    def filter_fish(self):
        if not self.possible_fish:
            return
        new_possible = []
        for fish in self.possible_fish:
            seq = fish.get('sequence', '').lower()
            if seq.startswith(self.history):
                new_possible.append(fish)
        self.possible_fish = new_possible

    def predict_next_key(self):
        if not CONFIG.get('use_prediction', False):
            return None
        if not self.possible_fish:
            return None
        
        next_chars = set()
        idx = len(self.history)
        for fish in self.possible_fish:
            seq = fish.get('sequence', '').lower()
            if idx < len(seq):
                next_chars.add(seq[idx])
        
        if len(next_chars) == 1:
            return list(next_chars)[0]
        return None

class FishingBot:
    def __init__(self):
        self.sct = mss.mss()
        self.load_settings()
        self.running = True
        self.brain = FishingBrain()
        
        # Estado de sesión
        self.session_start_time = None
        self.last_detection_time = None
        self.last_press_time = None
        self.awaiting_completion = False
        self.menu_absent_since = None
        self.last_state = None
        self.last_pressed_key = None
        self.sequence_fallback_done = False
        
        # Flags y tiempos de detección
        self.pressed_flags = {'e': False, 'r': False, 't': False, 'wait_red': False}
        self.detect_times = {'e': None, 'r': None, 't': None, 'wait_red': None}
        self.letter_red_registered = {'e': False, 'r': False, 't': False}
        
        # Control de reinicio
        self.next_session_delay_until = None
        self.session_start_timeout = CONFIG.get('start_wait_timeout_seconds', 5)
        
        # Inicializar OCR
        print("Cargando modelo OCR... (puede tardar un poco)")
        self.reader = easyocr.Reader(['es', 'en'], gpu=False)
        print("Modelo OCR cargado.")

    def load_settings(self):
        global CONFIG
        CONFIG = load_config()
        capture = CONFIG.get('capture_region', {})
        self.monitor = {
            "top": capture.get('top', 0),
            "left": capture.get('left', 0),
            "width": capture.get('width', 1920),
            "height": capture.get('height', 1080)
        }
        self.areas = CONFIG.get('areas', {})
        self.thresh = CONFIG.get('thresholds', {})

    def process_region(self, img, region_name):
        area = self.areas.get(region_name)
        if not area:
            return 0, 0, 0
        x, y, w, h = area['x'], area['y'], area['w'], area['h']
        if y+h > img.shape[0] or x+w > img.shape[1]:
            return 0, 0, 0
            
        roi = img[y:y+h, x:x+w]
        b = np.mean(roi[..., 0])
        g = np.mean(roi[..., 1])
        r = np.mean(roi[..., 2])
        return g, r, b

    def menu_present(self, img):
        roi_cfg = CONFIG.get('fishing_icon_roi') or CONFIG.get('result_name_roi')
        if not roi_cfg:
            return False
        x, y, w, h = roi_cfg['x'], roi_cfg['y'], roi_cfg['w'], roi_cfg['h']
        if y+h > img.shape[0] or x+w > img.shape[1]:
            return False
        roi = img[y:y+h, x:x+w]
        
        # Umbral configurable para detección del icono/menú
        # Default bajado a 75 para ser más tolerante con iconos no-blancos
        threshold = CONFIG.get('fishing_icon_threshold', 75)
        
        val = np.mean(roi)
        if CONFIG.get('log_debug_values', False):
            # Solo imprimir cada X frames para no saturar, o confiar en que el usuario lo activa a propósito
            pass 
            
        if val > threshold: 
            return True
        return False

    def read_fish_name(self, img):
        roi_cfg = CONFIG.get('result_name_roi')
        if not roi_cfg:
            return None
            
        x, y, w, h = roi_cfg['x'], roi_cfg['y'], roi_cfg['w'], roi_cfg['h']
        if w == 0 or h == 0:
            return None
            
        if y+h > img.shape[0] or x+w > img.shape[1]:
            return None
            
        roi = img[y:y+h, x:x+w]
        # Convertir a RGB para EasyOCR
        roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
        
        try:
            results = self.reader.readtext(roi_rgb, detail=0)
            if results:
                return " ".join(results)
        except Exception as e:
            print(f"Error OCR: {e}")
            
        return None

    def ensure_session(self):
        now = time.time()
        if self.next_session_delay_until and now < self.next_session_delay_until:
            return 

        if self.session_start_time is None:
            self.reset_session()

    def reset_session(self):
        self.session_start_time = time.time()
        self.last_detection_time = None
        self.last_press_time = None
        self.awaiting_completion = False
        self.menu_absent_since = None
        self.last_state = None
        self.last_pressed_key = None
        self.sequence_fallback_done = False
        self.pressed_flags = {'e': False, 'r': False, 't': False, 'wait_red': False}
        self.detect_times = {'e': None, 'r': None, 't': None, 'wait_red': None}
        self.letter_red_registered = {'e': False, 'r': False, 't': False}
        self.brain.reset()
        
        # Calcular timeout dinámico para esta sesión
        min_wait = CONFIG.get('start_wait_timeout_min_seconds', 18)
        max_wait = CONFIG.get('start_wait_timeout_max_seconds', 21)
        self.session_start_timeout = random.uniform(min_wait, max_wait)
        
    def try_start(self):
        if CONFIG.get('start_press_on_run', True):
            key = CONFIG.get('start_key', '5')
            print(f"Iniciando pesca con '{key}'...")
            pyautogui.press(key)
            self.session_start_time = time.time()
            # Calcular timeout dinámico para el inicio
            min_wait = CONFIG.get('start_wait_timeout_min_seconds', 18)
            max_wait = CONFIG.get('start_wait_timeout_max_seconds', 21)
            self.session_start_timeout = random.uniform(min_wait, max_wait)

    def run(self):
        print("--- BOT INICIADO ---")
        print("Presiona Ctrl+C en la terminal para detener.")
        delay = float(CONFIG.get('start_focus_delay_seconds', 0))
        if delay > 0:
            time.sleep(delay)
        self.try_start()
        
        try:
            while self.running:
                self.ensure_session()
                sct_img = self.sct.grab(self.monitor)
                img = np.array(sct_img)

                menu_is_present = self.menu_present(img)

                wait_g, wait_r, wait_b = self.process_region(img, 'wait')
                wg_diff = wait_g - max(wait_r, wait_b)
                wr_diff = wait_r - max(wait_g, wait_b)

                # 1. PRIORIDAD ABSOLUTA: Detectar '!' ROJO (Pez picó)
                # Chequeamos esto PRIMERO para evitar que el estado "Esperando" lo bloquee
                # FIX: Añadido chequeo de menu_present y not already_in_sequence para evitar falsos positivos al final
                already_in_sequence = (len(self.brain.history) > 0)
                wait_red_active = (wait_r > self.thresh['red_min'] and 
                                 wr_diff > CONFIG['thresholds'].get('wait_red_diff_min', 15) and
                                 menu_is_present and 
                                 not already_in_sequence)
                
                if wait_red_active:
                    if self.detect_times['wait_red'] is None:
                        self.detect_times['wait_red'] = time.time()
                    elif not self.pressed_flags['wait_red'] and time.time() - self.detect_times['wait_red'] >= float(CONFIG.get('press_delay_seconds', 0.5)):
                        key = random.choice(CONFIG['keys'])
                        print(f"¡PEZ PICÓ! → Presionando {key.upper()}")
                        pyautogui.press(key)
                        self.brain.register_key(key)
                        self.pressed_flags['wait_red'] = True
                        self.last_detection_time = time.time()
                        self.awaiting_completion = True
                    # Si detectamos rojo, no hacemos nada más en este frame
                    continue
                else:
                    self.detect_times['wait_red'] = None
                    self.pressed_flags['wait_red'] = False

                # 2. Estado "Esperando" (Verde/Grisáceo)
                # Solo si NO hay rojo y NO estamos ya en una secuencia de letras
                wait_green_active = (wait_g >= self.thresh['green_min'] and wg_diff > CONFIG['thresholds'].get('wait_green_diff_min', -30))
                # already_in_sequence ya calculado arriba
                
                if wait_green_active and not already_in_sequence:
                    if self.last_state != 'esperando':
                        print("Esperando...")
                        self.last_state = 'esperando'
                    # RESTAURADO: continue
                    # Evita falsos positivos de letras mientras esperamos.
                    # Como ya priorizamos el ROJO arriba, esto es seguro.
                    continue

                # Detección de teclas con prioridad
                e_g, e_r, e_b = self.process_region(img, 'e')
                e_diff = e_g - max(e_r, e_b)
                e_rdiff = e_r - max(e_g, e_b)
                e_is_red = (e_r >= self.thresh['red_min'] and e_rdiff > CONFIG['thresholds'].get('letter_red_diff_min', 15))
                if e_is_red and not self.letter_red_registered['e']:
                    self.brain.register_wrong_key('e')
                    self.letter_red_registered['e'] = True
                e_active = (e_g >= self.thresh['green_min'] and e_diff > CONFIG['thresholds'].get('green_diff_min', 20) and not e_is_red)
                
                r_g, r_r, r_b = self.process_region(img, 'r')
                r_diff = r_g - max(r_r, r_b)
                r_rdiff = r_r - max(r_g, r_b)
                r_is_red = (r_r >= self.thresh['red_min'] and r_rdiff > CONFIG['thresholds'].get('letter_red_diff_min', 15))
                if r_is_red and not self.letter_red_registered['r']:
                    self.brain.register_wrong_key('r')
                    self.letter_red_registered['r'] = True
                r_active = (r_g >= self.thresh['green_min'] and r_diff > CONFIG['thresholds'].get('green_diff_min', 20) and not r_is_red)
                
                t_g, t_r, t_b = self.process_region(img, 't')
                t_diff = t_g - max(t_r, t_b)
                t_rdiff = t_r - max(t_g, t_b)
                t_is_red = (t_r >= self.thresh['red_min'] and t_rdiff > CONFIG['thresholds'].get('letter_red_diff_min', 15))
                if t_is_red and not self.letter_red_registered['t']:
                    self.brain.register_wrong_key('t')
                    self.letter_red_registered['t'] = True
                t_active = (t_g >= self.thresh['green_min'] and t_diff > CONFIG['thresholds'].get('green_diff_min', 20) and not t_is_red)
                
                pressed_key = None
                if e_active and not self.pressed_flags['e']:
                    if self.detect_times['e'] is None:
                        self.detect_times['e'] = time.time()
                        self.last_state = 'e_detectada'
                    elif time.time() - self.detect_times['e'] >= float(CONFIG.get('press_delay_seconds', 0.5)):
                        pressed_key = 'e'
                elif r_active and not self.pressed_flags['r']:
                    if self.detect_times['r'] is None:
                        self.detect_times['r'] = time.time()
                        self.last_state = 'r_detectada'
                    elif time.time() - self.detect_times['r'] >= float(CONFIG.get('press_delay_seconds', 0.5)):
                        pressed_key = 'r'
                elif t_active and not self.pressed_flags['t']:
                    if self.detect_times['t'] is None:
                        self.detect_times['t'] = time.time()
                        self.last_state = 't_detectada'
                    elif time.time() - self.detect_times['t'] >= float(CONFIG.get('press_delay_seconds', 0.5)):
                        pressed_key = 't'
                
                if pressed_key:
                    key_names = {'e': 'ESPERA', 'r': 'REEL', 't': 'TIRA'}
                    print(f"{key_names[pressed_key]} DETECTADO → Presionando '{pressed_key.upper()}'")
                    pyautogui.press(pressed_key)
                    self.brain.register_key(pressed_key)
                    self.pressed_flags[pressed_key] = True
                    self.last_detection_time = time.time()
                    self.last_press_time = self.last_detection_time
                    self.awaiting_completion = True
                    self.last_state = pressed_key
                    self.last_pressed_key = pressed_key
                else:
                    if not e_active:
                        self.detect_times['e'] = None
                        self.pressed_flags['e'] = False
                    if not r_active:
                        self.detect_times['r'] = None
                        self.pressed_flags['r'] = False
                    if not t_active:
                        self.detect_times['t'] = None
                        self.pressed_flags['t'] = False

                letters_present = e_active or r_active or t_active

                # Lógica de finalización / Bloqueo
                # Si ha pasado mucho tiempo desde la última tecla y seguimos "pescando", algo va mal.
                # Esto soluciona el caso donde menu_present da falso positivo.
                force_finish = False
                if self.awaiting_completion and self.last_press_time:
                    idle_time = time.time() - self.last_press_time
                    if idle_time > CONFIG.get('max_sequence_idle_seconds', 8.0):
                        print(f"DEBUG: Tiempo de inactividad excedido ({idle_time:.1f}s). Forzando finalización.")
                        force_finish = True

                if menu_is_present and not force_finish:
                    self.menu_absent_since = None
                else:
                    if (self.last_press_time is not None and not letters_present) or force_finish:
                        if self.menu_absent_since is None:
                            self.menu_absent_since = time.time()
                        else:
                            hold = CONFIG.get('menu_absent_hold_seconds', 2.0)
                            # Si forzamos, reducimos el tiempo de espera
                            if force_finish: 
                                hold = 0.5
                                
                            post_key = CONFIG.get('post_last_key_min_seconds', 2.0)
                            if (time.time() - self.menu_absent_since >= hold and
                                time.time() - self.last_press_time >= post_key) or force_finish:
                                
                                # Intentar leer nombre antes de reiniciar
                                try:
                                    print("Intentando leer resultado...")
                                    fish_name = self.read_fish_name(img)
                                    if fish_name:
                                        print(f"CAPTURADO: {fish_name}")
                                    else:
                                        print("CAPTURADO: (No se detectó texto)")
                                except Exception as e:
                                    print(f"Error capturando nombre: {e}")

                                print("✓ Pesca completada → Reiniciando")
                                jitter = CONFIG.get('post_finish_delay_jitter')
                                if isinstance(jitter, dict):
                                    delay_secs = random.uniform(jitter.get('min', 1.0), jitter.get('max', 1.0))
                                    time.sleep(delay_secs)
                                self.reset_session()
                                if CONFIG.get('start_press_on_run', True):
                                    pyautogui.press(CONFIG.get('start_key', '5'))
                                continue
                    else:
                        self.menu_absent_since = None

                if (not self.awaiting_completion and self.last_detection_time is None 
                    and self.session_start_time is not None 
                    and time.time() - self.session_start_time >= self.session_start_timeout):
                    # Fallback siempre 'e' para reiniciar el lanzamiento
                    fb_key = 'e'
                    fb_wait = CONFIG.get('fallback_after_timeout_seconds', 1.5)
                    print(f"Tiempo de espera agotado ({self.session_start_timeout:.1f}s) → Reiniciando con '{fb_key.upper()}'")
                    # DEBUG DIAGNÓSTICO: Imprimir valores si falla para ajustar
                    # print(f"DEBUG VALORES: Wait(R:{int(wait_r)} G:{int(wait_g)} diff:{int(wr_diff)})")
                    # print(f"DEBUG E: G:{int(e_g)} diff:{int(e_diff)} | R: G:{int(r_g)} diff:{int(r_diff)} | T: G:{int(t_g)} diff:{int(t_diff)}")
                    pyautogui.press(fb_key)
                    time.sleep(fb_wait)
                    self.reset_session()
                    if CONFIG.get('start_press_on_run', True):
                        start_key = CONFIG.get('start_key', '5')
                        print(f"Reiniciando pesca tras timeout con '{start_key}'...")
                        pyautogui.press(start_key)
                    
        except KeyboardInterrupt:
            print("\nDeteniendo bot...")

if __name__ == "__main__":
    bot = FishingBot()
    bot.run()
