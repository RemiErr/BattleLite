import os
from src.python.assets_manager.base_character import BaseCharacter, HitboxDef, CharStats

_SHEET_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "src", "assets", "char", "paladin", "sprite-sheet-249x100.png"
))

_FACE_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "src", "assets", "char", "paladin", "faceset.png"
))

_FRAME_W = 249
_FRAME_H = 100
_COLS = 6

# ---------------------------------------------------------------------------
# 線性幀索引（6 cols/row）
#   Row 0 (0-7)   : IDLE / WALK（idle.gif 8 幀）
#   Row 1-2 (8-18): ATTACK（attack.gif 11 幀）
#   Row 3-5 (19-21): HURT（hit.gif 3 幀）
#   Row 3-6 (22-39): SKILL 聖光斬（attack2.gif 18 幀）
# (state, start_frame, num_frames, loop, speed)
# ---------------------------------------------------------------------------
_STATE_FRAMES = [
    (0,  0,  1, True,  6),   # IDLE
    (1,  0,  8, True,  6),   # WALK
    (2,  8, 11, False, 6),   # ATTACK
    (4, 22, 18, False, 4),   # SKILL
    (3, 19,  3, False, 3),   # HURT
]

# ---------------------------------------------------------------------------
# 判定框（以 Sprite 中心 (124, 50) 為原點，px，sheet 角色朝左）
# ---------------------------------------------------------------------------

_HURT_BODY = HitboxDef(ox=-20, oy=-82, w=60, h=82)   # bottom=0（腳）
_HURT_HURT = HitboxDef(ox=-15, oy=-78, w=48, h=78)

_HIT_ATTACK = HitboxDef(ox=-140, oy=-62, w=130, h=36)
_HIT_SKILL = HitboxDef(ox=-160, oy=-92, w=180, h=100)

STATE_IDLE, STATE_WALK, STATE_ATTACK, STATE_HURT, STATE_SKILL = 0, 1, 2, 3, 4

CHAR_TYPE_PALADIN = 3


class Paladin(BaseCharacter):
    def __init__(self):
        super().__init__("Paladin")
        self.anchor_x = 20
        self.anchor_y = 42
        self.faceset_path = _FACE_PATH
        self.load_sheet_linear(_SHEET_PATH, _FRAME_W,
                               _FRAME_H, _COLS, _STATE_FRAMES)

        # atk_timer = 11 frames * speed 4 = 44 ticks
        # skl_timer = 18 frames * speed 4 = 72 ticks
        # atk_timer = 11 frames * speed 4 = 44 ticks
        # skl_timer = 18 frames * speed 4 = 72 ticks
        self.stats = CharStats(
            max_hp=120_000,
            max_mp=75_000,
            skill_cost=30_000,
            atk_dmg=15_000,
            skill_dmg=30_000,
            atk_depth=25_000,
            skl_depth=40_000,
            atk_kb_vx=8_500,
            atk_kb_vz=5_000,
            atk_kb_timer=30,
            skl_kb_vx=16_500,
            skl_kb_vz=12_000,
            skl_kb_timer=65,
            atk_timer=44,
            skl_timer=72,
            atk_melee_enabled=True,
            skl_melee_enabled=True,
            atk_hit_frame_start=4,
            atk_hit_frame_end=7,
            skl_hit_frame_start=13,
            skl_hit_frame_end=17,
            skl_damage_absorb=10_000,
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
