import pytest
from battlelite_core import Player

# --- 常數對齊 ---
STATE_IDLE = 0
STATE_WALK = 1
STATE_ATTACK = 2
STATE_HURT = 3
STATE_SKILL = 4

# --- 1. 基礎屬性測試 ---
def test_player_attributes():
    player = Player()
    # 座標與速度
    assert hasattr(player, 'x')
    assert hasattr(player, 'vx')
    assert player.x == 0
    assert player.vx == 0
    # 狀態
    assert player.state == STATE_IDLE
    assert player.facing_right is True
    # 數值
    assert player.hp == 100000
    assert player.mp == 50000

# --- 2. 2.5D 物理邏輯測試 ---
def test_gravity_and_ground():
    player = Player()
    player.z = 5000
    player.vz = 0
    
    # 執行物理更新 (應下降)
    player.update()
    assert player.z < 5000
    
    # 落地判定
    player.z = 100
    player.vz = -1000
    for _ in range(5):
        player.update()
    assert player.z == 0
    assert player.vz == 0

# --- 3. 戰鬥判定測試 ---
def test_attack_hit_detection():
    p1 = Player()
    p1.x, p1.y, p1.z = 100000, 100000, 0
    p1.facing_right = True
    
    p2 = Player()
    p2.x, p2.y, p2.z = 130000, 100000, 0 # 在 p1 右側 30px
    
    # 測試打中
    assert p1.check_attack_hit(p2) is True
    
    # 測試轉向後打不到
    p1.facing_right = False
    assert p1.check_attack_hit(p2) is False
    
    # 測試高度差避開
    p1.facing_right = True
    p2.z = 10000 # 跳很高
    assert p1.check_attack_hit(p2) is False

# --- 4. 數值系統測試 ---
def test_mp_regeneration():
    player = Player()
    player.mp = 10000
    player.update()
    # 預期 MP 回復 (常數 MP_REGEN = 50)
    assert player.mp == 10050

def test_state_timer_recovery():
    player = Player()
    player.state = STATE_ATTACK
    player.timer = 2
    
    player.update()
    assert player.state == STATE_ATTACK
    assert player.timer == 1
    
    player.update()
    assert player.state == STATE_IDLE
    assert player.timer == 0
