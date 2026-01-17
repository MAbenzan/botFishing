import tkinter as tk
from tkinter import ttk, messagebox
import json
import threading
import time
import os
import sys

# Asegurar que podemos importar fishing_bot desde el directorio actual
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import fishing_bot

FISH_DATA_FILE = 'fish_data.json'
CONFIG_FILE = 'config_fishing.json'

class FishingGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Panel de Control - Fishing Bot")
        self.root.geometry("400x450")
        self.root.resizable(False, False)
        
        # Estilo
        style = ttk.Style()
        style.theme_use('clam')
        
        self.bot = None
        self.bot_thread = None
        self.is_running = False
        
        # Cargar Datos
        self.fish_data = self.load_json(FISH_DATA_FILE)
        self.config_data = self.load_json(CONFIG_FILE)
        
        # UI Elements
        self.create_widgets()
        
        # Protocolo de cierre
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def load_json(self, path):
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                messagebox.showerror("Error", f"Error cargando {path}: {e}")
        return {}

    def save_json(self, path, data):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            messagebox.showerror("Error", f"Error guardando {path}: {e}")

    def create_widgets(self):
        # Marco Principal
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        lbl_title = ttk.Label(main_frame, text="Configuración de Pesca", font=("Helvetica", 16, "bold"))
        lbl_title.pack(pady=(0, 20))
        
        # Selector de Ubicación
        ttk.Label(main_frame, text="Ubicación (Location):").pack(anchor=tk.W)
        self.loc_var = tk.StringVar(value=self.fish_data.get('active_location', ''))
        self.loc_combo = ttk.Combobox(main_frame, textvariable=self.loc_var, state="readonly")
        self.loc_combo['values'] = list(self.fish_data.get('locations', {}).keys())
        self.loc_combo.pack(fill=tk.X, pady=(0, 10))
        self.loc_combo.bind("<<ComboboxSelected>>", self.update_baits)
        
        # Selector de Cebo
        ttk.Label(main_frame, text="Cebo (Bait):").pack(anchor=tk.W)
        self.bait_var = tk.StringVar(value=self.fish_data.get('active_bait', ''))
        self.bait_combo = ttk.Combobox(main_frame, textvariable=self.bait_var, state="readonly")
        self.bait_combo.pack(fill=tk.X, pady=(0, 10))
        
        # Inicializar cebos si hay ubicación seleccionada
        self.update_baits(None)
        
        # Checkbox Predicción
        self.pred_var = tk.BooleanVar(value=self.config_data.get('use_prediction', True))
        chk_pred = ttk.Checkbutton(main_frame, text="Activar Predicción (Cerebro)", variable=self.pred_var)
        chk_pred.pack(pady=10, anchor=tk.W)
        
        # Controles de Inicio Automático
        ttk.Label(main_frame, text="Tecla de inicio de pesca (ej. 'f' o 'e')").pack(anchor=tk.W, pady=(10, 0))
        self.start_key_var = tk.StringVar(value=self.config_data.get('start_key', 'e'))
        self.start_key_entry = ttk.Entry(main_frame, textvariable=self.start_key_var)
        self.start_key_entry.pack(fill=tk.X, pady=(0, 10))
        
        self.start_press_var = tk.BooleanVar(value=bool(self.config_data.get('start_press_on_run', True)))
        chk_start_press = ttk.Checkbutton(main_frame, text="Presionar tecla de inicio al arrancar", variable=self.start_press_var)
        chk_start_press.pack(pady=(0, 10), anchor=tk.W)
        
        ttk.Label(main_frame, text="Retraso para cambiar a la ventana del juego (segundos)").pack(anchor=tk.W)
        self.focus_delay_var = tk.IntVar(value=int(self.config_data.get('start_focus_delay_seconds', 3)))
        self.focus_delay_entry = ttk.Entry(main_frame, textvariable=self.focus_delay_var)
        self.focus_delay_entry.pack(fill=tk.X, pady=(0, 10))
        
        # Separador
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=20)
        
        # Botón de Inicio/Parada
        self.start_btn = tk.Button(main_frame, text="INICIAR BOT", command=self.toggle_bot, 
                                  bg="#4CAF50", fg="white", font=("Arial", 14, "bold"),
                                  relief=tk.RAISED, bd=3)
        self.start_btn.pack(fill=tk.X, pady=10, ipady=10)
        
        # Etiqueta de Estado
        self.status_lbl = tk.Label(main_frame, text="Estado: DETENIDO", fg="red", font=("Arial", 10))
        self.status_lbl.pack(pady=5)
        
        # Nota
        ttk.Label(main_frame, text="Nota: Asegúrate de que el juego esté visible.", font=("Arial", 8, "italic")).pack(pady=(20, 0))

    def update_baits(self, event):
        loc = self.loc_var.get()
        if loc in self.fish_data.get('locations', {}):
            baits = list(self.fish_data['locations'][loc].keys())
            self.bait_combo['values'] = baits
            
            # Si el cebo actual no es válido para la nueva ubicación, seleccionar el primero
            if self.bait_var.get() not in baits:
                if baits:
                    self.bait_var.set(baits[0])
                else:
                    self.bait_var.set('')
        else:
            self.bait_combo['values'] = []
            self.bait_var.set('')

    def toggle_bot(self):
        if not self.is_running:
            self.start_bot()
        else:
            self.stop_bot()

    def start_bot(self):
        # Validaciones
        if not self.loc_var.get() or not self.bait_var.get():
            messagebox.showwarning("Faltan datos", "Por favor selecciona una Ubicación y un Cebo.")
            return
            
        # Guardar configuraciones antes de iniciar
        self.fish_data['active_location'] = self.loc_var.get()
        self.fish_data['active_bait'] = self.bait_var.get()
        self.save_json(FISH_DATA_FILE, self.fish_data)
        
        # Recargar config local para asegurar integridad
        self.config_data = self.load_json(CONFIG_FILE)
        self.config_data['use_prediction'] = self.pred_var.get()
        # Aplicar configuración de inicio automático
        self.config_data['start_key'] = (self.start_key_var.get() or '').strip().lower()
        self.config_data['start_press_on_run'] = bool(self.start_press_var.get())
        self.config_data['start_focus_delay_seconds'] = int(self.focus_delay_var.get() or 3)
        self.save_json(CONFIG_FILE, self.config_data)
        
        # UI Update
        self.is_running = True
        self.start_btn.config(text="DETENER BOT", bg="#F44336")
        self.status_lbl.config(text="Estado: CORRIENDO (Presiona para detener)", fg="green")
        self.disable_controls()
        
        # Iniciar Thread
        self.bot_thread = threading.Thread(target=self.run_bot_logic)
        self.bot_thread.daemon = True
        self.bot_thread.start()

    def run_bot_logic(self):
        try:
            # Forzar recarga de configuración en el módulo del bot
            fishing_bot.CONFIG = fishing_bot.load_config()
            
            # Crear e iniciar bot
            self.bot = fishing_bot.FishingBot()
            print("\n--- INICIANDO BOT DESDE GUI ---")
            self.bot.run()
        except Exception as e:
            print(f"Error crítico en el bot: {e}")
        finally:
            # Cuando el bot termina (por error o parada voluntaria), actualizar UI
            self.root.after(0, self.stop_bot_ui)

    def stop_bot(self):
        if self.bot:
            print("Deteniendo bot...")
            self.bot.running = False
            self.status_lbl.config(text="Estado: DETENIENDO...", fg="orange")
        # La UI se actualizará en el finally del thread

    def stop_bot_ui(self):
        self.is_running = False
        self.bot = None
        self.start_btn.config(text="INICIAR BOT", bg="#4CAF50")
        self.status_lbl.config(text="Estado: DETENIDO", fg="red")
        self.enable_controls()

    def disable_controls(self):
        self.loc_combo.config(state="disabled")
        self.bait_combo.config(state="disabled")
        self.start_key_entry.config(state="disabled")
        # Mantener checkbox habilitado para permitir desactivar si algo sale mal
        # pero deshabilitar el campo de retraso para evitar cambios accidentales
        self.focus_delay_entry.config(state="disabled")

    def enable_controls(self):
        self.loc_combo.config(state="readonly")
        self.bait_combo.config(state="readonly")
        self.start_key_entry.config(state="normal")
        self.focus_delay_entry.config(state="normal")

    def on_close(self):
        if self.is_running:
            if messagebox.askokcancel("Salir", "El bot está corriendo. ¿Quieres detenerlo y salir?"):
                self.stop_bot()
                # Esperar un poco a que el thread muera (opcional)
                self.root.destroy()
        else:
            self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = FishingGUI(root)
    root.mainloop()
