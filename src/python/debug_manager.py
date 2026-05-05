import pygame
import os

from src.python.app_root import PROJECT_ROOT

_FONTS_DIR = os.path.join(PROJECT_ROOT, "src", "assets", "fonts")

_COL_W = 256   # 與 HUD _SLOT_W 對齊（SCREEN_W // 4）
_LINE_H = 20    # 每行高度（px），縮小讓更多資訊塞進螢幕


def _fmt_fuzzy(d: dict) -> str:
    """將隸屬度向量壓縮成 'lo:80% md:15% hi:5%' 格式。"""
    abbr = {"low": "lo", "mid": "md", "high": "hi",
            "close": "cl", "far": "fr"}
    return " ".join(
        f"{abbr.get(k, k[:2])}:{int(v * 100)}%"
        for k, v in d.items()
    )


class DebugManager:
    def __init__(self, font_size=14):
        self.enabled = False

        font_path = os.path.join(
            _FONTS_DIR, "NotoSansTC-VariableFont_wght.ttf")
        try:
            if os.path.exists(font_path):
                self.font = pygame.font.Font(font_path, font_size)
            else:
                self.font = pygame.font.SysFont(
                    "Microsoft JhengHei, Consolas, monospace", font_size)
        except Exception as e:
            print(f"[Debug] Font loading failed: {e}")
            self.font = pygame.font.SysFont("monospace", font_size)

    def toggle(self):
        self.enabled = not self.enabled
        print(f"[Debug] Overlay: {'ENABLED' if self.enabled else 'DISABLED'}")

    def draw(self, screen, session, players, fps, ai_controllers=None):
        if not self.enabled:
            return

        sorted_players = sorted(players, key=lambda t: t[0])
        ai_controllers = ai_controllers or {}

        WHITE = (255, 255, 255)
        GREEN = (0,   255, 0)
        YELLOW = (255, 255, 0)
        CYAN = (0,   255, 255)
        ORANGE = (255, 180, 0)
        GRAY = (180, 180, 180)

        # ── 1. 標頭（單行橫條）──────────────────────────────────
        synced = session.is_synchronized()
        status_color = GREEN if synced else WHITE
        header: list[tuple[str, tuple]] = [
            ("BattleLite Debug：", WHITE),
            (f"Frame:{session.current_frame()}  FPS:{int(fps)}  "
             f"{'SYNCED' if synced else 'WAITING'}  "
             f"P:{len(sorted_players)}", status_color),
        ]

        # ── 2. 每個玩家資訊欄（橫向並列）──────────────────────
        player_cols: list[list[tuple[str, tuple]]] = []

        for pid, player in sorted_players:
            col: list[tuple[str, tuple]] = []

            def _add(text, color=WHITE, _col=col):
                _col.append((text, color))

            pos = f"({player.x//1000},{player.y//1000},{player.z//1000})"
            _add(f"P{pid} {pos}")

            if pid in ai_controllers:
                ai_info = ai_controllers[pid].get_debug_info()
                level = ai_info.get("level", "?")
                _add(f"AI: {level}", YELLOW)

                if level == "lv1-FSM":
                    _add(f"State: {ai_info.get('state')}")

                elif level == "lv2-Pattern":
                    _add(f"Patt: {ai_info.get('pattern')}")
                    _add(f"Step: {ai_info.get('step')}")

                elif level == "lv3-GOAP":
                    _add(f"Goal: {ai_info.get('goal')}")
                    _add(f"Mode: {ai_info.get('mode', '-')}")
                    _add(f"Plan: {ai_info.get('plan')}")

                    hp_str = _fmt_fuzzy(ai_info.get("fuzzy_hp",   {}))
                    mp_str = _fmt_fuzzy(ai_info.get("fuzzy_mp",   {}))
                    dist_str = _fmt_fuzzy(ai_info.get("fuzzy_dist", {}))
                    if hp_str:
                        _add(f"HP [{hp_str}]", ORANGE)
                    if mp_str:
                        _add(f"MP [{mp_str}]", ORANGE)
                    if dist_str:
                        _add(f"Dt [{dist_str}]", ORANGE)

                    adv = ai_info.get("hp_adv",    "-")
                    in_range = "T" if ai_info.get("in_range") else "F"
                    y_align = "T" if ai_info.get("y_aligned") else "F"
                    _add(f"Adv: {adv}, Rng: {in_range}, Y: {y_align}", GRAY)

            else:
                _add("HUMAN", CYAN)

            _add(f"Vel ({player.vx}, {player.vy}, {player.vz})", GRAY)
            player_cols.append(col)

        # ── 3. 計算面板尺寸並繪製背景 ──────────────────────────
        n = len(player_cols)
        PAD = 6
        y0 = 65 + PAD
        hdr_h = len(header) * _LINE_H + PAD
        col_h = max((len(c) for c in player_cols), default=0) * _LINE_H
        panel_w = _COL_W * max(1, n)
        panel_h = hdr_h + col_h + PAD

        overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 130))
        screen.blit(overlay, (0, 65))

        # ── 4. 渲染標頭 ──────────────────────────────────────
        for i, (text, color) in enumerate(header):
            surf = self.font.render(text, True, color)
            surf.set_alpha(210)
            screen.blit(surf, (PAD, y0 + i * _LINE_H))

        # 標頭下方橫向分隔線
        sep_y = y0 + hdr_h - 2
        pygame.draw.line(screen, (100, 100, 100),
                         (0, sep_y), (panel_w, sep_y), 1)

        # ── 5. 各玩家欄位橫向排列（欄位左緣對齊 HUD slot 邊界）────
        y_col = y0 + hdr_h
        for col_idx, col in enumerate(player_cols):
            x_base = col_idx * _COL_W   # 對齊 HUD slot 左緣

            # 欄位間縱向分隔線（對齊 HUD slot 分隔線）
            if col_idx > 0:
                pygame.draw.line(screen, (100, 100, 100),
                                 (x_base, sep_y),
                                 (x_base, sep_y + col_h), 1)

            for row_idx, (text, color) in enumerate(col):
                surf = self.font.render(text, True, color)
                surf.set_alpha(210)
                screen.blit(surf, (x_base + PAD, y_col + row_idx * _LINE_H))
