import pytest
from battlelite_core import Player

# 定義狀態常數 (包含新的 SKILL 狀態)
STATE_IDLE = 0
STATE_WALK = 1
STATE_ATTACK = 2
STATE_HURT = 3
STATE_SKILL = 4

def test_player_stats_attributes():
    """
    驗證 Player 是否具備 HP 與 MP 屬性。
    """
    player = Player()
    # 預期初始屬性
    assert hasattr(player, 'hp')
    assert hasattr(player, 'mp')
    assert player.hp > 0
    assert player.mp >= 0

def test_mp_regeneration():
    """
    驗證 MP 是否會隨時間自動回復。
    """
    player = Player()
    player.mp = 1000
    initial_mp = player.mp
    
    # 執行物理更新
    player.update()
    
    assert player.mp > initial_mp, "執行 update 後 MP 應該增加 (自動回復)"

def test_skill_cost_logic():
    """
    驗證施放技能是否會消耗 MP。
    """
    player = Player()
    player.mp = 20000 # 20.0 MP
    player.state = STATE_IDLE
    
    # 這裡我們預期在實作後，透過某種觸發邏輯進入 SKILL 狀態
    # 目前測試直接修改狀態來驗證 Rust 內部的扣除邏輯
    # (或者我們可以測試當 mp 不足時是否能進入 SKILL 狀態)
    pass
