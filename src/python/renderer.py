"""
BattleLite 渲染器模組
負責將 Rust 核心計算的物理座標轉換為 Pygame 的螢幕像素，並處理繪圖邏輯。
"""
from src.python.hud import HUD_H

def get_screen_pos(player):
    """
    將 Rust 2.5D 物理座標轉換為螢幕像素。

    物理座標單位為定點數 (1000 = 1 像素單位)。
    Y 軸代表深度，Z 軸代表垂直高度。
    螢幕 Y 加上 HUD_H 偏移，使遊戲場景顯示在 HUD 條下方。
    """
    screen_x = player.x / 1000.0
    screen_y = (player.y / 1000.0) - (player.z / 1000.0) + HUD_H
    return screen_x, screen_y
