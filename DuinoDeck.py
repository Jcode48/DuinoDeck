import os
import json
import subprocess
import time
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import pyautogui
from PIL import Image, ImageDraw
import pystray

CONFIG_FILE = "config.json"

class StreamDeckApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Arduino Stream Deck Controller")
        self.root.geometry("520x450")

        self.ser = None
        self.running = False
        self.tray_icon = None

        # Vang het sluiten (X) en minimaliseren (_) op naar het systeemvak
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.root.bind("<Unmap>", self.on_minimize)

        # Laad configuratie uit JSON of gebruik standaardinstellingen
        self.button_configs = self.load_config()

        self.setup_gui()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Fout bij laden JSON: {e}")
        
        # Standaardinstellingen als JSON niet bestaat
        return [
            {"label": "Mute", "type": "Hotkey", "val": "ctrl+alt+m", "color": "F800"},
            {"label": "Play/P", "type": "Hotkey", "val": "playpause", "color": "001F"},
            {"label": "Discord", "type": "App", "val": "C:\\Windows\\notepad.exe", "color": "07E0"},
            {"label": "Google", "type": "URL", "val": "https://google.com", "color": "F81F"}
        ]

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.button_configs, f, indent=4)
        except Exception as e:
            messagebox.showerror("Fout", f"Kan instellingen niet opslaan naar JSON: {e}")

    def create_tray_image(self):
        img = Image.new('RGB', (64, 64), color=(0, 120, 215))
        draw = ImageDraw.Draw(img)
        draw.rectangle([18, 18, 46, 46], fill=(255, 255, 255))
        return img

    def hide_to_tray(self):
        if self.tray_icon is not None:
            return
        
        self.root.withdraw()

        menu = pystray.Menu(
            pystray.MenuItem('Openen', self.show_window),
            pystray.MenuItem('Afsluiten', self.quit_app)
        )
        
        self.tray_icon = pystray.Icon("StreamDeckController", self.create_tray_image(), "Arduino Stream Deck", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def on_minimize(self, event):
        if self.root.state() == 'iconic':
            self.hide_to_tray()

    def show_window(self, icon=None, item=None):
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.state, 'normal')

    def quit_app(self, icon=None, item=None):
        self.running = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass

        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None

        self.root.after(0, self.root.destroy)

    def setup_gui(self):
        # COM Poort selectie
        port_frame = ttk.LabelFrame(self.root, text=" Verbinding ")
        port_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(port_frame, text="COM-poort:").pack(side="left", padx=5)
        self.port_cb = ttk.Combobox(port_frame, values=[p.device for p in serial.tools.list_ports.comports()])
        self.port_cb.pack(side="left", padx=5)

        self.btn_connect = ttk.Button(port_frame, text="Verbinden", command=self.toggle_connection)
        self.btn_connect.pack(side="left", padx=5)

        # Knoppen instellingen
        cfg_frame = ttk.LabelFrame(self.root, text=" Knoppen Configuratie ")
        cfg_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.inputs = []
        for i in range(4):
            f = ttk.Frame(cfg_frame)
            f.pack(fill="x", padx=5, pady=5)

            ttk.Label(f, text=f"Knop {i+1}:", width=8).pack(side="left")

            lbl_ent = ttk.Entry(f, width=10)
            lbl_ent.insert(0, self.button_configs[i]["label"])
            lbl_ent.pack(side="left", padx=2)

            type_cb = ttk.Combobox(f, values=["Hotkey", "App", "URL"], width=8)
            type_cb.set(self.button_configs[i]["type"])
            type_cb.pack(side="left", padx=2)

            val_ent = ttk.Entry(f, width=25)
            val_ent.insert(0, self.button_configs[i]["val"])
            val_ent.pack(side="left", padx=2)

            self.inputs.append({"label": lbl_ent, "type": type_cb, "val": val_ent})

        # Opslaan & Synchroniseren
        sync_btn = ttk.Button(self.root, text="Sync naar Arduino Shield & Opslaan", command=self.sync_to_arduino)
        sync_btn.pack(fill="x", padx=10, pady=10)

    def toggle_connection(self):
        if self.ser and self.ser.is_open:
            self.running = False
            self.ser.close()
            self.btn_connect.config(text="Verbinden")
        else:
            port = self.port_cb.get()
            if not port:
                messagebox.showerror("Fout", "Selecteer een COM-poort!")
                return
            try:
                self.ser = serial.Serial(port, 115200, timeout=1)
                self.running = True
                self.btn_connect.config(text="Ontkoppelen")
                threading.Thread(target=self.listen_serial, daemon=True).start()
                messagebox.showinfo("Succes", "Verbonden met Arduino!")
            except Exception as e:
                messagebox.showerror("Fout", f"Kan poort niet openen: {e}")

    def sync_to_arduino(self):
        # Update interne waarden uit GUI
        for i in range(4):
            self.button_configs[i]["label"] = self.inputs[i]["label"].get()
            self.button_configs[i]["type"] = self.inputs[i]["type"].get()
            self.button_configs[i]["val"] = self.inputs[i]["val"].get()

            # Stuur serial commando indien verbonden
            if self.ser and self.ser.is_open:
                cmd = f"UPDATE:{i}:{self.button_configs[i]['label']}:{self.button_configs[i]['color']}\n"
                self.ser.write(cmd.encode())

        # Sla op naar config.json
        self.save_config()
        messagebox.showinfo("Opslaan", "Instellingen opgeslagen naar JSON!")

    def listen_serial(self):
        while self.running:
            if self.ser and self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith("BTN_"):
                    try:
                        btn_idx = int(line.split("_")[1])
                        self.execute_action(btn_idx)
                    except ValueError:
                        pass

    def execute_action(self, idx):
        cfg = self.button_configs[idx]
        act_type = cfg["type"]
        val = cfg["val"]

        if act_type == "Hotkey":
            steps = [s.strip() for s in val.split(">")]
            for step in steps:
                if step.startswith("wait:") or step.startswith("sleep:"):
                    delay = float(step.split(":")[1])
                    time.sleep(delay)
                elif step.startswith("type:") or step.startswith("write:"):
                    text = step.split(":", 1)[1]
                    pyautogui.write(text, interval=0.02)
                else:
                    keys = [k.strip() for k in step.split("+")]
                    pyautogui.hotkey(*keys)

        elif act_type == "App":
            if os.path.exists(val):
                subprocess.Popen(val)
        elif act_type == "URL":
            webbrowser.open(val)

if __name__ == "__main__":
    root = tk.Tk()
    app = StreamDeckApp(root)
    root.mainloop()