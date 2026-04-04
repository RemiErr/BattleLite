import pytest

def test_player_entity_initialization():
    """
    驗證是否能從 Rust 模組建立 Player 物件，且其初始座標為 0。
    """
    try:
        from battlelite_core import Player
    except ImportError:
        pytest.fail("battlelite_core 模組中找不到 'Player' 類別。")

    # 建立玩家實體
    player = Player()
    
    # 預期初始座標 X, Y, Z 均為 0 (定點數表示)
    assert player.x == 0
    assert player.y == 0
    assert player.z == 0

def test_player_coordinate_modification():
    """
    驗證 Python 是否能手動修改 Player 的 X, Y, Z 座標。
    """
    from battlelite_core import Player
    player = Player()
    
    # 修改座標
    player.x = 1500  # 代表 1.5
    player.y = 2000  # 代表 2.0
    player.z = 500   # 代表 0.5
    
    assert player.x == 1500
    assert player.y == 2000
    assert player.z == 500
