import pytest
from battlelite_core import Player

# 定義狀態常數 (與計畫對齊)
STATE_IDLE = 0
STATE_WALK = 1
STATE_ATTACK = 2
STATE_HURT = 3

def test_player_state_attribute():
    """
    驗證 Player 是否具備 state 屬性，且預設為 IDLE。
    """
    player = Player()
    assert hasattr(player, 'state')
    assert player.state == STATE_IDLE

def test_attack_trigger_logic():
    """
    驗證攻擊觸發邏輯。
    在 Rust 端實作後，我們預期透過 update 或是特定的 state 轉換來觸發。
    """
    player = Player()
    player.state = STATE_IDLE
    
    # 這裡我們模擬攻擊指令
    # 在實際 GGRS 中，這會由 input_mask 觸發
    # 目前測試直接修改狀態來驗證屬性讀寫
    player.state = STATE_ATTACK
    assert player.state == STATE_ATTACK

def test_basic_collision_detection():
    """
    驗證 2.5D 碰撞判定邏輯 (AABB)。
    測試兩位玩家在 X, Y 重疊且 Z 高度相近時是否判定為碰撞。
    """
    p1 = Player()
    p1.x, p1.y, p1.z = 1000, 1000, 0
    
    p2 = Player()
    p2.x, p2.y, p2.z = 1050, 1050, 0 # 非常接近 p1
    
    # 這裡我們預期 Rust 端會提供一個檢測函式
    if hasattr(p1, 'is_colliding_with'):
        result = p1.is_colliding_with(p2)
        assert result is True
    else:
        pytest.fail("Player 類別中找不到 'is_colliding_with' 判定函式")

def test_z_axis_collision_avoidance():
    """
    驗證 Z 軸高度對判定的影響。
    如果一方跳得太高，即便 X, Y 重疊也不應判定為碰撞。
    """
    p1 = Player()
    p1.x, p1.y, p1.z = 1000, 1000, 0
    
    p2 = Player()
    p2.x, p2.y, p2.z = 1000, 1000, 5000 # 在 p1 正上方但很高
    
    if hasattr(p1, 'is_colliding_with'):
        result = p1.is_colliding_with(p2)
        assert result is False, "Z 軸高度差過大時不應判定為碰撞"
