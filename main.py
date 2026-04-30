import tkinter as tk
from tkinter import ttk, filedialog, messagebox
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

BUILD_VERSION = "1.1.2"

class GameLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("TimeGManager")
        self.root.geometry("1100x800")
        
        if getattr(sys, 'frozen', False):
            self.base_path = os.path.dirname(sys.executable)
        else:
            self.base_path = os.path.dirname(os.path.abspath(__file__))
            
        self.db_file = os.path.join(self.base_path, "data.json")
        
        self.themes = {
            "Black-Green": {"bg": "#0a0b10", "card": "#161925", "accent": "#00ffa3", "fg": "#ffffff", "text_sec": "#94a3b8", "btn_hover": "#00d185", "input_bg": "#000000"},
            "Black-Blue": {"bg": "#0a0b10", "card": "#161925", "accent": "#00b4ff", "fg": "#ffffff", "text_sec": "#94a3b8", "btn_hover": "#0091cc", "input_bg": "#000000"}
        }

        self.translations = {
            "EN": {
                "library": "My Library", "add": "ADD GAME", "played": "In game:",
                "play": "PLAY", "running": "ACTIVE", "settings": "Settings",
                "lang": "Language", "theme": "Color Scheme", "h": "h", "m": "m", "min": "min",
                "Programs": "Programs", "save": "Apply Changes", "del": "Delete Game", "edit": "Game Config",
                "browse": "Browse...", "title": "TITLE", "icon_path": "ICON PATH"
            },
            "RU": {
                "library": "Библиотека", "add": "ДОБАВИТЬ", "played": "В игре:",
                "play": "ИГРАТЬ", "running": "ЗАПУЩЕНО", "settings": "Настройки",
                "lang": "Язык", "theme": "Цветовая схема", "h": "ч", "m": "м", "min": "мин",
                "Programs": "Программы", "save": "Сохранить", "del": "Удалить игру", "edit": "Настройка игры",
                "browse": "Обзор...", "title": "НАЗВАНИЕ", "icon_path": "ПУТЬ К ИКОНКЕ"
            }
        }

        data = self.load_data()
        self.games = data.get("games", [])
        self.lang = data.get("lang", "RU")
        self.current_theme_name = data.get("theme", "Black-Blue")
        if self.current_theme_name not in self.themes:
            self.current_theme_name = "Black-Blue"
        self.colors = self.themes[self.current_theme_name]
        
        self.running_processes = {}
        self.icons_cache = {}
        self.image_refs = {}
        
        self.load_web_assets()
        self.setup_ui()
        self.refresh_grid()
        self.set_app_icon()

    def load_web_assets(self):
        assets = {
            "settings": "https://cdn-icons-png.flaticon.com/512/2040/2040504.png",
            "pause": "https://cdn-icons-png.flaticon.com/512/727/727245.png",
            "app": "https://cdn-icons-png.flaticon.com/512/681/681392.png"
        }
        for name, url in assets.items():
            try:
                response = requests.get(url, timeout=5)
                img = Image.open(BytesIO(response.content)).convert("RGBA")
                size = 20 if name != "app" else 64
                if name == "settings":
                    r, g, b, a = img.split()
                    img = Image.merge("RGBA", (r.point(lambda _: 255), g.point(lambda _: 255), b.point(lambda _: 255), a))
                self.icons_cache[name] = ImageTk.PhotoImage(img.resize((size, size), Image.Resampling.LANCZOS))
            except:
                self.icons_cache[name] = None

    def set_app_icon(self):
        if self.icons_cache.get("app"):
            self.root.iconphoto(False, self.icons_cache["app"])

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
        self.root.configure(bg=self.colors["bg"])
        self.top_bar = tk.Frame(self.root, bg=self.colors["bg"], height=100)
        self.top_bar.pack(fill=tk.X, padx=40, pady=20)
        self.top_bar.pack_propagate(False)

        left_group = tk.Frame(self.top_bar, bg=self.colors["bg"])
        left_group.pack(side=tk.LEFT)

        self.title_lbl = tk.Label(left_group, text=self.translations[self.lang]["library"], 
                                  font=("Segoe UI Variable Display", 28, "bold"), bg=self.colors["bg"], fg=self.colors["fg"])
        self.title_lbl.pack(side=tk.LEFT)

        self.settings_btn = tk.Button(self.top_bar, image=self.icons_cache.get("settings"), bg=self.colors["bg"],
                                      activebackground=self.colors["bg"], bd=0, cursor="hand2", command=self.open_settings)
        self.settings_btn.pack(side=tk.RIGHT, padx=10)

        self.add_btn = tk.Button(
            self.top_bar, text=self.translations[self.lang]["add"], font=("Segoe UI", 10, "bold"),
            bg=self.colors["accent"], fg="#000000", relief="flat", bd=0, padx=25, pady=10, 
            cursor="hand2", command=self.add_game
        )
        self.add_btn.pack(side=tk.RIGHT, padx=20)

        self.container = tk.Frame(self.root, bg=self.colors["bg"])
        self.container.pack(fill="both", expand=True, padx=40)

        self.canvas = tk.Canvas(self.container, bg=self.colors["bg"], highlightthickness=0)
        self.scrollable_frame = tk.Frame(self.canvas, bg=self.colors["bg"])

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))
        self.canvas.pack(side="left", fill="both", expand=True)
        self.root.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def create_modern_input(self, parent, width=400, btn_text=None, btn_cmd=None):
        container = tk.Canvas(parent, bg=self.colors["card"], height=42, width=width, highlightthickness=0)
        container.pack(pady=(5, 15))
        
        def render_bg(e=None):
            container.delete("bg_shape")
            w, h = container.winfo_width(), container.winfo_height()
            if w < 1 or h < 1: return
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle((0, 0, w, h), 10, fill=self.colors["input_bg"])
            photo = ImageTk.PhotoImage(img)
            container.image = photo
            container.create_image(0, 0, image=photo, anchor="nw", tags="bg_shape")
            container.tag_lower("bg_shape")

        entry_w = width - (100 if btn_text else 20)
        ent = tk.Entry(container, bg=self.colors["input_bg"], fg=self.colors["fg"], 
                      insertbackground=self.colors["fg"], relief="flat", font=("Segoe UI", 10), bd=0)
        container.create_window(12, 21, window=ent, anchor="w", width=entry_w)

        if btn_text:
            btn = tk.Button(container, text=btn_text, bg=self.colors["accent"], fg="#000000", 
                            font=("Segoe UI", 8, "bold"), relief="flat", bd=0, cursor="hand2", command=btn_cmd)
            container.create_window(width-5, 21, window=btn, anchor="e", width=80, height=30)

        container.bind("<Configure>", render_bg)
        return ent

    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title(" ")
        win.geometry("500x480")
        win.configure(bg=self.colors["card"])
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        t = self.translations[self.lang]
        tk.Label(win, text=t["settings"], font=("Segoe UI Semibold", 18), bg=self.colors["card"], fg=self.colors["fg"]).pack(pady=25)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Custom.TCombobox", 
                        fieldbackground=self.colors["input_bg"], 
                        background=self.colors["input_bg"], 
                        foreground=self.colors["fg"],
                        darkcolor=self.colors["input_bg"],
                        lightcolor=self.colors["input_bg"],
                        bordercolor=self.colors["input_bg"],
                        arrowcolor=self.colors["accent"])
        
        win.option_add("*TCombobox*Listbox.background", self.colors["input_bg"])
        win.option_add("*TCombobox*Listbox.foreground", self.colors["fg"])
        win.option_add("*TCombobox*Listbox.selectBackground", self.colors["accent"])
        win.option_add("*TCombobox*Listbox.selectForeground", "#000000")
        win.option_add("*TCombobox*Listbox.relief", "flat")
        win.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))

        style.map("Custom.TCombobox", 
                  fieldbackground=[('readonly', self.colors["input_bg"]), ('focus', self.colors["input_bg"])],
                  foreground=[('readonly', self.colors["fg"])])

        tk.Label(win, text=t["lang"].upper(), font=("Segoe UI", 8, "bold"), bg=self.colors["card"], fg=self.colors["text_sec"]).pack(anchor="w", padx=50)
        lang_var = tk.StringVar(value=self.lang)
        lang_cb = ttk.Combobox(win, textvariable=lang_var, values=["RU", "EN"], state="readonly", width=42, style="Custom.TCombobox")
        lang_cb.pack(pady=(5, 20), ipady=5)

        tk.Label(win, text=t["theme"].upper(), font=("Segoe UI", 8, "bold"), bg=self.colors["card"], fg=self.colors["text_sec"]).pack(anchor="w", padx=50)
        theme_var = tk.StringVar(value=self.current_theme_name)
        theme_cb = ttk.Combobox(win, textvariable=theme_var, values=list(self.themes.keys()), state="readonly", width=42, style="Custom.TCombobox")
        theme_cb.pack(pady=(5, 20), ipady=5)

        def apply():
            self.lang = lang_var.get()
            self.current_theme_name = theme_var.get()
            self.colors = self.themes[self.current_theme_name]
            self.save_data()
            self.root.configure(bg=self.colors["bg"])
            self.update_ui_styles()
            self.refresh_grid()
            win.destroy()

        tk.Button(win, text=t["save"], bg=self.colors["accent"], font=("Segoe UI", 10, "bold"),
                 fg="#000000", relief="flat", bd=0, width=28, pady=12, cursor="hand2", command=apply).pack(pady=30)
        
        tk.Label(win, text=f"Build Version {BUILD_VERSION}", font=("Consolas", 9), bg=self.colors["card"], fg=self.colors["text_sec"]).pack(side=tk.BOTTOM, pady=15)

    def update_ui_styles(self):
        t = self.translations[self.lang]
        self.top_bar.config(bg=self.colors["bg"])
        self.title_lbl.config(text=t["library"], bg=self.colors["bg"], fg=self.colors["fg"])
        self.settings_btn.config(bg=self.colors["bg"])
        self.add_btn.config(text=t["add"], bg=self.colors["accent"])
        self.container.config(bg=self.colors["bg"])
        self.canvas.config(bg=self.colors["bg"])
        self.scrollable_frame.config(bg=self.colors["bg"])

    def open_game_edit(self, index):
        game = self.games[index]
        win = tk.Toplevel(self.root)
        win.title(" ")
        win.geometry("520x500")
        win.configure(bg=self.colors["card"])
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        
        t = self.translations[self.lang]
        tk.Label(win, text=t["edit"], font=("Segoe UI Semibold", 18), bg=self.colors["card"], fg=self.colors["fg"]).pack(pady=20)
        
        tk.Label(win, text=t["title"], font=("Segoe UI", 8, "bold"), bg=self.colors["card"], fg=self.colors["text_sec"]).pack(anchor="w", padx=60)
        name_ent = self.create_modern_input(win, width=400)
        name_ent.insert(0, game['name'])

        tk.Label(win, text=t["icon_path"], font=("Segoe UI", 8, "bold"), bg=self.colors["card"], fg=self.colors["text_sec"]).pack(anchor="w", padx=60)
        
        def browse_icon():
            path = filedialog.askopenfilename(filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.ico")])
            if path:
                icon_ent.delete(0, tk.END)
                icon_ent.insert(0, path)

        icon_ent = self.create_modern_input(win, width=400, btn_text=t["browse"], btn_cmd=browse_icon)
        icon_ent.insert(0, game.get('custom_icon', ''))

        def save_edit():
            self.games[index]['name'] = name_ent.get()
            self.games[index]['custom_icon'] = icon_ent.get()
            self.save_data()
            self.refresh_grid()
            win.destroy()

        tk.Button(win, text=t["save"], bg=self.colors["accent"], font=("Segoe UI", 10, "bold"), 
                  relief="flat", bd=0, width=32, pady=12, cursor="hand2", command=save_edit).pack(pady=(35, 10))
        
        tk.Button(win, text=t["del"], bg="#ef4444", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", bd=0, width=32, pady=12, cursor="hand2", command=lambda: [self.delete_game(index), win.destroy()]).pack()

    def get_icon(self, game, size=70):
        custom = game.get('custom_icon')
        if custom:
            try:
                if custom.startswith('http'):
                    res = requests.get(custom, timeout=3)
                    img = Image.open(BytesIO(res.content)).convert("RGBA")
                else:
                    img = Image.open(custom).convert("RGBA")
                mask = Image.new("L", (size, size), 0)
                draw = ImageDraw.Draw(mask)
                draw.rounded_rectangle((0, 0, size, size), 18, fill=255)
                img = img.resize((size, size), Image.Resampling.LANCZOS)
                img.putalpha(mask)
                return ImageTk.PhotoImage(img)
            except: pass

        try:
            shell32 = ctypes.windll.shell32
            h_icon = wintypes.HICON()
            res = shell32.ExtractIconExW(game['path'], 0, ctypes.byref(h_icon), None, 1)
            if res > 0 and h_icon.value:
                import win32ui, win32gui
                hdc = win32gui.GetDC(0)
                h_dc = win32ui.CreateDCFromHandle(hdc)
                h_bmp = win32ui.CreateBitmap()
                h_bmp.CreateCompatibleBitmap(h_dc, size, size)
                h_dc_mem = h_dc.CreateCompatibleDC()
                h_dc_mem.SelectObject(h_bmp)
                win32gui.DrawIconEx(h_dc_mem.GetSafeHdc(), 0, 0, h_icon.value, size, size, 0, None, 0x0003)
                bmpinfo = h_bmp.GetInfo()
                bmpstr = h_bmp.GetBitmapBits(True)
                img = Image.frombuffer('RGBA', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRA', 0, 1)
                win32gui.DestroyIcon(h_icon.value)
                mask = Image.new("L", (size, size), 0)
                draw = ImageDraw.Draw(mask)
                draw.rounded_rectangle((0, 0, size, size), 18, fill=255)
                img = img.resize((size, size), Image.Resampling.LANCZOS)
                img.putalpha(mask)
                return ImageTk.PhotoImage(img)
        except: pass
        
        img = Image.new('RGBA', (size, size), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((0,0,size,size), 18, fill=self.colors["card"])
        return ImageTk.PhotoImage(img)

    def add_game(self):
        file_path = filedialog.askopenfilename(filetypes=[(f"{self.translations[self.lang]['Programs']}", "*.exe")])
        if not file_path: return
        game_name = os.path.splitext(os.path.basename(file_path))[0]
        self.games.append({"name": game_name, "path": file_path, "time_played": 0, "custom_icon": ""})
        self.save_data()
        self.refresh_grid()

    def format_time(self, seconds):
        t = self.translations[self.lang]
        h, m = seconds // 3600, (seconds % 3600) // 60
        return f"{h}{t['h']} {m}{t['m']}" if h > 0 else f"{m}{t['min']}"

    def render_card(self, canvas, index):
        canvas.delete("dynamic")
        game = self.games[index]
        is_run = game['path'] in self.running_processes
        t = self.translations[self.lang]
        
        w = canvas.winfo_width()
        h = 100
        if w < 10: return
        
        self.image_refs[index] = {}

        bg_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(bg_img)
        draw.rounded_rectangle((0, 0, w, h), 22, fill=self.colors["card"])
        if is_run:
            draw.rounded_rectangle((0, 0, w, h), 22, outline=self.colors["accent"], width=2)
        
        photo = ImageTk.PhotoImage(bg_img)
        self.image_refs[index]['bg'] = photo
        canvas.create_image(0, 0, image=photo, anchor="nw", tags="dynamic")
        
        icon_img = self.get_icon(game)
        self.image_refs[index]['icon'] = icon_img
        canvas.create_image(20, 15, image=icon_img, anchor="nw", tags="dynamic")
        
        canvas.create_text(110, 35, text=game['name'].upper(), font=("Segoe UI Variable Display", 14, "bold"), fill=self.colors["fg"], anchor="w", tags="dynamic")
        status_color = self.colors["accent"] if is_run else self.colors["text_sec"]
        canvas.create_text(110, 65, text=f"{t['played']} {self.format_time(game['time_played'])}", font=("Segoe UI", 10), fill=status_color, anchor="w", tags="dynamic")
        
        canvas.tag_lower("dynamic")

    def refresh_grid(self):
        for widget in self.scrollable_frame.winfo_children(): widget.destroy()
        self.image_refs = {}
        t = self.translations[self.lang]

        for index, game in enumerate(self.games):
            is_run = game['path'] in self.running_processes
            
            card_outer = tk.Frame(self.scrollable_frame, bg=self.colors["bg"], pady=8)
            card_outer.pack(fill="x", padx=10)
            
            card = tk.Canvas(card_outer, bg=self.colors["bg"], height=100, highlightthickness=0)
            card.pack(fill="x")
            
            btn_frame = tk.Frame(card, bg=self.colors["card"])
            card.create_window(0, 0, window=btn_frame, anchor="e", tags="btn_window") 

            play_btn = tk.Button(btn_frame, text=f" {t['play' if not is_run else 'running']}", 
                                 image=self.icons_cache.get("pause") if is_run else None, compound="left",
                                 font=("Segoe UI", 9, "bold"), bg=self.colors["accent"] if not is_run else "#334155", 
                                 fg="#000000" if not is_run else "#ffffff", bd=0, padx=25, pady=10, cursor="hand2",
                                 command=lambda p=game['path']: self.launch_game(p))
            play_btn.pack(side=tk.LEFT, padx=10)
            
            edit_btn = tk.Button(btn_frame, image=self.icons_cache.get("settings"), bg=self.colors["card"], 
                                 activebackground=self.colors["card"], bd=0, cursor="hand2", 
                                 command=lambda i=index: self.open_game_edit(i))
            edit_btn.pack(side=tk.LEFT, padx=10)

            def on_resize(e, c=card, i=index):
                self.render_card(c, i)
                c.coords("btn_window", e.width - 30, 50)

            card.bind("<Configure>", on_resize)

    def delete_game(self, index):
        self.games.pop(index)
        self.save_data()
        self.refresh_grid()

    def launch_game(self, exe_path):
        if exe_path in self.running_processes: return
        try:
            proc = subprocess.Popen(exe_path, cwd=os.path.dirname(exe_path))
            self.running_processes[exe_path] = True
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
        if exe_path in self.running_processes: del self.running_processes[exe_path]
        self.root.after(0, self.refresh_grid)

if __name__ == "__main__":
    root = tk.Tk()
    try:
        from ctypes import windll
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_ROUND = 2
        windll.dwmapi.DwmSetWindowAttribute(windll.user32.GetParent(root.winfo_id()), DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(ctypes.c_int(DWMWCP_ROUND)), 4)
    except: pass
    app = GameLauncher(root)
    root.mainloop()import tkinter as tk
from tkinter import ttk, filedialog, messagebox
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

BUILD_VERSION = "1.1.0"

class GameLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("TimeGManager")
        self.root.geometry("1100x800")
        
        if getattr(sys, 'frozen', False):
            self.base_path = os.path.dirname(sys.executable)
        else:
            self.base_path = os.path.dirname(os.path.abspath(__file__))
            
        self.db_file = os.path.join(self.base_path, "data.json")
        
        self.themes = {
            "Black-Green": {"bg": "#0a0b10", "card": "#161925", "accent": "#00ffa3", "fg": "#ffffff", "text_sec": "#94a3b8", "btn_hover": "#00d185", "input_bg": "#000000"},
            "Black-Blue": {"bg": "#0a0b10", "card": "#161925", "accent": "#00b4ff", "fg": "#ffffff", "text_sec": "#94a3b8", "btn_hover": "#0091cc", "input_bg": "#000000"}
        }

        self.translations = {
            "EN": {
                "library": "My Library", "add": "ADD GAME", "played": "In game:",
                "play": "PLAY", "running": "ACTIVE", "settings": "Settings",
                "lang": "Language", "theme": "Color Scheme", "h": "h", "m": "m", "min": "min",
                "Programs": "Programs", "save": "Apply Changes", "del": "Delete Game", "edit": "Game Config",
                "browse": "Browse...", "title": "TITLE", "icon_path": "ICON PATH"
            },
            "RU": {
                "library": "Библиотека", "add": "ДОБАВИТЬ", "played": "В игре:",
                "play": "ИГРАТЬ", "running": "ЗАПУЩЕНО", "settings": "Настройки",
                "lang": "Язык", "theme": "Цветовая схема", "h": "ч", "m": "м", "min": "мин",
                "Programs": "Программы", "save": "Сохранить", "del": "Удалить игру", "edit": "Настройка игры",
                "browse": "Обзор...", "title": "НАЗВАНИЕ", "icon_path": "ПУТЬ К ИКОНКЕ"
            }
        }

        data = self.load_data()
        self.games = data.get("games", [])
        self.lang = data.get("lang", "RU")
        self.current_theme_name = data.get("theme", "Black-Blue")
        if self.current_theme_name not in self.themes:
            self.current_theme_name = "Black-Blue"
        self.colors = self.themes[self.current_theme_name]
        
        self.running_processes = {}
        self.icons_cache = {}
        self.images_ref = []
        
        self.load_web_assets()
        self.setup_ui()
        self.refresh_grid()
        self.set_app_icon()

    def load_web_assets(self):
        assets = {
            "settings": "https://cdn-icons-png.flaticon.com/512/2040/2040504.png",
            "pause": "https://cdn-icons-png.flaticon.com/512/727/727245.png",
            "app": "https://cdn-icons-png.flaticon.com/512/681/681392.png"
        }
        for name, url in assets.items():
            try:
                response = requests.get(url, timeout=5)
                img = Image.open(BytesIO(response.content)).convert("RGBA")
                size = 20 if name != "app" else 64
                if name == "settings":
                    r, g, b, a = img.split()
                    img = Image.merge("RGBA", (r.point(lambda _: 255), g.point(lambda _: 255), b.point(lambda _: 255), a))
                self.icons_cache[name] = ImageTk.PhotoImage(img.resize((size, size), Image.Resampling.LANCZOS))
            except:
                self.icons_cache[name] = None

    def set_app_icon(self):
        if self.icons_cache.get("app"):
            self.root.iconphoto(False, self.icons_cache["app"])

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
        self.root.configure(bg=self.colors["bg"])
        self.top_bar = tk.Frame(self.root, bg=self.colors["bg"], height=100)
        self.top_bar.pack(fill=tk.X, padx=40, pady=20)
        self.top_bar.pack_propagate(False)

        left_group = tk.Frame(self.top_bar, bg=self.colors["bg"])
        left_group.pack(side=tk.LEFT)

        self.title_lbl = tk.Label(left_group, text=self.translations[self.lang]["library"], 
                                 font=("Segoe UI Variable Display", 28, "bold"), bg=self.colors["bg"], fg=self.colors["fg"])
        self.title_lbl.pack(side=tk.LEFT)

        self.settings_btn = tk.Button(self.top_bar, image=self.icons_cache.get("settings"), bg=self.colors["bg"],
                                     activebackground=self.colors["bg"], bd=0, cursor="hand2", command=self.open_settings)
        self.settings_btn.pack(side=tk.RIGHT, padx=10)

        self.add_btn = tk.Button(
            self.top_bar, text=self.translations[self.lang]["add"], font=("Segoe UI", 10, "bold"),
            bg=self.colors["accent"], fg="#000000", relief="flat", bd=0, padx=25, pady=10, 
            cursor="hand2", command=self.add_game
        )
        self.add_btn.pack(side=tk.RIGHT, padx=20)

        self.container = tk.Frame(self.root, bg=self.colors["bg"])
        self.container.pack(fill="both", expand=True, padx=40)

        self.canvas = tk.Canvas(self.container, bg=self.colors["bg"], highlightthickness=0)
        self.scrollable_frame = tk.Frame(self.canvas, bg=self.colors["bg"])

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))
        self.canvas.pack(side="left", fill="both", expand=True)
        self.root.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def create_modern_input(self, parent, width=400, btn_text=None, btn_cmd=None):
        container = tk.Canvas(parent, bg=self.colors["card"], height=42, width=width, highlightthickness=0)
        container.pack(pady=(5, 15))
        
        def render_bg(e=None):
            container.delete("bg_shape")
            w, h = container.winfo_width(), container.winfo_height()
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle((0, 0, w, h), 10, fill=self.colors["input_bg"])
            photo = ImageTk.PhotoImage(img)
            self.images_ref.append(photo)
            container.create_image(0, 0, image=photo, anchor="nw", tags="bg_shape")
            container.tag_lower("bg_shape")

        entry_w = width - (100 if btn_text else 20)
        ent = tk.Entry(container, bg=self.colors["input_bg"], fg=self.colors["fg"], 
                      insertbackground=self.colors["fg"], relief="flat", font=("Segoe UI", 10), bd=0)
        container.create_window(12, 21, window=ent, anchor="w", width=entry_w)

        if btn_text:
            btn = tk.Button(container, text=btn_text, bg=self.colors["accent"], fg="#000000", 
                           font=("Segoe UI", 8, "bold"), relief="flat", bd=0, cursor="hand2", command=btn_cmd)
            container.create_window(width-5, 21, window=btn, anchor="e", width=80, height=30)

        container.bind("<Configure>", render_bg)
        return ent

    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title(" ")
        win.geometry("500x480")
        win.configure(bg=self.colors["card"])
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        t = self.translations[self.lang]
        tk.Label(win, text=t["settings"], font=("Segoe UI Semibold", 18), bg=self.colors["card"], fg=self.colors["fg"]).pack(pady=25)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Custom.TCombobox", 
                        fieldbackground=self.colors["input_bg"], 
                        background=self.colors["input_bg"], 
                        foreground=self.colors["fg"],
                        darkcolor=self.colors["input_bg"],
                        lightcolor=self.colors["input_bg"],
                        bordercolor=self.colors["input_bg"],
                        arrowcolor=self.colors["accent"])
        
        win.option_add("*TCombobox*Listbox.background", self.colors["input_bg"])
        win.option_add("*TCombobox*Listbox.foreground", self.colors["fg"])
        win.option_add("*TCombobox*Listbox.selectBackground", self.colors["accent"])
        win.option_add("*TCombobox*Listbox.selectForeground", "#000000")
        win.option_add("*TCombobox*Listbox.relief", "flat")
        win.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))

        style.map("Custom.TCombobox", 
                  fieldbackground=[('readonly', self.colors["input_bg"]), ('focus', self.colors["input_bg"])],
                  foreground=[('readonly', self.colors["fg"])])

        tk.Label(win, text=t["lang"].upper(), font=("Segoe UI", 8, "bold"), bg=self.colors["card"], fg=self.colors["text_sec"]).pack(anchor="w", padx=50)
        lang_var = tk.StringVar(value=self.lang)
        lang_cb = ttk.Combobox(win, textvariable=lang_var, values=["RU", "EN"], state="readonly", width=42, style="Custom.TCombobox")
        lang_cb.pack(pady=(5, 20), ipady=5)

        tk.Label(win, text=t["theme"].upper(), font=("Segoe UI", 8, "bold"), bg=self.colors["card"], fg=self.colors["text_sec"]).pack(anchor="w", padx=50)
        theme_var = tk.StringVar(value=self.current_theme_name)
        theme_cb = ttk.Combobox(win, textvariable=theme_var, values=list(self.themes.keys()), state="readonly", width=42, style="Custom.TCombobox")
        theme_cb.pack(pady=(5, 20), ipady=5)

        def apply():
            self.lang = lang_var.get()
            self.current_theme_name = theme_var.get()
            self.colors = self.themes[self.current_theme_name]
            self.save_data()
            self.root.configure(bg=self.colors["bg"])
            self.update_ui_styles()
            self.refresh_grid()
            win.destroy()

        tk.Button(win, text=t["save"], bg=self.colors["accent"], font=("Segoe UI", 10, "bold"),
                 fg="#000000", relief="flat", bd=0, width=28, pady=12, cursor="hand2", command=apply).pack(pady=30)
        
        tk.Label(win, text=f"Build Version {BUILD_VERSION}", font=("Consolas", 9), bg=self.colors["card"], fg=self.colors["text_sec"]).pack(side=tk.BOTTOM, pady=15)

    def update_ui_styles(self):
        t = self.translations[self.lang]
        self.top_bar.config(bg=self.colors["bg"])
        self.title_lbl.config(text=t["library"], bg=self.colors["bg"], fg=self.colors["fg"])
        self.settings_btn.config(bg=self.colors["bg"])
        self.add_btn.config(text=t["add"], bg=self.colors["accent"])
        self.container.config(bg=self.colors["bg"])
        self.canvas.config(bg=self.colors["bg"])
        self.scrollable_frame.config(bg=self.colors["bg"])

    def open_game_edit(self, index):
        game = self.games[index]
        win = tk.Toplevel(self.root)
        win.title(" ")
        win.geometry("520x500")
        win.configure(bg=self.colors["card"])
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        
        t = self.translations[self.lang]
        tk.Label(win, text=t["edit"], font=("Segoe UI Semibold", 18), bg=self.colors["card"], fg=self.colors["fg"]).pack(pady=20)
        
        tk.Label(win, text=t["title"], font=("Segoe UI", 8, "bold"), bg=self.colors["card"], fg=self.colors["text_sec"]).pack(anchor="w", padx=60)
        name_ent = self.create_modern_input(win, width=400)
        name_ent.insert(0, game['name'])

        tk.Label(win, text=t["icon_path"], font=("Segoe UI", 8, "bold"), bg=self.colors["card"], fg=self.colors["text_sec"]).pack(anchor="w", padx=60)
        
        def browse_icon():
            path = filedialog.askopenfilename(filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.ico")])
            if path:
                icon_ent.delete(0, tk.END)
                icon_ent.insert(0, path)

        icon_ent = self.create_modern_input(win, width=400, btn_text=t["browse"], btn_cmd=browse_icon)
        icon_ent.insert(0, game.get('custom_icon', ''))

        def save_edit():
            self.games[index]['name'] = name_ent.get()
            self.games[index]['custom_icon'] = icon_ent.get()
            self.save_data()
            self.refresh_grid()
            win.destroy()

        tk.Button(win, text=t["save"], bg=self.colors["accent"], font=("Segoe UI", 10, "bold"), 
                  relief="flat", bd=0, width=32, pady=12, cursor="hand2", command=save_edit).pack(pady=(35, 10))
        
        tk.Button(win, text=t["del"], bg="#ef4444", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", bd=0, width=32, pady=12, cursor="hand2", command=lambda: [self.delete_game(index), win.destroy()]).pack()

    def get_icon(self, game, size=70):
        custom = game.get('custom_icon')
        if custom:
            try:
                if custom.startswith('http'):
                    res = requests.get(custom, timeout=3)
                    img = Image.open(BytesIO(res.content)).convert("RGBA")
                else:
                    img = Image.open(custom).convert("RGBA")
                mask = Image.new("L", (size, size), 0)
                draw = ImageDraw.Draw(mask)
                draw.rounded_rectangle((0, 0, size, size), 18, fill=255)
                img = img.resize((size, size), Image.Resampling.LANCZOS)
                img.putalpha(mask)
                return ImageTk.PhotoImage(img)
            except: pass

        try:
            shell32 = ctypes.windll.shell32
            h_icon = wintypes.HICON()
            res = shell32.ExtractIconExW(game['path'], 0, ctypes.byref(h_icon), None, 1)
            if res > 0 and h_icon.value:
                import win32ui, win32gui
                hdc = win32gui.GetDC(0)
                h_dc = win32ui.CreateDCFromHandle(hdc)
                h_bmp = win32ui.CreateBitmap()
                h_bmp.CreateCompatibleBitmap(h_dc, size, size)
                h_dc_mem = h_dc.CreateCompatibleDC()
                h_dc_mem.SelectObject(h_bmp)
                win32gui.DrawIconEx(h_dc_mem.GetSafeHdc(), 0, 0, h_icon.value, size, size, 0, None, 0x0003)
                bmpinfo = h_bmp.GetInfo()
                bmpstr = h_bmp.GetBitmapBits(True)
                img = Image.frombuffer('RGBA', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRA', 0, 1)
                win32gui.DestroyIcon(h_icon.value)
                mask = Image.new("L", (size, size), 0)
                draw = ImageDraw.Draw(mask)
                draw.rounded_rectangle((0, 0, size, size), 18, fill=255)
                img = img.resize((size, size), Image.Resampling.LANCZOS)
                img.putalpha(mask)
                return ImageTk.PhotoImage(img)
        except: pass
        
        img = Image.new('RGBA', (size, size), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((0,0,size,size), 18, fill=self.colors["bg"])
        return ImageTk.PhotoImage(img)

    def add_game(self):
        file_path = filedialog.askopenfilename(filetypes=[(f"{self.translations[self.lang]['Programs']}", "*.exe")])
        if not file_path: return
        game_name = os.path.splitext(os.path.basename(file_path))[0]
        self.games.append({"name": game_name, "path": file_path, "time_played": 0, "custom_icon": ""})
        self.save_data()
        self.refresh_grid()

    def format_time(self, seconds):
        t = self.translations[self.lang]
        h, m = seconds // 3600, (seconds % 3600) // 60
        return f"{h}{t['h']} {m}{t['m']}" if h > 0 else f"{m}{t['min']}"

    def refresh_grid(self):
        for widget in self.scrollable_frame.winfo_children(): widget.destroy()
        t = self.translations[self.lang]
        self.images_ref = []

        for index, game in enumerate(self.games):
            is_run = game['path'] in self.running_processes
            card_outer = tk.Frame(self.scrollable_frame, bg=self.colors["bg"], pady=8)
            card_outer.pack(fill="x", padx=10)
            
            card = tk.Canvas(card_outer, bg=self.colors["bg"], height=100, highlightthickness=0)
            card.pack(fill="x")
            
            def render_card(c=card, idx=index, g=game, r=is_run):
                c.update()
                w, h = c.winfo_width(), 100
                radius = 22
                
                img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                draw.rounded_rectangle((0, 0, w, h), radius, fill=self.colors["card"])
                if r: draw.rounded_rectangle((0, 0, w, h), radius, outline=self.colors["accent"], width=2)

                photo = ImageTk.PhotoImage(img)
                self.images_ref.append(photo)
                c.create_image(0, 0, image=photo, anchor="nw")
                
                icon_img = self.get_icon(g)
                self.images_ref.append(icon_img)
                c.create_image(20, 15, image=icon_img, anchor="nw")
                
                c.create_text(110, 35, text=g['name'].upper(), font=("Segoe UI Variable Display", 14, "bold"), fill=self.colors["fg"], anchor="w")
                status_color = self.colors["accent"] if r else self.colors["text_sec"]
                c.create_text(110, 65, text=f"{t['played']} {self.format_time(g['time_played'])}", font=("Segoe UI", 10), fill=status_color, anchor="w")

                btn_frame = tk.Frame(c, bg=self.colors["card"])
                c.create_window(w-30, 50, window=btn_frame, anchor="e")
                
                tk.Button(btn_frame, text=f" {t['play' if not r else 'running']}", 
                         image=self.icons_cache.get("pause") if r else None, compound="left",
                         font=("Segoe UI", 9, "bold"), bg=self.colors["accent"] if not r else "#334155", 
                         fg="#000000" if not r else "#ffffff", bd=0, padx=25, pady=10, cursor="hand2",
                         command=lambda p=g['path']: self.launch_game(p)).pack(side=tk.LEFT, padx=10)
                
                tk.Button(btn_frame, image=self.icons_cache.get("settings"), bg=self.colors["card"], 
                         activebackground=self.colors["card"], bd=0, cursor="hand2", 
                         command=lambda i=idx: self.open_game_edit(i)).pack(side=tk.LEFT, padx=10)

            card.bind("<Configure>", lambda e, c=card: render_card(c))

    def delete_game(self, index):
        self.games.pop(index)
        self.save_data()
        self.refresh_grid()

    def launch_game(self, exe_path):
        if exe_path in self.running_processes: return
        try:
            proc = subprocess.Popen(exe_path, cwd=os.path.dirname(exe_path))
            self.running_processes[exe_path] = True
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
        if exe_path in self.running_processes: del self.running_processes[exe_path]
        self.root.after(0, self.refresh_grid)

if __name__ == "__main__":
    root = tk.Tk()
    try:
        from ctypes import windll
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_ROUND = 2
        windll.dwmapi.DwmSetWindowAttribute(windll.user32.GetParent(root.winfo_id()), DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(ctypes.c_int(DWMWCP_ROUND)), 4)
    except: pass
    app = GameLauncher(root)
    root.mainloop()
