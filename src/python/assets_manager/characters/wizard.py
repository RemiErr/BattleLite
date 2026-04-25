import os
from src.python.assets_manager.base_character import BaseCharacter, HitboxDef, CharStats, FxDef

_SHEET_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "src", "assets", "char", "wizard", "sprite-sheet-161x106.png"
))

_FACE_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "src", "assets", "char", "wizard", "faceset.png"
))

_FX_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "src", "assets", "fx"
))

_FRAME_W = 161
_FRAME_H = 106
_COLS = 6

# ---------------------------------------------------------------------------
# 線性幀索引（6 cols/row，sheet 966×636）
#   Row 0  (frames  0- 5): IDLE / WALK（6 幀）
#   Row 1  (frames  6-11)
#   Row 2  (frames 12-17): ATTACK 跨列（6+1=7 幀，frames 6-12）
#   Row 2-4 (frames 13-30): SKILL 閃電 AOE（18 幀）
#   Row 5  (frames 31-35): HURT（5 幀）
#
# (state, start_frame, num_frames, loop, speed)
# ---------------------------------------------------------------------------
_STATE_FRAMES = [
    (0,  0,  7, True,  7),   # IDLE
    (1,  0,  7, True,  7),   # WALK
    (2,  7,  7, False, 4),   # ATTACK
    (4, 14, 18, False, 4),   # SKILL
    (3, 32,  4, False, 4),   # HURT
]

# ---------------------------------------------------------------------------
# 判定框（以 Sprite 中心 (80, 53) 為原點，px，sheet 角色朝左）
# ---------------------------------------------------------------------------

_HURT_BODY = HitboxDef(ox=-30, oy=-82, w=66, h=90)
_HURT_HURT = HitboxDef(ox=-18, oy=-72, w=38, h=72)

_HIT_ATTACK = HitboxDef(ox=-80, oy=-50, w=56, h=30)
_HIT_SKILL = HitboxDef(ox=-80, oy=-34, w=80, h=40)

STATE_IDLE, STATE_WALK, STATE_ATTACK, STATE_HURT, STATE_SKILL = 0, 1, 2, 3, 4

CHAR_TYPE_WIZARD = 4


class Wizard(BaseCharacter):
    def __init__(self):
        super().__init__("Wizard")
        self.anchor_x = 8
        self.anchor_y = 40
        self.faceset_path = _FACE_PATH
        self.load_sheet_linear(_SHEET_PATH, _FRAME_W,
                               _FRAME_H, _COLS, _STATE_FRAMES)

        self.stats = CharStats(
            max_hp=50_000,
            max_mp=100_000,
            skill_cost=25_000,
            atk_dmg=10_000,
            skill_dmg=25_000,
            atk_depth=25_000,
            skl_depth=60_000,       # 覆蓋 Y 軸廣 (深度大)
            atk_kb_vx=3_200,
            atk_kb_vz=8_000,
            atk_kb_timer=22,
            skl_kb_vx=5_000,
            skl_kb_vz=15_000,       # 往上擊飛
            skl_kb_timer=38,
            atk_timer=28,
            skl_timer=72,
            atk_melee_enabled=True,
            skl_melee_enabled=False,  # entity 判定
            atk_hit_frame_start=3,
            atk_hit_frame_end=5,
            atk_projectile_vx=-2_000,
            atk_projectile_lifetime=15,
            atk_spawn_timer=18,
            # entity 參數
            skl_projectile_vx=10_000,
            skl_projectile_lifetime=25,
            skl_spawn_frame=14,
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

        self.atk_proj_fx = FxDef(
            path=os.path.join(_FX_DIR, "11.png"),
            frame_w=83, frame_h=99,
            offset_x=160,
            offset_y=0,
            scale=0.6,
            speed=3,
        )

        self.skl_proj_fx = FxDef(
            path=os.path.join(_FX_DIR, "9.png"),
            frame_w=79, frame_h=46,
            offset_x=112,
            offset_y=20,
            scale=0.9,
            speed=3,
        )
