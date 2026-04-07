import customtkinter as ctk
import os
import sys
import json
import subprocess
import threading
import asyncio
import socket

# 確保路徑正確
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from src.python.launcher_settings import SettingsManager
    from src.python.crypto_utils import encrypt_payload
    from src.python.stun_utils import get_public_endpoint
    from src.python.lobby_client import LobbyClient
except ImportError as e:
    print(f"❌ 匯入失敗: {e}")
    sys.exit(1)

from dotenv import load_dotenv
load_dotenv() # 載入根目錄的 .env

# 設定大廳伺服器位址 (優先讀取環境變數)
LOBBY_SERVER_URL = os.getenv("LOBBY_SERVER_URL", "ws://localhost:8000")

class LauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.settings_mgr = SettingsManager()
        self.title("BattleLite Launcher")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        size = self.settings_mgr.get("window_size")
        pos = self.settings_mgr.get("window_pos")
        self.geometry(f"{size[0]}x{size[1]}+{pos[0]}+{pos[1]}")
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.game_process = None
        self.lobby_thread = None
        self.loop = None

        # --- UI 佈局 ---
        self.grid_columnconfigure(0, weight=1)
        self.main_frame = ctk.CTkFrame(self, corner_radius=10)
        self.main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.main_frame, text="BATTLE LITE", font=ctk.CTkFont(size=32, weight="bold")).grid(row=0, column=0, pady=20)

        self.entry_nickname = ctk.CTkEntry(self.main_frame, placeholder_text="Nickname", width=250)
        self.entry_nickname.insert(0, self.settings_mgr.get("nickname"))
        self.entry_nickname.grid(row=1, column=0, pady=10)

        self.entry_room = ctk.CTkEntry(self.main_frame, placeholder_text="Room Code", width=250)
        self.entry_room.insert(0, self.settings_mgr.get("last_room"))
        self.entry_room.grid(row=2, column=0, pady=10)

        self.btn_mode = ctk.CTkSegmentedButton(self.main_frame, values=["Online P2P", "Offline Dev"])
        self.btn_mode.set("Offline Dev")
        self.btn_mode.grid(row=3, column=0, pady=10)

        self.btn_start = ctk.CTkButton(self.main_frame, text="START GAME", font=ctk.CTkFont(size=18, weight="bold"),
                                       command=self.on_start_clicked, height=45)
        self.btn_start.grid(row=4, column=0, padx=20, pady=30)

        self.label_status = ctk.CTkLabel(self.main_frame, text="Ready.", font=ctk.CTkFont(size=12))
        self.label_status.grid(row=5, column=0, padx=20, pady=10)

    def on_start_clicked(self):
        mode = self.btn_mode.get()
        if mode == "Offline Dev":
            self.launch_game_offline()
        else:
            self.start_online_flow()

    def launch_game_offline(self):
        session_data = {
            "nickname": self.entry_nickname.get(),
            "room": "offline",
            "is_offline": True,
            "local_id": 0,
            "local_port": 5000,
            "num_players": 4
        }
        self.do_launch(session_data)

    def start_online_flow(self):
        if self.game_process: return
        self.btn_start.configure(state="disabled", text="CONNECTING...")
        self.update_status("Searching for free UDP port...")
        
        self.lobby_thread = threading.Thread(target=self.run_async_lobby, daemon=True)
        self.lobby_thread.start()

    def run_async_lobby(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.async_lobby_task())

    async def async_lobby_task(self):
        nickname = self.entry_nickname.get()
        room = self.entry_room.get()
        
        # 1. 尋找可用的本地埠號 (解決 Address already in use)
        local_port = 5000
        for p in range(5000, 5020):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                try:
                    s.bind(('0.0.0.0', p))
                    local_port = p
                    break
                except: continue

        # 2. STUN 探測
        try:
            pub_ip, pub_port = get_public_endpoint(local_port)
            self.update_status(f"NAT Probe: {pub_ip}:{pub_port}")
        except Exception as e:
            self.update_status(f"STUN Failed: {e}")
            self.after(2000, self.reset_ui_to_idle)
            return

        # 3. 連線大廳
        client = LobbyClient(server_url=LOBBY_SERVER_URL)
        if not await client.join_room(room, nickname):
            self.update_status("Lobby Server offline.")
            self.after(2000, self.reset_ui_to_idle)
            return

        # 4. 回報
        await client.send_data({"type": "report_endpoint", "ip": pub_ip, "port": pub_port})
        self.update_status("Waiting for opponent...")

        # 5. 監聽
        async for msg in client.listen():
            if msg["type"] == "start_match":
                my_id = 0
                for p in msg["players"]:
                    if p["name"] == nickname: my_id = p["id"]
                
                session_data = {
                    "nickname": nickname,
                    "room": room,
                    "is_offline": False,
                    "local_id": my_id,
                    "local_port": local_port,
                    "num_players": len(msg["players"]),
                    "players": msg["players"],
                    "seed": msg["seed"]
                }
                await client.close()
                self.after(100, lambda: self.do_launch(session_data))
                break

    def reset_ui_to_idle(self):
        self.btn_start.configure(state="normal", text="START GAME")
        self.label_status.configure(text="Ready.")

    def update_status(self, text):
        self.after(0, lambda: self.label_status.configure(text=text))

    def do_launch(self, session_data):
        payload = encrypt_payload(session_data)
        self.settings_mgr.set("nickname", session_data["nickname"])
        self.settings_mgr.set("last_room", session_data["room"])
        self.settings_mgr.save()
        
        try:
            game_script = os.path.join(PROJECT_ROOT, "src", "python", "main.py")
            self.game_process = subprocess.Popen([sys.executable, game_script, "--payload", payload])
            self.iconify()
            self.monitor_game_process()
        except Exception as e:
            self.reset_ui(f"Launch Error: {e}")

    def monitor_game_process(self):
        if self.game_process and self.game_process.poll() is not None:
            self.reset_ui("Game ended.")
            self.deiconify()
        else:
            self.after(1000, self.monitor_game_process)

    def reset_ui(self, message):
        self.btn_start.configure(state="normal", text="START GAME")
        self.label_status.configure(text=message)
        self.game_process = None

    def on_closing(self):
        self.settings_mgr.save()
        self.destroy()

if __name__ == "__main__":
    app = LauncherApp()
    app.mainloop()
