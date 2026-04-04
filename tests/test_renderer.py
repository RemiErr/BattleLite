import pytest
from battlelite_core import Player

def test_coordinate_conversion():
    """
    驗證渲染器是否能正確將 Rust 的 2.5D 物理座標轉換為 Pygame 的 2D 螢幕像素。
    公式: 
    Screen X = Physical X / 1000
    Screen Y = (Physical Y / 1000) - (Physical Z / 1000)
    """
    try:
        from src.python.renderer import get_screen_pos
    except (ImportError, ModuleNotFoundError):
        import sys
        import os
        # 強制加入根目錄到路徑中
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        from src.python.renderer import get_screen_pos

    # 模擬一個玩家在 X=1000, Y=2000, Z=500 (1.0, 2.0, 0.5)
    player = Player()
    player.x = 1000
    player.y = 2000
    player.z = 500
    
    screen_x, screen_y = get_screen_pos(player)
    
    # 預期結果: X=1, Y=2-0.5 = 1.5 -> 轉整數 1, 1 (Pygame 座標通常為整數)
    assert screen_x == 1
    assert screen_y == 1.5 or int(screen_y) == 1
