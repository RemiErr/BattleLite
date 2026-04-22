import os
import pygame
from src.python.assets_manager.base_character import BaseCharacter, HitboxDef

_SHEET_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "src", "assets", "char", "knight", "sprite-sheet-183-123.png"
)

_FRAME_W = 183
_FRAME_H = 123

# (state, row, num_frames, loop, speed)
_STATE_ROWS = [
    (0, 0, 1, True,  6),  # IDLE:   Row0, 1 frame
    (1, 0, 6, True,  6),  # WALK:   Row0, 6 frames
    (2, 1, 6, False, 4),  # ATTACK: Row1
    (4, 2, 6, False, 4),  # SKILL:  Row2 (Guard)
    (3, 3, 6, False, 4),  # HURT:   Row3
]

# ---------------------------------------------------------------------------
# 判定框（以 Sprite 中心為原點，單位 px，預設 sheet 角色朝左）
#
#   Sprite 中心 = (91, 61)（183//2, 123//2）
#
#   hurt_box（身體被打到的範圍）
#     Row0 量測：角色身體大約 frame x=18–85, y=10–108
#     → ox = 18-91 = -73, oy = 10-61 = -51, w=67, h=98
#
#   hit_box（攻擊傷害範圍）
#     ATTACK Row1 幀2–3 的弧形特效大約 frame x=0–55, y=8–82
#     （角色朝左，弧形出現在 frame 左側 = 角色前方）
#     → ox = 0-91 = -91, oy = 8-61 = -53, w=55, h=74
#
#     SKILL Row2 幀4–5 的盾牌光暈大約 frame x=40–100, y=15–90
#     → ox = 40-91 = -51, oy = 15-61 = -46, w=60, h=75
# ---------------------------------------------------------------------------

_HURT_BODY = HitboxDef(ox=-73, oy=-51, w=67, h=98)
_HURT_HURT = HitboxDef(ox=-60, oy=-40, w=55, h=80)   # HURT 狀態身體縮小

_HIT_ATTACK = HitboxDef(ox=-91, oy=-53, w=55, h=74)
_HIT_SKILL  = HitboxDef(ox=-51, oy=-46, w=60, h=75)

STATE_IDLE, STATE_WALK, STATE_ATTACK, STATE_HURT, STATE_SKILL = 0, 1, 2, 3, 4


class Knight(BaseCharacter):
    def __init__(self):
        super().__init__("Knight")
        self.load_sheet(
            os.path.normpath(_SHEET_PATH),
            _FRAME_W, _FRAME_H,
            _STATE_ROWS,
        )

        self.hurt_boxes = {
            STATE_IDLE:   _HURT_BODY,
            STATE_WALK:   _HURT_BODY,
            STATE_ATTACK: _HURT_BODY,
            STATE_SKILL:  _HURT_BODY,
            STATE_HURT:   _HURT_HURT,
        }

        self.hit_boxes = {
            STATE_IDLE:   None,
            STATE_WALK:   None,
            STATE_ATTACK: _HIT_ATTACK,
            STATE_SKILL:  _HIT_SKILL,
            STATE_HURT:   None,
        }

    def get_sprite(self, state: int, elapsed_frames: int, facing_right: bool = True) -> pygame.Surface:
        surf = self.get_sprite_rect(state, elapsed_frames)
        if surf is None:
            surf = self.get_sprite_rect(0, 0)
        assert surf is not None
        # 原始 sheet 角色朝左，facing_right 時需水平翻轉
        if facing_right:
            return pygame.transform.flip(surf, True, False)
        return surf
