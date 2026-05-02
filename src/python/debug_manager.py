import pygame
import os
import sys

if getattr(sys, 'frozen', False):
    PROJECT_ROOT = sys._MEIPASS
else:
    PROJECT_ROOT = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '../..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

_FONTS_DIR = os.path.join(PROJECT_ROOT, "src", "assets", "fonts")


def _fmt_fuzzy(d: dict) -> str:
    """將隸屬度向量壓縮成 'lo:80% md:15% hi:5%' 格式。"""
    abbr = {"low": "lo", "mid": "md", "high": "hi",
            "close": "cl", "far": "fr"}
    return " ".join(
        f"{abbr.get(k, k[:2])}:{int(v * 100)}%"
        for k, v in d.items()
    )


class DebugManager:
    def __init__(self, font_size=16):
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

        # 收集所有文字行，事後再依行數決定面板高度
        info_lines: list[tuple[str, tuple]] = []  # (text, color)

        WHITE = (255, 255, 255)
        GREEN = (0,   255, 0)
        YELLOW = (255, 255, 0)
        CYAN = (0,   255, 255)
        ORANGE = (255, 180, 0)
        GRAY = (180, 180, 180)

        def add(text, color=WHITE):
            info_lines.append((text, color))

        add("------  BattleLite Debug  ------")
        add(f"GGRS Frame: {session.current_frame()}")
        synced = session.is_synchronized()
        add(f"Status:     {'SYNCED' if synced else 'WAITING'}",
            GREEN if synced else WHITE)
        add(f"FPS:        {int(fps)}")
        add(f"Players:    {len(sorted_players)}")
        add("--------------------------------------")

        for pid, player in sorted_players:
            add(f"P{pid} Pos: ({player.x//1000}, {player.y//1000}, {player.z//1000})")

            if pid in ai_controllers:
                ai_info = ai_controllers[pid].get_debug_info()
                level = ai_info.get("level", "Unknown")
                add(f"  AI: {level}", YELLOW)

                if level == "lv1-FSM":
                    add(f"  State: {ai_info.get('state')}")

                elif level == "lv2-Pattern":
                    add(f"  Patt: {ai_info.get('pattern')} ({ai_info.get('step')})")

                elif level == "lv3-GOAP":
                    add(f"  Goal: {ai_info.get('goal')}  Mode: {ai_info.get('mode', '-')}")
                    add(f"  Plan: {ai_info.get('plan')}")

                    # 模糊隸屬度
                    hp_str = _fmt_fuzzy(ai_info.get("fuzzy_hp",   {}))
                    mp_str = _fmt_fuzzy(ai_info.get("fuzzy_mp",   {}))
                    dist_str = _fmt_fuzzy(ai_info.get("fuzzy_dist", {}))
                    if hp_str:
                        add(f"  HP  [{hp_str}]", ORANGE)
                    if mp_str:
                        add(f"  MP  [{mp_str}]", ORANGE)
                    if dist_str:
                        add(f"  Dst [{dist_str}]", ORANGE)

                    # 離散狀態
                    adv = ai_info.get("hp_adv",    "-")
                    in_range = "T" if ai_info.get("in_range") else "F"
                    y_align = "T" if ai_info.get("y_aligned") else "F"
                    add(f"  Adv:{adv}  Rng:{in_range}  Y:{y_align}", GRAY)

            else:
                add(f"  P{pid}: HUMAN", CYAN)

            add(f"  Vel: ({player.vx}, {player.vy}, {player.vz})")

        # 依行數動態計算面板高度
        panel_width = 260
        panel_height = 20 + len(info_lines) * 20
        overlay = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        screen.blit(overlay, (5, 65))

        for idx, (line, color) in enumerate(info_lines):
            text_surf = self.font.render(line, True, color)
            text_surf.set_alpha(200)
            screen.blit(text_surf, (20, 80 + idx * 20))
