"""
BattleLite 渲染器模組
負責將 Rust 核心計算的物理座標轉換為 Pygame 的螢幕像素，並處理繪圖邏輯。
"""

def get_screen_pos(player):
    """
    將 Rust 2.5D 物理座標轉換為螢幕像素。
    
    物理座標單位為定點數 (1000 = 1 像素單位)。
    Y 軸代表深度，Z 軸代表垂直高度。
    螢幕 Y 座標會受到深度 (Y) 與高度 (Z) 的共同影響。
    
    Args:
        player: 來自 battlelite_core 的 Player 物件。
        
    Returns:
        tuple: (screen_x, screen_y)
    """
    # 按照 ARCHITECTURE.md 規範進行縮放與座標轉換
    screen_x = player.x / 1000.0
    
    # Y 軸公式: 深度位置 減去 垂直高度
    screen_y = (player.y / 1000.0) - (player.z / 1000.0)
    
    return screen_x, screen_y
