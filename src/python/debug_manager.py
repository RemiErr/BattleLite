import pygame


class DebugManager:
    def __init__(self, font_size=18):
        self.enabled = False
        self.font = pygame.font.SysFont(
            "Consolas", font_size) or pygame.font.SysFont("monospace", font_size)

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
        panel_width = 320
        panel_height = 220 + (len(sorted_players) * 65)  # 增加高度給 AI 資訊
        overlay = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        screen.blit(overlay, (5, 65))

        # 2. 收集基礎資訊
        info_lines = [
            f"--- BattleLite Debug ---",
            f"GGRS Frame: {session.current_frame()}",
            f"Status:     {'SYNCED' if session.is_synchronized() else 'WAITING'}",
            f"FPS:        {int(fps)}",
            f"Players:    {len(sorted_players)}",
            f"------------------------",
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
            text_surf.set_alpha(180)
            screen.blit(text_surf, (30, 80 + idx * 20))
