import pytest
import sys
import os

# 確保路徑正確以匯入 src
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.python.assets_manager.base_character import BaseCharacter

def test_animation_frame_selection():
    """
    驗證動畫系統是否能根據幀數正確循環或停止。
    """
    char = BaseCharacter("test_hero")
    # 模擬 3 幀的待機動畫 (循環)
    char.animations[0] = [1, 2, 3] # IDLE
    char.loop_map[0] = True
    char.speed_map[0] = 1  # speed=1 讓每個遊戲幀切換一次動畫幀

    # 模擬 2 幀的死亡動畫 (不循環)
    char.animations[5] = [10, 20] # DEAD
    char.loop_map[5] = False
    char.speed_map[5] = 1

    # 1. 測試 IDLE 循環
    assert char.get_frame_index(state=0, elapsed_frames=0) == 0
    assert char.get_frame_index(state=0, elapsed_frames=1) == 1
    assert char.get_frame_index(state=0, elapsed_frames=3) == 0 # 回到第 0 幀
    
    # 2. 測試 DEAD 播放一次後停止
    assert char.get_frame_index(state=5, elapsed_frames=0) == 0
    assert char.get_frame_index(state=5, elapsed_frames=1) == 1
    assert char.get_frame_index(state=5, elapsed_frames=5) == 1 # 停在最後一幀

def test_missing_state_graceful_handling():
    """
    驗證當請求不存在的狀態時，系統是否能優雅回傳預設值。
    """
    char = BaseCharacter("ghost")
    assert char.get_frame_index(state=99, elapsed_frames=10) == 0
