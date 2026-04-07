import customtkinter as ctk
import os
import sys
import json

# 確保路徑正確以匯入 settings
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from src.python.launcher_settings import SettingsManager
except ImportError as e:
    print(f"❌ 匯入失敗: {e}")
    sys.exit(1)

class LauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 1. 載入設定
        self.settings_mgr = SettingsManager()
        
        # 2. 設定視窗基礎屬性
        self.title("BattleLite Launcher")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 恢復上次的位置與大小
        size = self.settings_mgr.get("window_size")
        pos = self.settings_mgr.get("window_pos")
        self.geometry(f"{size[0]}x{size[1]}+{pos[0]}+{pos[1]}")
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # 3. 佈局 UI 元件
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 主容器
        self.main_frame = ctk.CTkFrame(self, corner_radius=10)
        self.main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)

        # 標題
        self.label_title = ctk.CTkLabel(self.main_frame, text="BATTLE LITE", font=ctk.CTkFont(size=32, weight="bold"))
        self.label_title.grid(row=0, column=0, padx=20, pady=(20, 10))

        # 暱稱輸入
        self.entry_nickname = ctk.CTkEntry(self.main_frame, placeholder_text="Enter Nickname", width=250)
        self.entry_nickname.insert(0, self.settings_mgr.get("nickname"))
        self.entry_nickname.grid(row=1, column=0, padx=20, pady=10)

        # 房間碼輸入
        self.entry_room = ctk.CTkEntry(self.main_frame, placeholder_text="Enter Room Code (e.g. LF2_BATTLE)", width=250)
        self.entry_room.insert(0, self.settings_mgr.get("last_room"))
        self.entry_room.grid(row=2, column=0, padx=20, pady=10)

        # 模式切換按鈕 (目前僅顯示)
        self.btn_mode = ctk.CTkSegmentedButton(self.main_frame, values=["Online P2P", "Offline Dev"])
        self.btn_mode.set("Offline Dev")
        self.btn_mode.grid(row=3, column=0, padx=20, pady=10)

        # 開始遊戲按鈕
        self.btn_start = ctk.CTkButton(self.main_frame, text="START GAME", font=ctk.CTkFont(size=18, weight="bold"),
                                       command=self.start_game_action, height=45)
        self.btn_start.grid(row=4, column=0, padx=20, pady=30)

        # 底部狀態列
        self.label_status = ctk.CTkLabel(self.main_frame, text="Ready to fight.", font=ctk.CTkFont(size=12))
        self.label_status.grid(row=5, column=0, padx=20, pady=10)

    def start_game_action(self):
        nickname = self.entry_nickname.get()
        room = self.entry_room.get()
        mode = self.btn_mode.get()
        
        self.label_status.configure(text=f"Launching {mode} for {nickname} in room {room}...")
        print(f"🚀 Launching Game: Nickname={nickname}, Room={room}, Mode={mode}")
        
        # 保存當前輸入
        self.settings_mgr.set("nickname", nickname)
        self.settings_mgr.set("last_room", room)
        self.settings_mgr.save()
        
        # 暫時：我們還沒實作進程啟動邏輯，先只印出資訊
        # self.withdraw() # 隱藏 Launcher

    def on_closing(self):
        """關閉視窗時保存位置與大小。"""
        # 獲取當前幾何資訊
        geo = self.geometry().split('+')
        size = geo[0].split('x')
        pos_x, pos_y = geo[1], geo[2]
        
        self.settings_mgr.set("window_size", [int(size[0]), int(size[1])])
        self.settings_mgr.set("window_pos", [int(pos_x), int(pos_y)])
        self.settings_mgr.set("nickname", self.entry_nickname.get())
        self.settings_mgr.set("last_room", self.entry_room.get())
        
        self.settings_mgr.save()
        print("💾 Settings saved. Goodbye!")
        self.destroy()

if __name__ == "__main__":
    app = LauncherApp()
    app.mainloop()
