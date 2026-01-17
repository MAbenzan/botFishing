import time
import os
import mss
import cv2
import numpy as np
import json
import tkinter as tk
from tkinter import ttk
import threading
import sys

# Cargar configuración existente para usar la región de captura definida
CONFIG_FILE = 'config_fishing.json'
DATASET_DIR = 'dataset/images'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

class DataCaptureTool:
    def __init__(self):
        self.config = load_config()
        self.capturing = False
        self.capture_count = 0
        self.capture_interval = 2.0  # Segundos entre capturas
        
        # Crear directorio si no existe
        if not os.path.exists(DATASET_DIR):
            os.makedirs(DATASET_DIR)
            
        # Configurar región de captura
        if 'capture_region' in self.config:
            r = self.config['capture_region']
            self.monitor = {
                "top": r['top'],
                "left": r['left'],
                "width": r['width'],
                "height": r['height']
            }
        else:
            print("ERROR: No hay región de captura configurada. Ejecuta primero calibrate_regions.py")
            sys.exit(1)

        # GUI
        self.root = tk.Tk()
        self.root.title("Recolector de Datos IA")
        self.root.geometry("300x200")
        self.root.attributes('-topmost', True)
        
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Recolector de Datos para YOLO").pack(pady=10)
        
        self.status_label = ttk.Label(main_frame, text="Estado: DETENIDO", foreground="red")
        self.status_label.pack(pady=5)
        
        self.count_label = ttk.Label(main_frame, text=f"Capturas: {self.get_existing_count()}")
        self.count_label.pack(pady=5)
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        
        self.btn_start = ttk.Button(btn_frame, text="Iniciar Captura", command=self.toggle_capture)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="Salir", command=self.root.destroy).pack(side=tk.LEFT, padx=5)
        
        self.root.mainloop()

    def get_existing_count(self):
        return len([name for name in os.listdir(DATASET_DIR) if os.path.isfile(os.path.join(DATASET_DIR, name))])

    def toggle_capture(self):
        if not self.capturing:
            self.capturing = True
            self.btn_start.configure(text="Detener Captura")
            self.status_label.configure(text="Estado: CAPTURANDO...", foreground="green")
            threading.Thread(target=self.capture_loop, daemon=True).start()
        else:
            self.capturing = False
            self.btn_start.configure(text="Iniciar Captura")
            self.status_label.configure(text="Estado: DETENIDO", foreground="red")

    def capture_loop(self):
        while self.capturing:
            try:
                # Usar contexto para mejor manejo de recursos
                with mss.mss() as sct:
                    sct_img = sct.grab(self.monitor)
                    img = np.array(sct_img)
                    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                    
                    # Generar nombre único basado en timestamp
                    timestamp = int(time.time() * 1000)
                    filename = f"fishing_{timestamp}.jpg"
                    filepath = os.path.join(DATASET_DIR, filename)
                    
                    # Guardar
                    cv2.imwrite(filepath, img)
                    
                    # Actualizar contador
                    self.capture_count = self.get_existing_count()
                    self.root.after(0, lambda: self.count_label.configure(text=f"Capturas: {self.capture_count}"))
                    
                    print(f"Guardada: {filename}")
                
                time.sleep(self.capture_interval)
                
            except Exception as e:
                print(f"Error en captura: {e}")
                # Si es el error específico de Windows, detener
                if "srcdc" in str(e) or "thread" in str(e):
                    print("Error de captura de pantalla. Deteniendo...")
                    self.capturing = False
                    self.root.after(0, self.toggle_capture)
                    break
                # Si es otro error, esperar y reintentar
                time.sleep(1)

if __name__ == "__main__":
    DataCaptureTool()