import pytest
from battlelite_core import Player

def test_player_velocity_attributes():
    """
    驗證 Player 是否具備速度屬性 vx, vy, vz。
    """
    player = Player()
    # 預期初始速度均為 0
    assert hasattr(player, 'vx')
    assert hasattr(player, 'vy')
    assert hasattr(player, 'vz')
    assert player.vx == 0
    assert player.vy == 0
    assert player.vz == 0

def test_gravity_effect():
    """
    驗證重力是否作用於 Z 軸。
    在空中 (Z > 0) 的玩家，執行物理更新後 Z 座標應該減少。
    """
    player = Player()
    player.z = 5000  # 設在空中
    
    # 這裡我們預期 Rust 端會有一個 update 函式來推進物理
    if hasattr(player, 'update'):
        player.update()
        assert player.z < 5000, f"執行 update 後玩家應下降，但目前 Z={player.z}"
    else:
        pytest.fail("Player 類別中找不到 'update' 物理更新函式")

def test_ground_collision():
    """
    驗證落地判定。玩家不應該掉出地板 (Z < 0)。
    """
    player = Player()
    player.z = 100   # 接近地面
    player.vz = -1000 # 正在高速下墜
    
    if hasattr(player, 'update'):
        # 執行多次更新模擬下墜
        for _ in range(5):
            player.update()
        
        assert player.z == 0, f"玩家應停在地面 (Z=0)，但目前 Z={player.z}"
        assert player.vz == 0, "落地後垂直速度應歸零"
    else:
        pytest.fail("Player 類別中找不到 'update' 物理更新函式")
