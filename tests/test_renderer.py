import pytest
from battlelite_core import Player

def test_coordinate_conversion():
    """
    驗證渲染器是否能正確將 Rust 的 2.5D 物理座標轉換為 Pygame 的 2D 螢幕像素。
    公式:
    Screen X = Physical X / 1000
    Screen Y = (Physical Y / 1000) - (Physical Z / 1000) + HUD_H
    """
    from src.python.renderer import get_screen_pos
    from src.python.hud import HUD_H

    player = Player()
    player.x = 1000
    player.y = 2000
    player.z = 500

    screen_x, screen_y = get_screen_pos(player)

    assert screen_x == 1.0
    assert screen_y == (2000 / 1000) - (500 / 1000) + HUD_H  # 61.5
