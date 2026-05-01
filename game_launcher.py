import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import json
import os
import sys
import subprocess
import time
import threading
import psutil
import requests
from io import BytesIO
from PIL import Image, ImageTk, ImageDraw
import ctypes
from ctypes import wintypes
import pystray
from pystray import MenuItem as item
from pynput import keyboard
from datetime import datetime
import pygame

BUILD_VERSION = "1.2.0"

ctk.set_appearance_mode("Dark")

class GameLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        if getattr(sys, 'frozen', False):
            self.base_path = os.path.dirname(sys.executable)
        else:
            self.base_path = os.path.dirname(os.path.abspath(__file__))
            
        self.db_file = os.path.join(self.base_path, "data.json")
        
        self.themes = {
            "Black-Green": {
                "bg": "#0a0b10", 
                "card": "#161925", 
                "accent": "#00ffa3", 
                "hover": "#00d185",
                "fg": "#ffffff", 
                "text_sec": "#94a3b8", 
                "title_bar": "#050608", 
                "input": "#000000"
            },
            "Black-Blue": {
                "bg": "#0a0b10", 
                "card": "#161925", 
                "accent": "#0078d7", 
                "hover": "#005a9e",
                "fg": "#ffffff", 
                "text_sec": "#94a3b8", 
                "title_bar": "#050608", 
                "input": "#000000"
            }
        }

        self.translations = {
            "EN": {
                "library": "My Library", "add": "ADD GAME", "played": "Played:",
                "play": "PLAY", "running": "ACTIVE", "settings": "Settings",
                "lang": "Language", "theme": "Color Scheme", "h": "h", "m": "m", "min": "min",
                "save": "Apply Changes", "del": "Delete Game", "edit": "Game Config",
                "browse": "Browse...", "title": "TITLE", "path": "EXE PATH", "icon": "ICON PATH"
            },
            "RU": {
                "library": "Библиотека", "add": "ДОБАВИТЬ", "played": "В игре:",
                "play": "ИГРАТЬ", "running": "ЗАПУЩЕНО", "settings": "Настройки",
                "lang": "Язык", "theme": "Цветовая схема", "h": "ч", "m": "м", "min": "мин",
                "save": "Сохранить", "del": "Удалить игру", "edit": "Настройка игры",
                "browse": "Обзор...", "title": "НАЗВАНИЕ", "path": "ПУТЬ К EXE", "icon": "ПУТЬ К ИКОНКЕ"
            }
        }

        data = self.load_data()
        self.games = data.get("games", [])
        self.lang = data.get("lang", "RU")
        self.current_theme_name = data.get("theme", "Black-Blue")
        self.colors = self.themes.get(self.current_theme_name, self.themes["Black-Blue"])
        
        self.running_processes = {}
        self.icons_cache = {}
        self._offsetx = 0
        self._offsety = 0
        self.listener = None
        self.screenshot_sound = None
        
        # Initialize pygame mixer for sound
        try:
            pygame.mixer.init()
        except:
            pass
        
        self.title("TimeGManager")
        self.geometry("1100x800")
        self.overrideredirect(True)
        
        self.setup_tray()
        self.setup_ui()
        self.set_appwindow()
        self.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.start_hotkey_listener()

    def get_game_icon(self, game, size=64):
        icon_key = game.get('custom_icon') or game['path']
        if icon_key in self.icons_cache:
            return self.icons_cache[icon_key]

        try:
            if game.get('custom_icon') and os.path.exists(game['custom_icon']):
                img = Image.open(game['custom_icon']).convert("RGBA")
            else:
                import win32gui, win32ui, win32con, win32api
                large, small = win32gui.ExtractIconEx(game['path'], 0)
                if large:
                    win32gui.DestroyIcon(small[0])
                    hicon = large[0]
                    hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
                    hbmp = win32ui.CreateBitmap()
                    hbmp.CreateCompatibleBitmap(hdc, 32, 32)
                    hdc_mem = hdc.CreateCompatibleDC()
                    hdc_mem.SelectObject(hbmp)
                    hdc_mem.DrawIcon((0, 0), hicon)
                    
                    bmpinfo = hbmp.GetInfo()
                    bmpstr = hbmp.GetBitmapBits(True)
                    img = Image.frombuffer('RGBA', (32, 32), bmpstr, 'raw', 'BGRA', 0, 1)
                    win32gui.DestroyIcon(hicon)
                else:
                    raise Exception("No system icon found")

            img = img.resize((size, size), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
            self.icons_cache[icon_key] = ctk_img
            return ctk_img
        except:
            # Fallback icon
            img = Image.new("RGBA", (size, size), (0,0,0,0))
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle((0,0,size,size), 15, fill=self.colors["accent"])
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
            return ctk_img

    def set_appwindow(self):
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080
        hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style = style & ~WS_EX_TOOLWINDOW
        style = style | WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

    def setup_tray(self):
        def on_clicked(icon, item):
            if str(item) in ["Развернуть", "Restore"]:
                self.after(0, self.show_window)
            elif str(item) in ["Выход", "Exit"]:
                self.after(0, self.quit_app)

        icon_img = Image.new('RGB', (64, 64), color=(31, 106, 165))
        try:
            res = requests.get("https://cdn-icons-png.flaticon.com/512/681/681392.png", timeout=2)
            icon_img = Image.open(BytesIO(res.content))
        except: pass

        menu_items = [
            item('Развернуть' if self.lang == "RU" else 'Restore', on_clicked, default=True),
            item('Выход' if self.lang == "RU" else 'Exit', on_clicked)
        ]
        self.tray_icon = pystray.Icon("TimeGManager", icon_img, "TimeGManager", menu=pystray.Menu(*menu_items))
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def hide_window(self):
        self.withdraw()

    def show_window(self):
        self.deiconify()
        self.set_appwindow()

    def quit_app(self):
        if self.listener:
            self.listener.stop()
        self.tray_icon.stop()
        self.destroy()
        sys.exit()

    def load_data(self):
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return {"games": [], "lang": "RU", "theme": "Black-Blue"}

    def save_data(self):
        with open(self.db_file, "w", encoding="utf-8") as f:
            json.dump({
                "games": self.games, 
                "lang": self.lang, 
                "theme": self.current_theme_name
            }, f, indent=4, ensure_ascii=False)

    def setup_ui(self):
        self.configure(fg_color=self.colors["bg"])
        
        self.title_bar = ctk.CTkFrame(self, fg_color=self.colors["title_bar"], height=35, corner_radius=0)
        self.title_bar.pack(side="top", fill="x")
        self.title_bar.bind("<Button-1>", self.click_title_bar)
        self.title_bar.bind("<B1-Motion>", self.drag_title_bar)

        self.title_label = ctk.CTkLabel(self.title_bar, text=f"TimeGManager [v{BUILD_VERSION}]", font=("Segoe UI", 11), text_color=self.colors["text_sec"])
        self.title_label.pack(side="left", padx=15)
        self.title_label.bind("<Button-1>", self.click_title_bar)
        self.title_label.bind("<B1-Motion>", self.drag_title_bar)

        self.close_btn = ctk.CTkButton(self.title_bar, text="✕", width=45, height=35, 
                                        fg_color="transparent", hover_color="#e81123", 
                                        corner_radius=0, command=self.hide_window)
        self.close_btn.pack(side="right")

        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=40, pady=20)

        header = ctk.CTkFrame(self.main_container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))

        self.lib_label = ctk.CTkLabel(header, text=self.translations[self.lang]["library"], 
                                      font=("Segoe UI Variable Display", 32, "bold"), text_color=self.colors["fg"])
        self.lib_label.pack(side="left")

        self.add_btn = ctk.CTkButton(header, text=self.translations[self.lang]["add"], 
                                     font=("Segoe UI", 13, "bold"), height=40,
                                     fg_color=self.colors["accent"], text_color="#000000",
                                     hover_color=self.colors["hover"], command=self.add_game)
        self.add_btn.pack(side="right", padx=10)

        self.settings_btn = ctk.CTkButton(header, text="⚙", width=40, height=40, 
                                          fg_color=self.colors["card"], hover_color="#2b2e3b",
                                          command=self.open_settings)
        self.settings_btn.pack(side="right")

        self.scroll_canvas = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent", scrollbar_button_color=self.colors["card"])
        self.scroll_canvas.pack(fill="both", expand=True)
        
        self.refresh_grid()

    def click_title_bar(self, event):
        self._offsetx = event.x
        self._offsety = event.y

    def drag_title_bar(self, event):
        x = self.winfo_pointerx() - self._offsetx
        y = self.winfo_pointery() - self._offsety
        self.geometry(f"+{x}+{y}")

    def refresh_grid(self):
        for child in self.scroll_canvas.winfo_children():
            child.destroy()
        
        t = self.translations[self.lang]
        for index, game in enumerate(self.games):
            is_run = game['path'] in self.running_processes
            
            card = ctk.CTkFrame(self.scroll_canvas, fg_color=self.colors["card"], height=100, corner_radius=18, 
                                border_width=2 if is_run else 0, border_color=self.colors["accent"])
            card.pack(fill="x", pady=8, padx=5)
            card.pack_propagate(False)

            icon = self.get_game_icon(game)
            icon_label = ctk.CTkLabel(card, text="" if icon else "🎮", image=icon, font=("Segoe UI", 30), width=80)
            icon_label.pack(side="left", padx=20)

            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, pady=18)

            name_lbl = ctk.CTkLabel(info_frame, text=game['name'].upper(), font=("Segoe UI", 15, "bold"), anchor="w", text_color=self.colors["fg"])
            name_lbl.pack(fill="x")

            time_str = self.format_time(game['time_played'])
            time_lbl = ctk.CTkLabel(info_frame, text=f"{t['played']} {time_str}", 
                                    font=("Segoe UI", 12), text_color=self.colors["accent"] if is_run else self.colors["text_sec"], anchor="w")
            time_lbl.pack(fill="x")

            btns = ctk.CTkFrame(card, fg_color="transparent")
            btns.pack(side="right", padx=20)

            p_text = t["play"] if not is_run else t["running"]
            play_btn = ctk.CTkButton(btns, text=p_text, width=130, height=42, corner_radius=10,
                                     fg_color=self.colors["accent"] if not is_run else "#334155",
                                     text_color="#000000" if not is_run else "#ffffff",
                                     hover_color=self.colors["hover"] if not is_run else "#475569",
                                     font=("Segoe UI", 13, "bold"),
                                     command=lambda p=game['path']: self.launch_game(p))
            play_btn.pack(side="left", padx=10)

            edit_btn = ctk.CTkButton(btns, text="⋮", width=42, height=42, corner_radius=10,
                                     fg_color="#2b2e3b", text_color="white",
                                     command=lambda i=index: self.open_game_edit(i))
            edit_btn.pack(side="left")

    def format_time(self, seconds):
        t = self.translations[self.lang]
        h, m = seconds // 3600, (seconds % 3600) // 60
        return f"{h}{t['h']} {m}{t['m']}" if h > 0 else f"{m} {t['min']}"

    def launch_game(self, exe_path):
        if exe_path in self.running_processes: return
        try:
            proc = subprocess.Popen(exe_path, cwd=os.path.dirname(exe_path))
            self.running_processes[exe_path] = proc
            self.refresh_grid()
            threading.Thread(target=self.track_time, args=(proc, exe_path), daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def track_time(self, proc, exe_path):
        start = time.time()
        while psutil.pid_exists(proc.pid):
            try:
                p = psutil.Process(proc.pid)
                if p.status() == psutil.STATUS_ZOMBIE: break
            except: break
            time.sleep(2)
        
        elapsed = int(time.time() - start)
        for g in self.games:
            if g['path'] == exe_path:
                g['time_played'] += elapsed
                break
        self.save_data()
        self.running_processes.pop(exe_path, None)
        self.after(0, self.refresh_grid)

    def add_game(self):
        file_path = filedialog.askopenfilename(filetypes=[("Games", "*.exe")])
        if file_path:
            name = os.path.splitext(os.path.basename(file_path))[0]
            self.games.append({"name": name, "path": file_path, "time_played": 0, "custom_icon": ""})
            self.save_data()
            self.refresh_grid()

    def open_game_edit(self, index):
        game = self.games[index]
        t = self.translations[self.lang]
        
        edit_win = ctk.CTkToplevel(self)
        edit_win.title(t["edit"])
        edit_win.geometry("500x450")
        edit_win.resizable(False, False)
        edit_win.configure(fg_color=self.colors["card"])
        edit_win.after(10, edit_win.focus_force)
        edit_win.attributes("-topmost", True)

        ctk.CTkLabel(edit_win, text=t["edit"].upper(), font=("Segoe UI", 18, "bold")).pack(pady=20)
        
        ctk.CTkLabel(edit_win, text=t["title"], font=("Segoe UI", 10, "bold"), text_color=self.colors["text_sec"]).pack(anchor="w", padx=50)
        name_entry = ctk.CTkEntry(edit_win, width=400, height=40, fg_color=self.colors["input"], border_width=0)
        name_entry.insert(0, game['name'])
        name_entry.pack(pady=(5, 15))

        ctk.CTkLabel(edit_win, text=t["icon"], font=("Segoe UI", 10, "bold"), text_color=self.colors["text_sec"]).pack(anchor="w", padx=50)
        icon_frame = ctk.CTkFrame(edit_win, fg_color="transparent")
        icon_frame.pack(fill="x", padx=50)
        
        icon_entry = ctk.CTkEntry(icon_frame, width=310, height=40, fg_color=self.colors["input"], border_width=0)
        icon_entry.insert(0, game.get('custom_icon', ''))
        icon_entry.pack(side="left")
        
        def browse_icon():
            path = filedialog.askopenfilename(filetypes=[("Image", "*.png;*.jpg;*.jpeg;*.ico")])
            if path:
                icon_entry.delete(0, tk.END)
                icon_entry.insert(0, path)

        ctk.CTkButton(icon_frame, text="...", width=80, height=40, fg_color="#2b2e3b", command=browse_icon).pack(side="right", padx=(10,0))

        def save():
            self.games[index]['name'] = name_entry.get()
            self.games[index]['custom_icon'] = icon_entry.get()
            self.icons_cache.pop(game['path'], None)
            self.save_data()
            self.refresh_grid()
            edit_win.destroy()

        def delete():
            self.games.pop(index)
            self.save_data()
            self.refresh_grid()
            edit_win.destroy()

        ctk.CTkButton(edit_win, text=t["save"], width=400, height=45, fg_color=self.colors["accent"], text_color="#000000", hover_color=self.colors["hover"], font=("Segoe UI", 12, "bold"), command=save).pack(pady=(30, 10))
        ctk.CTkButton(edit_win, text=t["del"], width=400, height=45, fg_color="#ef4444", hover_color="#dc2626", font=("Segoe UI", 12, "bold"), command=delete).pack(pady=5)

    def open_settings(self):
        t = self.translations[self.lang]
        set_win = ctk.CTkToplevel(self)
        set_win.title(t["settings"])
        set_win.geometry("450x450")
        set_win.resizable(False, False)
        set_win.configure(fg_color=self.colors["card"])
        set_win.attributes("-topmost", True)

        ctk.CTkLabel(set_win, text=t["settings"].upper(), font=("Segoe UI", 18, "bold")).pack(pady=25)

        ctk.CTkLabel(set_win, text=t["lang"], font=("Segoe UI", 10, "bold"), text_color=self.colors["text_sec"]).pack(anchor="w", padx=50)
        lang_cb = ctk.CTkComboBox(set_win, values=["RU", "EN"], width=350, height=40, fg_color=self.colors["input"], border_width=0)
        lang_cb.set(self.lang)
        lang_cb.pack(pady=(5, 20))

        ctk.CTkLabel(set_win, text=t["theme"], font=("Segoe UI", 10, "bold"), text_color=self.colors["text_sec"]).pack(anchor="w", padx=50)
        theme_cb = ctk.CTkComboBox(set_win, values=list(self.themes.keys()), width=350, height=40, fg_color=self.colors["input"], border_width=0)
        theme_cb.set(self.current_theme_name)
        theme_cb.pack(pady=(5, 20))

        def apply():
            self.lang = lang_cb.get()
            self.current_theme_name = theme_cb.get()
            self.colors = self.themes[self.current_theme_name]
            self.save_data()
            self.configure(fg_color=self.colors["bg"])
            self.title_bar.configure(fg_color=self.colors["title_bar"])
            self.lib_label.configure(text=self.translations[self.lang]["library"], text_color=self.colors["fg"])
            self.add_btn.configure(text=self.translations[self.lang]["add"], fg_color=self.colors["accent"], hover_color=self.colors["hover"])
            self.refresh_grid()
            set_win.destroy()

        ctk.CTkButton(set_win, text=t["save"], width=350, height=45, fg_color=self.colors["accent"], text_color="#000000", hover_color=self.colors["hover"], font=("Segoe UI", 12, "bold"), command=apply).pack(pady=30)

    def start_hotkey_listener(self):
        """Start listening for F12 hotkey"""
        def on_press(key):
            try:
                if key == keyboard.Key.f12 and self.running_processes:
                    threading.Thread(target=self.take_screenshot, daemon=True).start()
            except AttributeError:
                pass

        self.listener = keyboard.Listener(on_press=on_press)
        self.listener.start()

    def take_screenshot(self):
        """Take screenshot and save it"""
        try:
            from mss import mss
            
            # Create screenshots directory in exe location
            if self.running_processes:
                exe_path = list(self.running_processes.keys())[0]
                game_dir = os.path.dirname(exe_path)
                screenshots_dir = os.path.join(game_dir, "screenshots")
                
                if not os.path.exists(screenshots_dir):
                    os.makedirs(screenshots_dir)
                
                # Take screenshot
                with mss() as sct:
                    monitor = sct.monitors[1]
                    screenshot = sct.grab(monitor)
                    img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
                    
                    # Save with timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = os.path.join(screenshots_dir, f"screenshot_{timestamp}.png")
                    img.save(filename)
                
                # Play sound
                self.play_screenshot_sound()
                
        except Exception as e:
            print(f"Screenshot error: {e}")

    def play_screenshot_sound(self):
        """Download and play screenshot sound"""
        try:
            if not self.screenshot_sound:
                res = requests.get("https://www.myinstants.com/media/sounds/iphone-screenshot.mp3", timeout=5)
                self.screenshot_sound = BytesIO(res.content)
                self.screenshot_sound.seek(0)
            else:
                self.screenshot_sound.seek(0)
            
            pygame.mixer.music.load(self.screenshot_sound)
            pygame.mixer.music.play()
        except Exception as e:
            print(f"Sound playback error: {e}")

if __name__ == "__main__":
    app = GameLauncher()
    app.mainloop()
