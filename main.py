import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
import sys
import subprocess
import time
import threading
import psutil
from PIL import Image, ImageTk, ImageDraw
import ctypes
from ctypes import wintypes

class GameLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("TimeGManagment")
        self.root.geometry("1000x750")
        
        if getattr(sys, 'frozen', False):
            self.base_path = os.path.dirname(sys.executable)
        else:
            self.base_path = os.path.dirname(os.path.abspath(__file__))
            
        self.db_file = os.path.join(self.base_path, "data.json")
        self.games = self.load_data()
        self.running_processes = {}

        self.setup_ui()
        self.refresh_grid()

    def load_data(self):
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_data(self):
        try:
            with open(self.db_file, "w", encoding="utf-8") as f:
                json.dump(self.games, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving: {e}")

    def setup_ui(self):
        self.root.configure(bg="#0f111a")
        
        self.top_bar = tk.Frame(self.root, bg="#1a1d2b", height=80)
        self.top_bar.pack(fill=tk.X, padx=0, pady=0)
        self.top_bar.pack_propagate(False)

        title_lbl = tk.Label(self.top_bar, text="My Library", font=("Segoe UI", 18, "bold"), bg="#1a1d2b", fg="#ffffff")
        title_lbl.pack(side=tk.LEFT, padx=30, pady=20)
        
        self.add_btn = tk.Button(
            self.top_bar, text="+ ADD GAME", font=("Segoe UI", 10, "bold"),
            bg="#24293e", fg="#00d4ff", activebackground="#00d4ff", activeforeground="#ffffff",
            relief="flat", bd=0, padx=20, cursor="hand2", command=self.add_game
        )
        self.add_btn.pack(side=tk.RIGHT, padx=30, pady=20)

        self.container = tk.Frame(self.root, bg="#0f111a")
        self.container.pack(fill="both", expand=True, padx=20, pady=10)

        self.canvas = tk.Canvas(self.container, bg="#0f111a", highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self.container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="#0f111a")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))

        self.canvas.pack(side="left", fill="both", expand=True)
        self.root.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def get_icon(self, exe_path, size=64):
        try:
            shell32 = ctypes.windll.shell32
            h_icon = wintypes.HICON()
            res = shell32.ExtractIconExW(exe_path, 0, ctypes.byref(h_icon), None, 1)
            
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
                return ImageTk.PhotoImage(img.resize((size, size), Image.Resampling.LANCZOS))
        except:
            pass
        
        img = Image.new('RGBA', (size, size), color=(36, 41, 62))
        draw = ImageDraw.Draw(img)
        draw.rectangle([10, 10, size-10, size-10], fill=(60, 70, 100))
        return ImageTk.PhotoImage(img)

    def add_game(self):
        file_path = filedialog.askopenfilename(filetypes=[("Programs", "*.exe")])
        if not file_path: return
        game_name = os.path.splitext(os.path.basename(file_path))[0]
        if any(g['path'] == file_path for g in self.games): return
        self.games.append({"name": game_name, "path": file_path, "time_played": 0})
        self.save_data()
        self.refresh_grid()

    def format_time(self, seconds):
        h = seconds // 3600
        m = (seconds % 3600) // 60
        if h > 0: return f"{h} h. {m} m."
        return f"{m} мин."

    def refresh_grid(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        for index, game in enumerate(self.games):
            card = tk.Frame(self.scrollable_frame, bg="#1a1d2b", padx=15, pady=15, highlightthickness=0)
            card.pack(fill="x", padx=10, pady=8)

            icon = self.get_icon(game['path'])
            icon_lbl = tk.Label(card, image=icon, bg="#1a1d2b")
            icon_lbl.image = icon
            icon_lbl.pack(side=tk.LEFT)

            info = tk.Frame(card, bg="#1a1d2b")
            info.pack(side=tk.LEFT, padx=20)

            tk.Label(info, text=game['name'].upper(), font=("Segoe UI", 13, "bold"), bg="#1a1d2b", fg="#ffffff").pack(anchor="w")
            
            status_color = "#00d4ff" if game['path'] in self.running_processes else "#888888"
            time_txt = f"You played: {self.format_time(game['time_played'])}"
            time_lbl = tk.Label(info, text=time_txt, font=("Segoe UI", 9), bg="#1a1d2b", fg=status_color)
            time_lbl.pack(anchor="w", pady=(5, 0))

            btns = tk.Frame(card, bg="#1a1d2b")
            btns.pack(side=tk.RIGHT)

            is_run = game['path'] in self.running_processes
            
            if is_run:
                play_bg = "#80b3ff"
                play_text = "RUNNING"
                play_state = "disabled"
            else:
                play_bg = "#0066ff"
                play_text = "PLAY"
                play_state = "normal"
            
            play_btn = tk.Button(
                btns, text=play_text, 
                font=("Segoe UI", 10, "bold"), width=12,
                bg=play_bg, fg="white", activebackground="#0052cc", activeforeground="white",
                relief="flat", bd=0, pady=8, cursor="hand2",
                state=play_state,
                command=lambda p=game['path'], l=time_lbl: self.launch_game(p, l)
            )
            play_btn.pack(side=tk.LEFT, padx=10)

            del_btn = tk.Button(
                btns, text="DELETE", 
                font=("Segoe UI", 10, "bold"),
                bg="#ff3333", fg="white", activebackground="#cc0000", activeforeground="white",
                relief="flat", bd=0, padx=15, pady=8, cursor="hand2",
                command=lambda i=index: self.delete_game(i)
            )
            del_btn.pack(side=tk.LEFT)

    def delete_game(self, index):
        self.games.pop(index)
        self.save_data()
        self.refresh_grid()

    def launch_game(self, exe_path, label_widget):
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
        while True:
            try:
                if not psutil.pid_exists(proc.pid): break
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
        if exe_path in self.running_processes:
            del self.running_processes[exe_path]
        self.root.after(0, self.refresh_grid)

if __name__ == "__main__":
    root = tk.Tk()
    app = GameLauncher(root)
    root.mainloop()
