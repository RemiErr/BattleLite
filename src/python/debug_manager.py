import pygame


class DebugManager:
    def __init__(self, font_size=18):
        self.enabled = True
        self.font = pygame.font.SysFont(
            "Consolas", font_size) or pygame.font.SysFont("monospace", font_size)

    def toggle(self):
        self.enabled = not self.enabled
        print(f"[Debug] Overlay: {'ENABLED' if self.enabled else 'DISABLED'}")

    def draw(self, screen, session, players, fps):
        if not self.enabled:
            return

        # players 為 [(original_idx, Player), ...] 依原始 id 排序顯示
        sorted_players = sorted(players, key=lambda t: t[0])

        # 1. 根據玩家人數調整面板高度
        panel_width = 300
        panel_height = 150 + (len(sorted_players) * 40)
        overlay = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (5, 5))

        # 2. 收集資訊
        info_lines = [
            f"--- BattleLite Debug ---",
            f"GGRS Frame: {session.current_frame()}",
            f"Status:     {'SYNCED' if session.is_synchronized() else 'WAITING'}",
            f"FPS:        {int(fps)}",
            f"Players:    {len(sorted_players)}",
            f"------------------------",
        ]

        # 每個玩家的座標與速度（依原始 id 顯示）
        for pid, player in sorted_players:
            info_lines.append(
                f"P{pid} Pos: ({player.x//1000}, {player.y//1000}, {player.z//1000})")
            info_lines.append(
                f"P{pid} Vel: ({player.vx}, {player.vy}, {player.vz})")

        # 3. 渲染文字
        for idx, line in enumerate(info_lines):
            text_surf = self.font.render(
                line, True, (0, 255, 0) if "SYNCED" in line else (255, 255, 255))
            screen.blit(text_surf, (15, 10 + idx * 20))
