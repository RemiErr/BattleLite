import customtkinter as ctk
import os
import sys
import json
import subprocess

# 確保路徑正確
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from src.python.launcher_settings import SettingsManager
    from src.python.crypto_utils import encrypt_payload
except ImportError as e:
    print(f"❌ 匯入失敗: {e}")
    sys.exit(1)

class LauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.settings_mgr = SettingsManager()
        self.title("BattleLite Launcher")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 恢復設定
        size = self.settings_mgr.get("window_size")
        pos = self.settings_mgr.get("window_pos")
        self.geometry(f"{size[0]}x{size[1]}+{pos[0]}+{pos[1]}")
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # 遊戲進程追蹤
        self.game_process = None

        # --- UI 佈局 ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.main_frame = ctk.CTkFrame(self, corner_radius=10)
        self.main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)

        self.label_title = ctk.CTkLabel(self.main_frame, text="BATTLE LITE", font=ctk.CTkFont(size=32, weight="bold"))
        self.label_title.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.entry_nickname = ctk.CTkEntry(self.main_frame, placeholder_text="Enter Nickname", width=250)
        self.entry_nickname.insert(0, self.settings_mgr.get("nickname"))
        self.entry_nickname.grid(row=1, column=0, padx=20, pady=10)

        self.entry_room = ctk.CTkEntry(self.main_frame, placeholder_text="Enter Room Code", width=250)
        self.entry_room.insert(0, self.settings_mgr.get("last_room"))
        self.entry_room.grid(row=2, column=0, padx=20, pady=10)

        self.btn_mode = ctk.CTkSegmentedButton(self.main_frame, values=["Online P2P", "Offline Dev"])
        self.btn_mode.set("Offline Dev")
        self.btn_mode.grid(row=3, column=0, padx=20, pady=10)

        self.btn_start = ctk.CTkButton(self.main_frame, text="START GAME", font=ctk.CTkFont(size=18, weight="bold"),
                                       command=self.start_game_action, height=45)
        self.btn_start.grid(row=4, column=0, padx=20, pady=30)

        self.label_status = ctk.CTkLabel(self.main_frame, text="Ready to fight.", font=ctk.CTkFont(size=12))
        self.label_status.grid(row=5, column=0, padx=20, pady=10)

    def start_game_action(self):
        if self.game_process and self.game_process.poll() is None:
            return # 遊戲還在跑，禁止重複啟動

        nickname = self.entry_nickname.get()
        room = self.entry_room.get()
        mode = self.btn_mode.get()
        
        session_data = {
            "nickname": nickname, "room": room,
            "is_offline": (mode == "Offline Dev"),
            "local_id": 0, "num_players": 4
        }
        
        payload = encrypt_payload(session_data)
        
        # 禁用按鈕與顯示狀態
        self.btn_start.configure(state="disabled", text="GAME RUNNING")
        self.label_status.configure(text=f"Game session active...")
        
        try:
            game_script = os.path.join(PROJECT_ROOT, "src", "python", "main.py")
            self.game_process = subprocess.Popen([sys.executable, game_script, "--payload", payload])
            self.iconify()
            # 開始監控進程
            self.monitor_game_process()
        except Exception as e:
            self.reset_ui(f"Error: {e}")

    def monitor_game_process(self):
        """定期檢查遊戲是否已關閉。"""
        if self.game_process:
            if self.game_process.poll() is not None:
                # 遊戲已結束
                self.reset_ui("Welcome back! Game ended.")
                self.deiconify() # 彈回視窗
            else:
                # 每隔 1 秒檢查一次
                self.after(1000, self.monitor_game_process)

    def reset_ui(self, message):
        """還原 Launcher 介面狀態。"""
        self.btn_start.configure(state="normal", text="START GAME")
        self.label_status.configure(text=message)
        self.game_process = None

    def on_closing(self):
        # 關閉時若遊戲還在跑，先關閉遊戲 (可選，這裡我們先採溫和策略)
        geo = self.geometry().split('+')
        size = geo[0].split('x')
        self.settings_mgr.set("window_size", [int(size[0]), int(size[1])])
        self.settings_mgr.set("window_pos", [int(geo[1]), int(geo[2])])
        self.settings_mgr.set("nickname", self.entry_nickname.get())
        self.settings_mgr.set("last_room", self.entry_room.get())
        self.settings_mgr.save()
        self.destroy()

if __name__ == "__main__":
    app = LauncherApp()
    app.mainloop()
