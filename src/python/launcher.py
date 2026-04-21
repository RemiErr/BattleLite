from dotenv import load_dotenv
import customtkinter as ctk
import os
import sys
import json
import subprocess
import threading
import asyncio
import socket
import time

# 確保路徑正確
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from src.python.launcher_settings import SettingsManager
    from src.python.crypto_utils import encrypt_payload
    from src.python.stun_utils import probe_stun_on_sock, get_local_ip
    from src.python.lobby_client import LobbyClient
except ImportError as e:
    print(f"❌ 匯入失敗: {e}")
    sys.exit(1)

load_dotenv()

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

        self.grid_columnconfigure(0, weight=1)
        self.main_frame = ctk.CTkFrame(self, corner_radius=10)
        self.main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.main_frame, text="BATTLE LITE", font=ctk.CTkFont(
            size=32, weight="bold")).grid(row=0, column=0, pady=20)

        self.entry_nickname = ctk.CTkEntry(
            self.main_frame, placeholder_text="Nickname", width=250)
        self.entry_nickname.insert(0, self.settings_mgr.get("nickname"))
        self.entry_nickname.grid(row=1, column=0, pady=10)

        self.entry_room = ctk.CTkEntry(
            self.main_frame, placeholder_text="Room Code", width=250)
        self.entry_room.insert(0, self.settings_mgr.get("last_room"))
        self.entry_room.grid(row=2, column=0, pady=10)

        self.btn_mode = ctk.CTkSegmentedButton(
            self.main_frame, values=["Online P2P", "Offline Dev"])
        self.btn_mode.set("Offline Dev")
        self.btn_mode.grid(row=3, column=0, pady=10)

        self.btn_start = ctk.CTkButton(self.main_frame, text="START GAME",
                                       font=ctk.CTkFont(size=18, weight="bold"),
                                       command=self.on_start_clicked, height=45)
        self.btn_start.grid(row=4, column=0, padx=20, pady=30)

        self.label_status = ctk.CTkLabel(
            self.main_frame, text="Ready.", font=ctk.CTkFont(size=12))
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
        if self.game_process:
            return
        self.btn_start.configure(state="disabled", text="CONNECTING...")
        self.update_status("Searching for free UDP port...")
        self.lobby_thread = threading.Thread(
            target=self.run_async_lobby, daemon=True)
        self.lobby_thread.start()

    # --- Punch loop (背景執行緒) ---

    def _punch_loop(self, sock: socket.socket, remotes: list, stop_event: threading.Event):
        """持續向所有 remote 發 UDP 封包，直到 stop_event 被設置。"""
        count = 0
        while not stop_event.is_set():
            for ip, port in remotes:
                try:
                    sock.sendto(b'\x00', (ip, port))
                except Exception:
                    pass
            count += 1
            time.sleep(0.1)  # 10 輪/秒
        print(f"  [punch] 結束，共發送 {count} 輪")

    # --- Async lobby flow ---

    def run_async_lobby(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.async_lobby_task())
        finally:
            pending = asyncio.all_tasks(self.loop)
            if pending:
                self.loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True))
            self.loop.close()

    async def async_lobby_task(self):
        nickname = self.entry_nickname.get()
        room = self.entry_room.get()

        # 1. 找可用 local port
        local_port = 5000
        for p in range(5000, 5020):
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                test_sock.bind(('0.0.0.0', p))
                test_sock.close()
                local_port = p
                break
            except OSError:
                test_sock.close()

        # 2. 建立並保持 UDP socket（方案二：不在 STUN 後關閉）
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_sock.bind(('0.0.0.0', local_port))

        try:
            loop = asyncio.get_event_loop()
            pub_ip, pub_port = await loop.run_in_executor(
                None, lambda: probe_stun_on_sock(udp_sock))
            self.update_status(f"NAT Probe: {pub_ip}:{pub_port}")
            print(f"  [stun] local={local_port}  public={pub_ip}:{pub_port}")
        except Exception as e:
            udp_sock.close()
            self.update_status(f"STUN Failed: {e}")
            self.after(2000, self.reset_ui_to_idle)
            return

        # 3. 連線大廳
        client = LobbyClient(server_url=LOBBY_SERVER_URL)
        if not await client.join_room(room, nickname):
            udp_sock.close()
            self.update_status("Lobby Server offline.")
            self.after(2000, self.reset_ui_to_idle)
            return

        # 4. 回報公網 + 私有 endpoint（供同 LAN 直連判斷使用）
        local_ip = get_local_ip()
        await client.send_data({
            "type": "report_endpoint",
            "pub_ip": pub_ip, "pub_port": pub_port,
            "local_ip": local_ip, "local_port": local_port,
        })
        print(f"  [report] pub={pub_ip}:{pub_port}  lan={local_ip}:{local_port}")
        self.update_status("Waiting for opponent...")

        # 5. 監聽大廳訊息（方案三：新協議 punch_start / game_start）
        punch_stop = threading.Event()
        punch_thread = None

        try:
            async for msg in client.listen():

                if msg["type"] == "punch_start":
                    my_id = next((p["id"] for p in msg["players"] if p["name"] == nickname), 0)
                    my_pub_ip = next((p["pub_ip"] for p in msg["players"] if p["id"] == my_id), pub_ip)
                    remotes = [
                        # 同公網 IP → 同 LAN → 用私有 IP 直連，避免 NAT hairpin 失敗
                        (p["local_ip"], p["local_port"]) if p["pub_ip"] == my_pub_ip
                        else (p["pub_ip"], p["pub_port"])
                        for p in msg["players"]
                        if p["id"] != my_id and p["pub_port"] != 0
                    ]
                    print(f"  [punch_start] my_id={my_id}  remotes={remotes}")
                    punch_stop.clear()
                    punch_thread = threading.Thread(
                        target=self._punch_loop,
                        args=(udp_sock, remotes, punch_stop),
                        daemon=True
                    )
                    punch_thread.start()
                    self.update_status("Punching NAT holes...")

                elif msg["type"] == "game_start":
                    punch_stop.set()
                    if punch_thread:
                        punch_thread.join(timeout=1.0)
                    udp_sock.close()

                    my_id = next((p["id"] for p in msg["players"] if p["name"] == nickname), 0)
                    my_pub_ip = next((p["pub_ip"] for p in msg["players"] if p["id"] == my_id), "")

                    # 為每位玩家決定 GGRS 實際要連線的 IP:port
                    resolved_players = []
                    for p in msg["players"]:
                        if p["pub_ip"] == my_pub_ip and p["id"] != my_id:
                            # 同 LAN → 私有 IP 直連
                            eff_ip, eff_port = p["local_ip"], p["local_port"]
                        else:
                            eff_ip, eff_port = p["pub_ip"], p["pub_port"]
                        resolved_players.append({**p, "ip": eff_ip, "port": eff_port})
                        tag = "← me" if p["id"] == my_id else "→ remote"
                        print(f"  [resolve] id={p['id']} {eff_ip}:{eff_port}  {tag}")

                    session_data = {
                        "nickname": nickname,
                        "room": room,
                        "is_offline": False,
                        "local_id": my_id,
                        "local_port": local_port,
                        "num_players": len(msg["players"]),
                        "players": resolved_players,
                        "seed": msg["seed"]
                    }
                    await client.close()
                    # 給 OS 50ms 釋放 port 再讓 GGRS 綁定
                    self.after(50, lambda sd=session_data: self.do_launch(sd))
                    break

        except Exception as e:
            punch_stop.set()
            udp_sock.close()
            self.update_status(f"Lobby error: {e}")
            self.after(2000, self.reset_ui_to_idle)

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
            self.game_process = subprocess.Popen(
                [sys.executable, game_script, "--payload", payload],
                env=os.environ.copy()
            )
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
