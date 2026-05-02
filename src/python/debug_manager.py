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


class DebugManager:
    def __init__(self, font_size=16):
        self.enabled = False

        # 定位字型檔案路徑
        font_path = os.path.join(
            _FONTS_DIR, "NotoSansTC-VariableFont_wght.ttf")

        try:
            if os.path.exists(font_path):
                # 直接載入支援中文的字型檔
                self.font = pygame.font.Font(font_path, font_size)
            else:
                # 若找不到則回退系統預設
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

        # players 為 [(original_idx, Player), ...] 依原始 id 排序顯示
        sorted_players = sorted(players, key=lambda t: t[0])
        ai_controllers = ai_controllers or {}

        # 1. 根據玩家人數與 AI 資訊量調整面板寬度與高度
        panel_width = 220
        panel_height = 200 + (len(sorted_players) * 80)
        overlay = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        # 擺放位置稍作下移，避免與 HUD 衝突
        screen.blit(overlay, (5, 65))

        # 2. 收集基礎資訊
        info_lines = [
            f"------  BattleLite Debug  ------",
            f"GGRS Frame: {session.current_frame()}",
            f"Status:     {'SYNCED' if session.is_synchronized() else 'WAITING'}",
            f"FPS:        {int(fps)}",
            f"Players:    {len(sorted_players)}",
            f"--------------------------------------",
        ]

        # 每個玩家的狀態（座標、速度、AI 策略）
        for pid, player in sorted_players:
            info_lines.append(
                f"P{pid} Pos: ({player.x//1000}, {player.y//1000}, {player.z//1000})")

            if pid in ai_controllers:
                ai_info = ai_controllers[pid].get_debug_info()
                level = ai_info.get("level", "Unknown")
                info_lines.append(f"  AI: {level}")
                if level == "lv1-FSM":
                    info_lines.append(f"  State: {ai_info.get('state')}")
                elif level == "lv2-Pattern":
                    info_lines.append(
                        f"  Patt: {ai_info.get('pattern')} ({ai_info.get('step')})")
                elif level == "lv3-GOAP":
                    info_lines.append(f"  Goal: {ai_info.get('goal')}")
                    # 這裡的 Plan 欄位可能會包含中文字，現在載入 NotoSans 後可正確顯示
                    info_lines.append(f"  Plan: {ai_info.get('plan')}")
            else:
                info_lines.append(f"  P{pid}: HUMAN")

            info_lines.append(
                f"  Vel: ({player.vx}, {player.vy}, {player.vz})")

        # 3. 渲染文字
        for idx, line in enumerate(info_lines):
            color = (255, 255, 255)
            if "SYNCED" in line:
                color = (0, 255, 0)
            elif "AI:" in line:
                color = (255, 255, 0)  # 黃色標註 AI
            elif "HUMAN" in line:
                color = (0, 255, 255)  # 青色標註真人

            text_surf = self.font.render(line, True, color)
            # 設定文字透明度
            text_surf.set_alpha(200)
            # 配合背景座標進行偏移
            screen.blit(text_surf, (20, 80 + idx * 20))
