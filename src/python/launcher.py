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
import random
import string
import urllib.request
import urllib.parse

if getattr(sys, 'frozen', False):
    PROJECT_ROOT = sys._MEIPASS
else:
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
    print(f"[ERR] 匯入失敗: {e}")
    sys.exit(1)

load_dotenv()

_use_local = os.getenv("LOBBY_USE_LOCAL", "false").lower() == "true"
LOBBY_WS_URL = (
    os.getenv("LOBBY_SERVER_URL_LOCAL", "ws://localhost:8000") if _use_local
    else os.getenv("LOBBY_SERVER_URL_CLOUD", "ws://localhost:8000")
)
LOBBY_HTTP_URL = LOBBY_WS_URL.replace(
    "ws://", "http://").replace("wss://", "https://")

CHAR_NAMES = ["Knight", "Mage", "Archer", "Paladin", "Wizard"]
_WIN_W, _WIN_H = 600, 400
_TIER_LABELS = {
    "placement": "定位賽",
    "bronze":    "銅牌",
    "silver":    "銀牌",
    "gold":      "金牌",
}


_FONTS_DIR = os.path.join(PROJECT_ROOT, "src", "assets", "fonts")
_FC_TMP_CONF: str | None = None

_CJK_FONT = "Noto Sans TC"


def _font(size: int, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=_CJK_FONT, size=size, weight=weight)


def _setup_project_font() -> None:
    """點 Tk 初始化前，透過 fontconfig 臨時 config 載入專案內的字型目錄。"""
    global _FC_TMP_CONF
    if not os.path.isdir(_FONTS_DIR):
        return
    has_font = any(f.lower().endswith((".ttf", ".otf", ".ttc"))
                   for f in os.listdir(_FONTS_DIR))
    if not has_font:
        return

    import tempfile
    conf = (
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n'
        '<fontconfig>\n'
        f'  <dir>{_FONTS_DIR}</dir>\n'
        '  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>\n'
        '</fontconfig>\n'
    )
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False)
    tmp.write(conf)
    tmp.close()
    _FC_TMP_CONF = tmp.name
    os.environ["FONTCONFIG_FILE"] = tmp.name


def _gen_room_code(length: int = 6) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


# ── 常數 ─────────────────────────────────────────────────────────────────

_PRESET_LABELS = ["方向鍵 + Z/X", "WASD + J/K"]


# ── 主應用程式 ────────────────────────────────────────────────────────────

class LauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.settings_mgr = SettingsManager()
        self.title("BattleLite Launcher")
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        pos = self.settings_mgr.get("window_pos")
        self.resizable(False, False)
        self.geometry(f"{_WIN_W}x{_WIN_H}+{pos[0]}+{pos[1]}")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Launcher icon
        icon_path = os.path.join(PROJECT_ROOT, "src/assets/img/launcher.ico")
        if os.path.exists(icon_path):
            try:
                self.wm_iconbitmap(icon_path)
                print("[INFO] Launcher window icon set successfully.")
            except Exception as e:
                print(f"[WARN] Failed to set launcher window icon: {e}")
        else:
            print(f"[WARN] Launcher icon not found at: {icon_path}")

        # 連線狀態
        self.game_process = None
        self.lobby_thread: threading.Thread | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self._client: LobbyClient | None = None
        self._udp_sock: socket.socket | None = None
        self._punch_stop = threading.Event()
        self._queue_cancelled = False

        # 房間狀態
        self._my_id = 0
        self._is_host = False
        self._is_queue = False
        self._room_id = ""
        self._local_ct = 0    # 本玩家選的 char_type
        self._room_data: dict = {}  # 最後一次 room_update 快取，供樂觀更新使用
        self._tier_cache: dict[str, str] = {}  # nickname → tier，由排行榜資料填入
        # pid → {"char_type": int, "level": int}
        self._ai_players: dict[int, dict] = {}

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_main_frame()
        self._build_room_frame()
        self._build_settings_frame()
        self._build_leaderboard_frame()
        self._build_offline_frame()
        self._build_replay_frame()
        self._show_main()
        self._poll_online()
        self.bind_all(
            "<Button-1>",
            func=lambda event: event.widget.focus_set()
            if hasattr(event.widget, "focus_set") else None)

    # ── Main Frame ────────────────────────────────────────────────────────

    def _build_main_frame(self):
        f = ctk.CTkFrame(self, corner_radius=10)
        f.grid_columnconfigure(0, weight=1)
        self.main_frame = f

        ctk.CTkLabel(f, text="BATTLE LITE",
                     font=_font(32, "bold")).grid(
            row=0, column=0, pady=(20, 4))

        self._lbl_online_main = ctk.CTkLabel(f, text="Online: -",
                                             font=_font(12))
        self._lbl_online_main.grid(row=1, column=0)

        self.entry_nickname = ctk.CTkEntry(
            f, placeholder_text="Nickname", width=260)
        self.entry_nickname.insert(0, self.settings_mgr.get("nickname"))
        self.entry_nickname.grid(row=2, column=0, pady=12)

        # 線上按鈕列
        btn_grid = ctk.CTkFrame(f, fg_color="transparent")
        btn_grid.grid(row=3, column=0, pady=4)
        ctk.CTkButton(btn_grid, text="牌位賽", width=130,
                      command=self._on_queue).grid(
            row=0, column=0, padx=5, pady=4)
        ctk.CTkButton(btn_grid, text="自訂房間", width=130,
                      command=self._on_create).grid(
            row=0, column=1, padx=5, pady=4)
        self._entry_room = ctk.CTkEntry(
            btn_grid, placeholder_text="請輸入房間碼", width=130)
        self._entry_room.grid(row=1, column=0, padx=5, pady=4)
        ctk.CTkButton(btn_grid, text="加入", width=130,
                      command=self._on_join_click).grid(
            row=1, column=1, padx=5, pady=4)

        ctk.CTkButton(f, text="離線模式", fg_color="gray40",
                      command=self._on_offline).grid(row=5, column=0, pady=6)

        bot_row = ctk.CTkFrame(f, fg_color="transparent")
        bot_row.grid(row=6, column=0, pady=2)
        ctk.CTkButton(bot_row, text="設定", width=80, fg_color="gray30",
                      command=self._show_settings).grid(row=0, column=0, padx=4)
        ctk.CTkButton(bot_row, text="排行榜", width=80, fg_color="gray30",
                      command=self._show_leaderboard).grid(row=0, column=1, padx=4)
        ctk.CTkButton(bot_row, text="對戰紀錄", width=80, fg_color="gray30",
                      command=self._show_replay).grid(row=0, column=2, padx=4)

        self._lbl_status_main = ctk.CTkLabel(
            f, text="Ready.", font=_font(12))
        self._lbl_status_main.grid(row=7, column=0, pady=10)

    # ── Settings Frame ────────────────────────────────────────────────────

    def _build_settings_frame(self):
        f = ctk.CTkFrame(self, corner_radius=10)
        f.grid_columnconfigure(0, weight=1)
        self.settings_frame = f

        hdr = ctk.CTkFrame(f, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="ew")
        hdr.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(hdr, text="← 返回", width=80, fg_color="gray30",
                      command=self._show_main).grid(row=0, column=0)
        ctk.CTkLabel(hdr, text="設定",
                     font=_font(16, "bold")).grid(row=0, column=1, padx=10)
        ctk.CTkFrame(hdr, fg_color="transparent", width=80,
                     height=28).grid(row=0, column=2)

        ctk.CTkLabel(f, text="音量", font=_font(14)).grid(
            row=1, column=0, pady=(24, 4))
        self._settings_vol = ctk.IntVar(value=self.settings_mgr.get("volume"))
        slider = ctk.CTkSlider(f, from_=0, to=100,
                               variable=self._settings_vol, width=260)
        slider.grid(row=2, column=0, pady=4)
        self._settings_vol_lbl = ctk.CTkLabel(
            f, text=f"{self._settings_vol.get()}%")
        self._settings_vol_lbl.grid(row=3, column=0)
        slider.configure(
            command=lambda v: self._settings_vol_lbl.configure(
                text=f"{int(v)}%"))

        ctk.CTkLabel(f, text="按鍵組合", font=_font(14)).grid(
            row=4, column=0, pady=(20, 4))
        self._settings_preset_seg = ctk.CTkSegmentedButton(
            f, values=_PRESET_LABELS, width=260)
        self._settings_preset_seg.set(
            _PRESET_LABELS[self.settings_mgr.get("key_preset")])
        self._settings_preset_seg.grid(row=5, column=0, pady=4)

        bg_row = ctk.CTkFrame(f, fg_color="transparent")
        bg_row.grid(row=6, column=0, pady=(20, 4))
        ctk.CTkLabel(bg_row, text="背景圖", font=_font(14)).pack(side="left", padx=(0, 8))
        self._settings_bg_switch = ctk.CTkSwitch(bg_row, text="")
        self._settings_bg_switch.pack(side="left")
        if self.settings_mgr.get("background_enabled"):
            self._settings_bg_switch.select()
        else:
            self._settings_bg_switch.deselect()

        self._settings_bg_seg = ctk.CTkSegmentedButton(
            f, values=[str(i) for i in range(1, 10)], width=260)
        self._settings_bg_seg.set(str(self.settings_mgr.get("background_id")))
        self._settings_bg_seg.grid(row=7, column=0, pady=4)

        ctk.CTkButton(f, text="儲存", command=self._save_settings).grid(
            row=8, column=0, pady=20)

    # ── Leaderboard Frame ─────────────────────────────────────────────────

    def _build_leaderboard_frame(self):
        f = ctk.CTkFrame(self, corner_radius=10)
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(3, weight=1)
        self.leaderboard_frame = f

        hdr = ctk.CTkFrame(f, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="ew")
        hdr.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(hdr, text="← 返回", width=80, fg_color="gray30",
                      command=self._show_main).grid(row=0, column=0)
        ctk.CTkLabel(hdr, text="排行榜",
                     font=_font(16, "bold")).grid(row=0, column=1, padx=10)
        ctk.CTkButton(hdr, text="↻ 重新整理", width=90, fg_color="gray30",
                      height=28, command=self._refresh_leaderboard).grid(
            row=0, column=2)

        self._lb_status = ctk.CTkLabel(
            f, text="", font=_font(11), text_color="gray60")
        self._lb_status.grid(row=1, column=0, sticky="w", padx=15, pady=(4, 0))

        col_hdr = ctk.CTkFrame(f, fg_color="transparent")
        col_hdr.grid(row=2, column=0, sticky="ew", padx=15, pady=(6, 2))
        for col, (label, w) in enumerate([
                ("#", 30), ("Nickname", 155), ("場", 40),
                ("勝", 40), ("負", 40), ("勝%", 55), ("段位", 60)]):
            ctk.CTkLabel(col_hdr, text=label, width=w, anchor="center",
                         font=_font(11, "bold"),
                         text_color="gray70").grid(row=0, column=col)

        self._lb_scroll = ctk.CTkScrollableFrame(f, fg_color="transparent")
        self._lb_scroll.grid(row=3, column=0, sticky="nsew",
                             padx=15, pady=(0, 15))

    def _do_fetch_leaderboard(self):
        try:
            with urllib.request.urlopen(
                    f"{LOBBY_HTTP_URL}/leaderboard", timeout=5) as r:
                entries = json.loads(r.read()).get("entries", [])
            self.after(0, lambda e=entries: self._render_leaderboard(e))
        except Exception as ex:
            msg = str(ex)
            self.after(0, lambda m=msg: self._lb_status.configure(
                text=f"無法取得資料: {m}"))

    def _render_leaderboard(self, entries: list):
        for e in entries:
            if "nickname" in e and "tier" in e:
                self._tier_cache[e["nickname"]] = e["tier"]

        for w in self._lb_scroll.winfo_children():
            w.destroy()

        WIDTHS = [30, 155, 40, 40, 40, 55, 60]
        for rank, e in enumerate(entries, 1):
            tier_label = _TIER_LABELS.get(e.get("tier", ""), "")
            row_data = [
                str(rank),
                e.get("nickname", ""),
                str(e.get("games", 0)),
                str(e.get("wins", 0)),
                str(e.get("losses", 0)),
                f"{e.get('win_rate', 0.0)}%",
                tier_label,
            ]
            bg = "gray20" if rank % 2 == 0 else "transparent"
            row_frame = ctk.CTkFrame(self._lb_scroll, fg_color=bg,
                                     corner_radius=4)
            row_frame.pack(fill="x", pady=1)
            for col, (text, w) in enumerate(zip(row_data, WIDTHS)):
                anchor = "w" if col == 1 else "center"
                ctk.CTkLabel(row_frame, text=text, width=w, anchor=anchor,
                             font=_font(11)).grid(row=0, column=col)

        count = len(entries)
        self._lb_status.configure(
            text=f"{count} 位玩家" if count else "目前無紀錄")

    # ── Offline Config Frame ──────────────────────────────────────────────

    def _build_offline_frame(self):
        # 預設 AI 配置
        _OFFLINE_DEFAULTS = [
            {"char_type": 0, "level": 1},  # P1
            {"char_type": 0, "level": 1},  # P2
            {"char_type": 0, "level": 1},  # P3
        ]

        f = ctk.CTkFrame(self, corner_radius=10)
        f.grid_columnconfigure(0, weight=1)
        self.offline_frame = f

        hdr = ctk.CTkFrame(f, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="ew")
        hdr.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(hdr, text="← 返回", width=80, fg_color="gray30",
                      command=self._show_main).grid(row=0, column=0)
        ctk.CTkLabel(hdr, text="離線模式設定",
                     font=_font(16, "bold")).grid(row=0, column=1, padx=10)
        ctk.CTkFrame(hdr, fg_color="transparent", width=80,
                     height=28).grid(row=0, column=2)

        size_row = ctk.CTkFrame(f, fg_color="transparent")
        size_row.grid(row=1, column=0, pady=(10, 4))
        ctk.CTkLabel(size_row, text="玩家人數",
                     font=_font(12)).pack(side="left", padx=(0, 8))
        self._offline_size_seg = ctk.CTkSegmentedButton(
            size_row, values=["2人", "3人", "4人"], width=150,
            command=self._on_offline_size_change)
        self._offline_size_seg.set("2人")
        self._offline_size_seg.pack(side="left")

        col_hdr = ctk.CTkFrame(f, fg_color="transparent")
        col_hdr.grid(row=2, column=0, padx=20, pady=(8, 2), sticky="ew")
        for col, (label, w) in enumerate([("玩家", 80), ("角色", 250), ("難度", 140)]):
            ctk.CTkLabel(col_hdr, text=label, width=w, anchor="w",
                         font=_font(11, "bold"),
                         text_color="gray70").grid(row=0, column=col, padx=4)

        self._offline_char_segs: list[ctk.CTkSegmentedButton] = []
        self._offline_level_segs: list[ctk.CTkSegmentedButton] = []
        self._offline_ai_rows: list[ctk.CTkFrame] = []
        for i, defaults in enumerate(_OFFLINE_DEFAULTS):
            pid = i + 1
            row_f = ctk.CTkFrame(f, fg_color="transparent")
            row_f.grid(row=3 + i, column=0, padx=20, pady=2, sticky="ew")

            ctk.CTkLabel(row_f, text=f"P{pid} (AI)",
                         width=80, anchor="w",
                         font=_font(12)).grid(row=0, column=0, padx=4)

            char_seg = ctk.CTkSegmentedButton(
                row_f, values=CHAR_NAMES, width=250)
            char_seg.set(CHAR_NAMES[defaults["char_type"]])
            char_seg.grid(row=0, column=1, padx=4)

            level_seg = ctk.CTkSegmentedButton(
                row_f, values=["LV1", "LV2", "LV3"], width=140)
            level_seg.set(f"LV{defaults['level']}")
            level_seg.grid(row=0, column=2, padx=4)

            self._offline_char_segs.append(char_seg)
            self._offline_level_segs.append(level_seg)
            self._offline_ai_rows.append(row_f)

        self._offline_update_rows(1)  # 預設 2 人 = 1 個 AI

        ctk.CTkButton(f, text="開始遊戲", width=200, fg_color="green4",
                      command=self._on_offline_start).grid(row=6, column=0, pady=20)

    def _on_offline_size_change(self, label: str):
        num_ai = {"2人": 1, "3人": 2, "4人": 3}.get(label, 1)
        self._offline_update_rows(num_ai)

    def _offline_update_rows(self, num_ai: int):
        for i, row_f in enumerate(self._offline_ai_rows):
            if i < num_ai:
                row_f.grid()
            else:
                row_f.grid_remove()

    def _on_offline_start(self):
        num_players = {"2人": 2, "3人": 3, "4人": 4}.get(
            self._offline_size_seg.get(), 2)
        ai_players: dict[str, dict] = {}
        for i in range(num_players - 1):
            ct = CHAR_NAMES.index(self._offline_char_segs[i].get())
            lv = int(self._offline_level_segs[i].get().replace("LV", ""))
            ai_players[str(i + 1)] = {"char_type": ct, "level": lv}
        self._do_launch({
            "nickname": self.entry_nickname.get() or "DevPlayer",
            "room": "offline",
            "is_offline": True,
            "local_id": 0,
            "local_port": 5000,
            "num_players": num_players,
            "ai_players": ai_players,
        })

    # ── Replay Frame ──────────────────────────────────────────────────────

    def _build_replay_frame(self):
        f = ctk.CTkFrame(self, corner_radius=10)
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)
        self.replay_frame = f

        hdr = ctk.CTkFrame(f, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="ew")
        hdr.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(hdr, text="← 返回", width=80, fg_color="gray30",
                      command=self._show_main).grid(row=0, column=0)
        ctk.CTkLabel(hdr, text="對戰紀錄",
                     font=_font(16, "bold")).grid(row=0, column=1, padx=10)
        ctk.CTkButton(hdr, text="↻ 重新整理", width=90, fg_color="gray30",
                      height=28, command=self._refresh_replay_list).grid(
            row=0, column=2)

        self._replay_tabs = ctk.CTkTabview(f)
        self._replay_tabs.grid(row=1, column=0, padx=15,
                               pady=(0, 15), sticky="nsew")
        self._replay_tabs.add("牌位賽")
        self._replay_tabs.add("自訂房間")

        for tab_name in ("牌位賽", "自訂房間"):
            tab = self._replay_tabs.tab(tab_name)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)
            scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
            scroll.grid(row=0, column=0, sticky="nsew")
            if tab_name == "牌位賽":
                self._replay_scroll_ranked = scroll
            else:
                self._replay_scroll_custom = scroll

    def _show_replay(self):
        self._refresh_replay_list()
        self._hide_all_frames()
        self.replay_frame.grid(row=0, column=0, padx=20,
                               pady=20, sticky="nsew")

    def _refresh_replay_list(self):
        try:
            from src.python.replay import get_replay_dir
        except Exception:
            return
        replay_dir = get_replay_dir()
        entries: list[dict] = []
        if os.path.isdir(replay_dir):
            for fname in os.listdir(replay_dir):
                if not fname.endswith(".json"):
                    continue
                path = os.path.join(replay_dir, fname)
                try:
                    with open(path, encoding="utf-8") as fh:
                        data = json.load(fh)
                    data["_path"] = path
                    entries.append(data)
                except Exception:
                    pass
        entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

        for scroll in (self._replay_scroll_ranked, self._replay_scroll_custom):
            for w in scroll.winfo_children():
                w.destroy()

        for entry in entries:
            rt = entry.get("room_type", "custom")
            scroll = self._replay_scroll_ranked if rt == "ranked" else self._replay_scroll_custom
            self._add_replay_row(scroll, entry)

        for scroll, label in [
                (self._replay_scroll_ranked, "牌位賽"),
                (self._replay_scroll_custom, "自訂房間")]:
            if not scroll.winfo_children():
                ctk.CTkLabel(scroll, text=f"目前無{label}紀錄",
                             font=_font(12), text_color="gray60").pack(pady=20)

    def _add_replay_row(self, parent, entry: dict):
        players = entry.get("players", [])
        winner = entry.get("winner")
        total_f = entry.get("total_frames", 0)
        secs = total_f // 60
        dur_str = f"{secs // 60}分{secs % 60:02d}秒"

        if winner is None or winner == -2:
            winner_str = "平局"
        else:
            wp = next((p for p in players if p["id"] == winner), None)
            if wp:
                cn = CHAR_NAMES[wp.get("char_type", 0)] if wp.get(
                    "char_type", 0) < len(CHAR_NAMES) else "?"
                winner_str = f"{wp.get('nickname', '?')} ({cn})"
            else:
                winner_str = f"P{winner}"

        ts_raw = entry.get("timestamp", "")
        ts_disp = ts_raw.replace("T", " ")[:16]
        players_str = "  v  ".join(
            f"{p.get('nickname', '?')}({CHAR_NAMES[p.get('char_type', 0)] if p.get('char_type', 0) < len(CHAR_NAMES) else '?'})"
            for p in players
        )

        row_f = ctk.CTkFrame(parent, fg_color="gray20", corner_radius=4)
        row_f.pack(fill="x", pady=2, padx=2)
        row_f.grid_columnconfigure(0, weight=1)

        info_f = ctk.CTkFrame(row_f, fg_color="transparent")
        info_f.grid(row=0, column=0, padx=8, pady=4, sticky="ew")

        ctk.CTkLabel(info_f, text=ts_disp, font=_font(11),
                     text_color="gray70", width=110, anchor="w").pack(side="left", padx=2)
        ctk.CTkLabel(info_f, text=players_str, font=_font(11),
                     width=130, anchor="w").pack(side="left", padx=4)
        ctk.CTkLabel(info_f, text=dur_str, font=_font(11),
                     text_color="gray60", width=55, anchor="w").pack(side="right", padx=4)
        ctk.CTkLabel(info_f, text=f"勝者: {winner_str}", font=_font(11),
                     anchor="w").pack(side="left", padx=4, fill="x", expand=True)

        path = entry.get("_path", "")
        ctk.CTkButton(row_f, text="播放", width=60, height=26,
                      command=lambda p=path: self._do_launch_replay(p)).grid(
            row=0, column=1, padx=8, pady=4)

    def _do_launch_replay(self, path: str):
        if self.game_process:
            return
        log_path = os.path.join(os.path.dirname(sys.executable)
                                if getattr(sys, 'frozen', False) else PROJECT_ROOT,
                                "game_launch.log")
        try:
            if getattr(sys, 'frozen', False):
                game_exe = os.path.join(
                    os.path.dirname(sys.executable), "Game")
                cmd = [game_exe, "--replay", path]
            else:
                script = os.path.join(PROJECT_ROOT, "src", "python", "main.py")
                cmd = [sys.executable, script, "--replay", path]
            self.game_process = subprocess.Popen(
                cmd, env=os.environ.copy(),
                stdout=open(log_path, "a"), stderr=subprocess.STDOUT)
            self._show_main()
            self._set_status_main("重播播放中...")
            self.iconify()
            self._monitor_game()
        except Exception as e:
            self._set_status_main(f"Replay Launch Error: {e}")

    # ── Room Frame ────────────────────────────────────────────────────────

    def _build_room_frame(self):
        f = ctk.CTkFrame(self, corner_radius=10)
        f.grid_columnconfigure(0, weight=1)
        self.room_frame = f

        # 頂列
        hdr = ctk.CTkFrame(f, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="ew")
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(hdr, text="← 返回", width=80, fg_color="gray30",
                      command=self._leave_room).grid(row=0, column=0)
        self._lbl_room_code = ctk.CTkLabel(hdr, text="Room: ------",
                                           font=_font(16, "bold"))
        self._lbl_room_code.grid(row=0, column=1, padx=10)
        ctk.CTkButton(hdr, text="複製", width=60, fg_color="gray40",
                      command=self._copy_room_code).grid(row=0, column=2)
        self._lbl_online_room = ctk.CTkLabel(hdr, text="Online: -",
                                             font=_font(12))
        self._lbl_online_room.grid(row=0, column=3, padx=10)

        # 玩家列表區
        self._rows_frame = ctk.CTkFrame(f, fg_color="transparent")
        self._rows_frame.grid(row=1, column=0, padx=15, pady=8, sticky="ew")
        self._rows_frame.grid_columnconfigure(1, weight=1)

        # 房間人數（房主在自訂房間時可調整）
        self._size_frame = ctk.CTkFrame(f, fg_color="transparent")
        self._size_frame.grid(row=2, column=0, pady=(0, 4))
        ctk.CTkLabel(self._size_frame, text="房間人數",
                     font=_font(12)).pack(side="left", padx=(0, 8))
        self._room_size_seg = ctk.CTkSegmentedButton(
            self._size_frame, values=["2人", "3人", "4人"], width=150,
            command=self._on_room_size_change)
        self._room_size_seg.set("2人")
        self._room_size_seg.pack(side="left")
        self._size_frame.grid_remove()   # 預設隱藏

        # 底列按鈕
        bot = ctk.CTkFrame(f, fg_color="transparent")
        bot.grid(row=3, column=0, pady=10)
        self._btn_ready = ctk.CTkButton(bot, text="準備好了", width=130,
                                        command=self._on_ready)
        self._btn_ready.grid(row=0, column=0, padx=10)
        self._btn_start = ctk.CTkButton(bot, text="開始遊戲", width=130,
                                        state="disabled", fg_color="green4",
                                        command=self._on_start_game)
        self._btn_start.grid(row=0, column=1, padx=10)

        self._lbl_status_room = ctk.CTkLabel(f, text="等待玩家...",
                                             font=_font(12))
        self._lbl_status_room.grid(row=4, column=0, pady=8)

    def _update_room_ui(self, data: dict):
        self._room_data = data
        players = data.get("players", [])
        host_id = data.get("host_id", 0)
        target_size = data.get("target_size", 2)

        # 清除舊列
        for w in self._rows_frame.winfo_children():
            w.destroy()

        # 欄標題
        for col, txt in enumerate(["玩家", "角色選擇", "狀態"]):
            ctk.CTkLabel(self._rows_frame, text=txt,
                         font=_font(11, "bold"),
                         width=[120, 380, 70][col], anchor="w").grid(
                row=0, column=col, padx=4, pady=2, sticky="w")

        for i, p in enumerate(players):
            row = i + 1
            is_local = (p["id"] == self._my_id)
            # 排位：gold=★★★  silver=☆★★  bronze=☆☆★  placement=✖
            # 機器人：⌥♚ ⌥♜ ⌥♞
            _TIER_ICONS = {"gold": "★★★", "silver": "☆★★",
                           "bronze": "☆☆★", "placement": "✖"}
            if self._is_queue:
                tier_badge = _TIER_ICONS.get(
                    self._tier_cache.get(p["name"], "placement"), "✖")
            else:
                tier_badge = "⌘" if p["id"] == host_id else ""

            ctk.CTkLabel(self._rows_frame,
                         text=f"P{p['id']} {p['name']} {tier_badge}".strip(),
                         width=120, anchor="w").grid(
                row=row, column=0, padx=4, pady=4, sticky="w")

            if is_local:
                seg = ctk.CTkSegmentedButton(
                    self._rows_frame, values=CHAR_NAMES, width=380,
                    command=self._on_char_selected)
                seg.set(CHAR_NAMES[p.get("char_type", 0)])
                seg.grid(row=row, column=1, padx=4, pady=4)
            else:
                ctk.CTkLabel(self._rows_frame,
                             text=CHAR_NAMES[p.get("char_type", 0)],
                             width=380, anchor="center",
                             fg_color=("gray75", "gray30"),
                             corner_radius=6).grid(
                    row=row, column=1, padx=4, pady=4)

            ready = p.get("ready", False)
            ctk.CTkLabel(self._rows_frame,
                         text="✓ 準備" if ready else "- 等待",
                         width=70, anchor="center",
                         fg_color="green4" if ready else "gray40",
                         corner_radius=6).grid(
                row=row, column=2, padx=4, pady=4)

        # 清除已被真實玩家佔用的 AI 槽位
        real_pids = {p["id"] for p in players}
        for pid in list(self._ai_players.keys()):
            if pid in real_pids:
                del self._ai_players[pid]

        # 空槽位：手動加入 AI
        for i in range(len(players), target_size):
            row = i + 1
            if self._is_host and not self._is_queue:
                pid = i
                if pid in self._ai_players:
                    # 已加入 AI：顯示設定列
                    ctk.CTkLabel(self._rows_frame,
                                 text=f"P{pid} (機器人)",
                                 width=120, anchor="w").grid(
                        row=row, column=0, padx=4, pady=4, sticky="w")

                    # 角色選單：與正常玩家槽寬度相同，直接 grid 在 col 1
                    char_seg = ctk.CTkSegmentedButton(
                        self._rows_frame, values=CHAR_NAMES, width=380)
                    char_seg.set(
                        CHAR_NAMES[self._ai_players[pid]["char_type"]])
                    char_seg.configure(
                        command=lambda v, p=pid: self._on_room_ai_char(p, v))
                    char_seg.grid(row=row, column=1, padx=4, pady=4)

                    # 難度 + 移除按鈕：擺在 col 2
                    ai_ctrl = ctk.CTkFrame(
                        self._rows_frame, fg_color="transparent")
                    ai_ctrl.grid(row=row, column=2, padx=4, pady=4)

                    level_seg = ctk.CTkSegmentedButton(
                        ai_ctrl, values=["1", "2", "3"], width=46)
                    level_seg.set(str(self._ai_players[pid]["level"]))
                    level_seg.configure(
                        command=lambda v, p=pid: self._on_room_ai_level(p, v))
                    level_seg.pack(side="left", padx=(0, 2))

                    ctk.CTkButton(
                        ai_ctrl, text="✕", width=18, height=28,
                        fg_color="gray30", hover_color="red4",
                        command=lambda p=pid: self._on_remove_ai(p)).pack(side="left")
                else:
                    # 尚未加入 AI：顯示「加入AI」按鈕
                    ctk.CTkLabel(self._rows_frame,
                                 text=f"P{pid} (空)",
                                 width=120, anchor="w",
                                 text_color="gray50").grid(
                        row=row, column=0, padx=4, pady=4, sticky="w")
                    ctk.CTkButton(
                        self._rows_frame, text="+ 加入 AI",
                        width=380, height=28,
                        fg_color=("gray70", "gray25"), hover_color=("gray60", "gray35"),
                        command=lambda p=pid: self._on_add_ai(p)).grid(
                        row=row, column=1, padx=4, pady=4)
                    ctk.CTkLabel(self._rows_frame, text="---",
                                 width=70, anchor="center",
                                 text_color="gray50").grid(
                        row=row, column=2, padx=4, pady=4)
            else:
                ctk.CTkLabel(self._rows_frame, text=f"P{i} (空)",
                             width=120, anchor="w",
                             text_color="gray50").grid(
                    row=row, column=0, padx=4, pady=4, sticky="w")
                ctk.CTkLabel(self._rows_frame, text="---",
                             width=380, anchor="center",
                             text_color="gray50").grid(row=row, column=1, padx=4, pady=4)
                ctk.CTkLabel(self._rows_frame, text="---",
                             width=70, anchor="center",
                             text_color="gray50").grid(row=row, column=2, padx=4, pady=4)

        # 人數選擇器（房主且非天梯）
        if self._is_host and not self._is_queue:
            self._room_size_seg.set(f"{target_size}人")
            self._size_frame.grid()
        else:
            self._size_frame.grid_remove()

        # 開始按鈕（房主且全員準備且真人+AI人數達標）
        filled = len(players) + len(self._ai_players)
        all_ready = (filled >= target_size
                     and all(p.get("ready") for p in players))
        if self._is_host and not self._is_queue:
            self._btn_start.configure(
                state="normal" if all_ready else "disabled",
                text=f"開始遊戲 ({filled}/{target_size})")
        else:
            self._btn_start.configure(
                state="disabled",
                text="排隊中" if self._is_queue else "等待房主")

    # ── 切換 Frame ────────────────────────────────────────────────────────

    def _hide_all_frames(self):
        for frame in (self.main_frame, self.room_frame,
                      self.settings_frame, self.leaderboard_frame,
                      self.offline_frame, self.replay_frame):
            frame.grid_remove()

    def _show_main(self):
        self._hide_all_frames()
        self.main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

    def _show_settings(self):
        self._settings_vol.set(self.settings_mgr.get("volume"))
        self._settings_vol_lbl.configure(
            text=f"{self.settings_mgr.get('volume')}%")
        self._settings_preset_seg.set(
            _PRESET_LABELS[self.settings_mgr.get("key_preset")])
        self._hide_all_frames()
        self.settings_frame.grid(
            row=0, column=0, padx=20, pady=20, sticky="nsew")

    def _show_leaderboard(self):
        self._hide_all_frames()
        self.leaderboard_frame.grid(
            row=0, column=0, padx=20, pady=20, sticky="nsew")
        self._refresh_leaderboard()

    def _save_settings(self):
        self.settings_mgr.set("volume", int(self._settings_vol.get()))
        self.settings_mgr.set(
            "key_preset",
            _PRESET_LABELS.index(self._settings_preset_seg.get()))
        self.settings_mgr.set("background_enabled", bool(self._settings_bg_switch.get()))
        self.settings_mgr.set("background_id",      int(self._settings_bg_seg.get()))
        self.settings_mgr.save()
        self._show_main()

    def _refresh_leaderboard(self):
        self._lb_status.configure(text="載入中…")
        threading.Thread(
            target=self._do_fetch_leaderboard, daemon=True).start()

    def _show_room(self, room_id: str, is_queue: bool):
        self._room_id = room_id
        if is_queue:
            tier = room_id.removeprefix("__queue_").removesuffix("__")
            tier_label = _TIER_LABELS.get(tier, tier)
            label = f"Room: 配對中（{tier_label}）"
        else:
            label = f"Room: {room_id}"
        self._lbl_room_code.configure(text=label)
        self.main_frame.grid_remove()
        self.room_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self._set_status_room("等待玩家加入..." if not is_queue else "等待其他玩家...")

    # ── Main Frame 回呼 ───────────────────────────────────────────────────

    def _on_queue(self):
        self._is_queue = True
        self._start_online("__queue__")

    def _on_create(self):
        self._is_queue = False
        self._start_online(_gen_room_code())

    def _on_join_click(self):
        self._is_queue = False
        code = self._entry_room.get().strip().upper()
        if not code:
            self._set_status_main("請輸入房間碼")
            return
        self._start_online(code)
        self._entry_room.delete(0, "end")

    def _on_offline(self):
        self._hide_all_frames()
        self.offline_frame.grid(
            row=0, column=0, padx=20, pady=20, sticky="nsew")

    # ── Room Frame 回呼 ───────────────────────────────────────────────────

    def _on_char_selected(self, name: str):
        ct = CHAR_NAMES.index(name) if name in CHAR_NAMES else 0
        self._local_ct = ct
        if self.loop and self._client:
            asyncio.run_coroutine_threadsafe(
                self._client.send_char_select(ct), self.loop)

    def _on_add_ai(self, pid: int):
        self._ai_players[pid] = {"char_type": 0, "level": 1}
        if self._room_data:
            self._update_room_ui(self._room_data)

    def _on_remove_ai(self, pid: int):
        self._ai_players.pop(pid, None)
        if self._room_data:
            self._update_room_ui(self._room_data)

    def _on_room_ai_char(self, pid: int, name: str):
        ct = CHAR_NAMES.index(name) if name in CHAR_NAMES else 0
        self._ai_players.setdefault(pid, {"level": 1})["char_type"] = ct

    def _on_room_ai_level(self, pid: int, level_str: str):
        level = int(level_str.replace("LV", ""))
        self._ai_players.setdefault(pid, {"char_type": 0})["level"] = level

    def _on_room_size_change(self, label: str):
        size_map = {"2人": 2, "3人": 3, "4人": 4}
        size = size_map.get(label, 2)
        if self._room_data:
            self._update_room_ui({**self._room_data, "target_size": size})
        if self.loop and self._client:
            asyncio.run_coroutine_threadsafe(
                self._client.send_data(
                    {"type": "set_room_size", "size": size}),
                self.loop)

    def _on_ready(self):
        self._btn_ready.configure(text="取消準備", command=self._on_cancel_ready)
        if self.loop and self._client:
            asyncio.run_coroutine_threadsafe(
                self._client.send_ready(), self.loop)

    def _on_cancel_ready(self):
        if self._is_queue:
            return
        self._btn_ready.configure(text="準備好了", command=self._on_ready)
        if self.loop and self._client:
            asyncio.run_coroutine_threadsafe(
                self._client.send_cancel_ready(), self.loop)

    def _on_start_game(self):
        self._btn_start.configure(state="disabled")
        if self.loop and self._client:
            asyncio.run_coroutine_threadsafe(
                self._client.send_start_game(
                    len(self._ai_players),
                    {str(k): v for k, v in self._ai_players.items()}),
                self.loop)

    def _leave_room(self):
        self._queue_cancelled = True
        if self.loop and self._client:
            asyncio.run_coroutine_threadsafe(self._client.close(), self.loop)
        self._reset_room_state()
        self._show_main()
        self._set_status_main("已離開房間。")

    def _copy_room_code(self):
        if self._room_id and not self._room_id.startswith("__queue_"):
            self.clipboard_clear()
            self.clipboard_append(self._room_id)
            self._set_status_room("房間碼已複製！")

    # ── Online Flow ───────────────────────────────────────────────────────

    def _start_online(self, room_id: str):
        if self.game_process:
            return
        self._set_status_main("探測 NAT 位址...")
        self.lobby_thread = threading.Thread(
            target=self._run_lobby_thread, args=(room_id,), daemon=True)
        self.lobby_thread.start()

    def _run_lobby_thread(self, room_id: str):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._lobby_task(room_id))
        finally:
            pending = asyncio.all_tasks(self.loop)
            if pending:
                self.loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True))
            self.loop.close()
            self.loop = None

    async def _fetch_tier_async(self, nickname: str) -> str:
        try:
            loop = asyncio.get_event_loop()
            url = f"{LOBBY_HTTP_URL}/player_tier/{urllib.parse.quote(nickname)}"

            def _get():
                with urllib.request.urlopen(url, timeout=3) as r:
                    return json.loads(r.read()).get("tier", "placement")
            return await loop.run_in_executor(None, _get)
        except Exception:
            return "placement"

    async def _lobby_task(self, room_id: str):
        nickname = self.entry_nickname.get() or "Player"
        is_queue = (room_id == "__queue__")
        self._queue_cancelled = False

        # 定義配對階段（牌位賽模式才有擴段）
        if is_queue:
            self._set_status_main("查詢段位中...")
            tier = await self._fetch_tier_async(nickname)
            self._tier_cache[nickname] = tier
            tier_label = _TIER_LABELS.get(tier, tier)
            # 等待時間 = 120 + 60 = 3分鐘，優先排同段位玩家，之後放寬段位限制
            phases = [
                (f"__queue_{tier}__", 120,  f"段位：{tier_label}，尋找對手中..."),
                ("__queue_all__",      60,  f"放寬段位限制，尋找對手中..."),
            ]
        else:
            phases = [(room_id, None, "")]

        # STUN（一次，所有階段共用 socket）
        local_port = 5000
        for p in range(5000, 5020):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.bind(('0.0.0.0', p))
                s.close()
                local_port = p
                break
            except OSError:
                s.close()

        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_sock.bind(('0.0.0.0', local_port))
        self._udp_sock = udp_sock
        try:
            loop = asyncio.get_event_loop()
            pub_ip, pub_port = await loop.run_in_executor(
                None, lambda: probe_stun_on_sock(udp_sock))
            self._set_status_main(f"NAT: {pub_ip}:{pub_port}")
        except Exception as e:
            udp_sock.close()
            self._udp_sock = None
            self._set_status_main(f"STUN 失敗: {e}")
            return

        local_ip = get_local_ip()

        # 逐階段配對
        for phase_idx, (phase_room, phase_timeout, phase_status) in enumerate(phases):
            if is_queue:
                self._set_status_main(phase_status)
            result = await self._phase_listen(
                phase_room, nickname, udp_sock, pub_ip, pub_port,
                local_ip, local_port, phase_timeout,
                auto_ready=(is_queue and phase_idx > 0))
            if result in ("matched", "cancelled", "error"):
                return

        # 所有階段都超時 → 玩家不足提示
        try:
            udp_sock.close()
        except Exception:
            pass
        self._udp_sock = None
        self._set_status_main(
            "歡迎使用自訂房間邀請朋友對戰。")
        self.after(0, self._show_main)

    async def _phase_listen(
            self, room_id: str, nickname: str,
            udp_sock, pub_ip: str, pub_port: int,
            local_ip: str, local_port: int,
            timeout_secs: float | None,
            auto_ready: bool = False) -> str:
        """加入 room_id，等待 game_start 或 timeout。
        Returns: 'matched' | 'timeout' | 'cancelled' | 'error'
        """
        self._is_queue = room_id.startswith("__queue_")
        self._client = LobbyClient(LOBBY_WS_URL)
        if not await self._client.join_room(room_id, nickname):
            self._set_status_main("無法連線至大廳伺服器。")
            return "error"

        client = self._client  # 捕捉非 None 的參考，供 nested function 使用
        await client.send_data({
            "type": "report_endpoint",
            "pub_ip": pub_ip, "pub_port": pub_port,
            "local_ip": local_ip, "local_port": local_port,
        })

        punch_stop = threading.Event()
        punch_thread: threading.Thread | None = None
        result = "timeout"

        async def _listen_loop():
            nonlocal punch_thread, result
            try:
                async for msg in client.listen():
                    if self._queue_cancelled:
                        result = "cancelled"
                        return
                    t = msg.get("type")

                    if t == "join_ack":
                        self._my_id = msg["player_id"]
                        self._is_host = msg["is_host"]
                        is_q = room_id.startswith("__queue_")
                        self.after(0, lambda m=msg,
                                   q=is_q: self._show_room(m["room_id"], q))
                        if auto_ready:
                            await client.send_data({"type": "player_ready"})

                    elif t == "room_update":
                        self.after(0, lambda m=msg: self._update_room_ui(m))

                    elif t == "punch_start":
                        my_pub = next((p["pub_ip"] for p in msg["players"]
                                       if p["id"] == self._my_id), pub_ip)
                        remotes = [
                            (p["local_ip"], p["local_port"])
                            if p["pub_ip"] == my_pub else (p["pub_ip"], p["pub_port"])
                            for p in msg["players"]
                            if p["id"] != self._my_id and p["pub_port"] != 0
                        ]
                        punch_stop.clear()
                        punch_thread = threading.Thread(
                            target=self._punch_loop,
                            args=(udp_sock, remotes, punch_stop), daemon=True)
                        punch_thread.start()
                        self._set_status_room("打洞中...")

                    elif t == "game_start":
                        punch_stop.set()
                        if punch_thread:
                            punch_thread.join(timeout=1.0)
                        try:
                            udp_sock.close()
                        except Exception:
                            pass
                        self._udp_sock = None

                        my_pub = next((p["pub_ip"] for p in msg["players"]
                                       if p["id"] == self._my_id), "")
                        resolved = []
                        for p in msg["players"]:
                            same_lan = (p["pub_ip"] == my_pub
                                        and p["id"] != self._my_id)
                            resolved.append({**p,
                                             "ip":   p["local_ip"] if same_lan else p["pub_ip"],
                                             "port": p["local_port"] if same_lan else p["pub_port"],
                                             })
                        # host 的 self._ai_players 為本地權威；非 host 從伺服器廣播取得
                        local_ai = {str(k): v for k,
                                    v in self._ai_players.items()}
                        ai_players_final = local_ai or msg.get(
                            "ai_players", {})
                        session_data = {
                            "nickname":    nickname,
                            "room":        room_id,
                            "is_offline":  False,
                            "local_id":    self._my_id,
                            "local_port":  local_port,
                            "num_players": len(msg["players"]) + len(ai_players_final),
                            "players":     resolved,
                            "seed":        msg["seed"],
                            "host_id":     msg.get("host_id", 0),
                            "match_id":    msg.get("match_id", ""),
                            "lobby_url":   LOBBY_HTTP_URL,
                            "ai_players":  ai_players_final,
                        }
                        await client.close()
                        self.after(
                            50, lambda sd=session_data: self._do_launch(sd))
                        result = "matched"
                        return

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._set_status_main(f"連線錯誤: {e}")
                self.after(0, self._show_main)
                result = "cancelled"

        if timeout_secs is not None:
            listen_task = asyncio.create_task(_listen_loop())
            timer_task = asyncio.create_task(asyncio.sleep(timeout_secs))
            done, pending = await asyncio.wait(
                {listen_task, timer_task}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            if timer_task in done:
                # timeout：清理 punch 與連線，切回主頁面準備下一階段
                punch_stop.set()
                if punch_thread and punch_thread.is_alive():
                    punch_thread.join(timeout=1.0)
                try:
                    await client.close()
                except Exception:
                    pass
                self._reset_room_state()
                self.after(0, self._show_main)
        else:
            await _listen_loop()

        return result

    # ── 工具方法 ──────────────────────────────────────────────────────────

    def _punch_loop(self, sock: socket.socket, remotes: list, stop: threading.Event):
        while not stop.is_set():
            for ip, port in remotes:
                try:
                    sock.sendto(b'\x00', (ip, port))
                except Exception:
                    pass
            time.sleep(0.1)

    def _reset_room_state(self):
        self._my_id = 0
        self._is_host = False
        self._is_queue = False
        self._room_id = ""
        self._local_ct = 0
        self._room_data = {}
        self._ai_players = {}
        self._size_frame.grid_remove()
        self._btn_ready.configure(state="normal", text="準備好了",
                                  command=self._on_ready)
        self._btn_start.configure(state="disabled", text="開始遊戲")

    def _set_status_main(self, text: str):
        self.after(0, lambda: self._lbl_status_main.configure(text=text))

    def _set_status_room(self, text: str):
        self.after(0, lambda: self._lbl_status_room.configure(text=text))

    def _poll_online(self):
        threading.Thread(target=self._fetch_online, daemon=True).start()
        self.after(10_000, self._poll_online)

    def _fetch_online(self):
        try:
            with urllib.request.urlopen(f"{LOBBY_HTTP_URL}/online", timeout=3) as r:
                count = json.loads(r.read()).get("count", 0)
            self.after(0, lambda: self._lbl_online_main.configure(
                text=f"Online: {count}"))
            self.after(0, lambda: self._lbl_online_room.configure(
                text=f"Online: {count}"))
        except Exception:
            pass

    def _do_launch(self, session_data: dict):
        payload = encrypt_payload(session_data)
        self.settings_mgr.set("nickname", session_data["nickname"])
        self.settings_mgr.save()
        log_path = os.path.join(os.path.dirname(sys.executable)
                                if getattr(sys, 'frozen', False) else PROJECT_ROOT,
                                "game_launch.log")
        try:
            if getattr(sys, 'frozen', False):
                game_exe = os.path.join(
                    os.path.dirname(sys.executable), "Game")
                cmd = [game_exe, "--payload", payload]
            else:
                script = os.path.join(PROJECT_ROOT, "src", "python", "main.py")
                cmd = [sys.executable, script, "--payload", payload]
            with open(log_path, "w") as _lf:
                _lf.write(
                    f"cmd: {cmd}\nexe_exists: {os.path.exists(cmd[0])}\n")
            self.game_process = subprocess.Popen(
                cmd, env=os.environ.copy(),
                stdout=open(log_path, "a"), stderr=subprocess.STDOUT)
            self._reset_room_state()
            self._show_main()
            self._set_status_main("遊戲進行中...")
            self.iconify()
            self._monitor_game()
        except Exception as e:
            self._set_status_main(f"Launch Error: {e}")

    def _monitor_game(self):
        if self.game_process and self.game_process.poll() is not None:
            exit_code = self.game_process.returncode
            self._reset_room_state()
            self._show_main()
            self._set_status_main(f"遊戲結束（exit {exit_code}）。")
            self.deiconify()
            self.game_process = None
        else:
            self.after(1000, self._monitor_game)

    def _on_closing(self):
        self.settings_mgr.set("window_pos", [self.winfo_x(), self.winfo_y()])
        self.settings_mgr.save()
        if self._udp_sock:
            try:
                self._udp_sock.close()
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    _setup_project_font()
    app = LauncherApp()
    app.mainloop()
    if _FC_TMP_CONF and os.path.exists(_FC_TMP_CONF):
        os.unlink(_FC_TMP_CONF)
