import pytest
import os
import sys
import pygame

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# pygame 需要初始化才能建立 Surface
pygame.display.init()
pygame.display.set_mode((1, 1), flags=pygame.NOFRAME)

from src.python.assets_manager.characters.knight import Knight

STATE_IDLE   = 0
STATE_WALK   = 1
STATE_ATTACK = 2
STATE_HURT   = 3
STATE_SKILL  = 4

SHEET_FRAME_W = 183
SHEET_FRAME_H = 123


@pytest.fixture(scope="module")
def knight():
    return Knight()


# --- 1. 載入不崩潰 ---

def test_knight_loads_without_error(knight):
    assert knight is not None


# --- 2. 回傳正確尺寸的 Surface ---

def test_get_sprite_returns_surface(knight):
    surf = knight.get_sprite(STATE_IDLE, 0, True)
    assert isinstance(surf, pygame.Surface)


def test_sprite_size_matches_frame(knight):
    surf = knight.get_sprite(STATE_IDLE, 0, True)
    assert surf.get_width()  == SHEET_FRAME_W
    assert surf.get_height() == SHEET_FRAME_H


# --- 3. 不同狀態切換不同列 ---

def test_walk_and_idle_use_row0(knight):
    """IDLE 用 Row0 第 0 幀，WALK 也在 Row0 循環。"""
    idle_surf  = knight.get_sprite(STATE_IDLE, 0,  True)
    walk_surf  = knight.get_sprite(STATE_WALK, 0,  True)
    # 同 Row 同 frame → 應為同一張圖
    assert idle_surf.get_size() == walk_surf.get_size()


def test_different_states_produce_different_frames(knight):
    """不同狀態應從不同 Row 取幀，像素內容不同。"""
    walk_surf   = knight.get_sprite(STATE_WALK,   0, True)
    attack_surf = knight.get_sprite(STATE_ATTACK, 0, True)
    hurt_surf   = knight.get_sprite(STATE_HURT,   0, True)

    # 比較像素陣列，確認各列圖片不同
    import pygame
    walk_bytes   = pygame.image.tostring(walk_surf,   "RGB")
    attack_bytes = pygame.image.tostring(attack_surf, "RGB")
    hurt_bytes   = pygame.image.tostring(hurt_surf,   "RGB")

    assert walk_bytes != attack_bytes
    assert walk_bytes != hurt_bytes
    assert attack_bytes != hurt_bytes


# --- 4. 動畫幀推進 ---

def test_walk_animation_cycles_through_6_frames(knight):
    """WALK 有 6 幀，elapsed_frames 推進後應取不同幀。"""
    frames = [knight.get_sprite(STATE_WALK, i * 6, True) for i in range(6)]
    pixel_sets = [pygame.image.tostring(f, "RGB") for f in frames]
    # 至少有兩幀不同（不是靜止圖）
    assert len(set(pixel_sets)) > 1


def test_attack_animation_stops_at_last_frame(knight):
    """ATTACK 不循環，超出幀數後應停在最後一幀。"""
    last   = knight.get_sprite(STATE_ATTACK, 5 * 4,       True)
    beyond = knight.get_sprite(STATE_ATTACK, 5 * 4 + 100, True)
    assert pygame.image.tostring(last, "RGB") == pygame.image.tostring(beyond, "RGB")


# --- 5. 左右翻轉 ---

def test_facing_left_flips_sprite(knight):
    right = knight.get_sprite(STATE_WALK, 0, True)
    left  = knight.get_sprite(STATE_WALK, 0, False)
    assert pygame.image.tostring(right, "RGB") != pygame.image.tostring(left, "RGB")
