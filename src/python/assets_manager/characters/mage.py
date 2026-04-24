import os
from src.python.assets_manager.base_character import BaseCharacter, HitboxDef, CharStats

_SHEET_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "src", "assets", "char", "mage", "sprite-sheet-151x100.png"
))

_FACE_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "src", "assets", "char", "mage", "faceset.png"
))

_FRAME_W = 151
_FRAME_H = 100

# (state, row, num_frames, loop, speed)
_STATE_ROWS = [
    (0, 0, 1, True,  6),  # IDLE:   Row0 frame 0 static
    (1, 0, 5, True,  6),  # WALK:   Row0, 5 frames
    (2, 1, 5, False, 4),  # ATTACK: Row1 近身出拳
    (4, 2, 5, False, 4),  # SKILL:  Row2 發射投擲物
    (3, 3, 1, False, 4),  # HURT:   Row3
]

# ---------------------------------------------------------------------------
# 判定框（以 Sprite 中心為原點，單位 px，sheet 角色朝左）
#
#   Sprite 中心 = (75, 50)（151//2, 100//2）
#
#   hurt_box：身體從 x≈28~115, y≈5~92
#     → ox = 28-75 = -47, oy = 5-50 = -45, w=87, h=87
#
#   hit_box ATTACK：出拳延伸至 x≈8~68, y≈18~62
#     → ox = 8-75 = -67, oy = 18-50 = -32, w=60, h=44
#
#   hit_box SKILL：飛踢範圍 x≈5~88, y≈22~68
#     → ox = 5-75 = -70, oy = 22-50 = -28, w=83, h=46
# ---------------------------------------------------------------------------

_HURT_BODY = HitboxDef(ox=-47, oy=-45, w=87, h=87)
_HURT_HURT = HitboxDef(ox=-30, oy=-38, w=70, h=78)   # HURT 狀態縮小

_HIT_ATTACK = HitboxDef(ox=-67, oy=-32, w=60, h=44)
_HIT_SKILL  = HitboxDef(ox=-70, oy=-28, w=83, h=46)

STATE_IDLE, STATE_WALK, STATE_ATTACK, STATE_HURT, STATE_SKILL = 0, 1, 2, 3, 4


class Mage(BaseCharacter):
    def __init__(self):
        super().__init__("Mage")
        self.faceset_path = _FACE_PATH
        self.load_sheet(
            _SHEET_PATH,
            _FRAME_W, _FRAME_H,
            _STATE_ROWS,
        )

        self.stats = CharStats(
            max_hp=70_000,
            max_mp=80_000,
            skill_cost=25_000,
            atk_dmg=8_000,
            skill_dmg=20_000,
            atk_depth=25_000,
            skl_depth=40_000,
            atk_kb_vx=5_000,
            atk_kb_vz=3_000,
            atk_kb_timer=20,
            skl_kb_vx=7_000,
            skl_kb_vz=5_000,
            skl_kb_timer=30,
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

