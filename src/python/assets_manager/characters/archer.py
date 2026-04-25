import os
from src.python.assets_manager.base_character import BaseCharacter, HitboxDef, CharStats, FxDef

_SHEET_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "src", "assets", "char", "archer", "sprite-sheet-158x173.png"
))

_FACE_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "src", "assets", "char", "archer", "faceset.png"
))

_FX_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "src", "assets", "fx"
))

_FRAME_W = 158
_FRAME_H = 173
_COLS = 8

# ---------------------------------------------------------------------------
# 線性幀索引（8 cols/row）
#   Row 0        : IDLE（第0幀）/ WALK（全8幀）
#   Row 1 + Row2 col0-2 : ATTACK（共11幀，start=8）
#   Row2 col3-7 + Row3-4 + Row5 col0-2 : SKILL（共24幀，start=19）
#   Row5 col5-7  : HURT（3幀，start=44）
# (state, start_frame, num_frames, loop, speed)
# ---------------------------------------------------------------------------
_STATE_FRAMES = [
    (0,  0,  1, True,  6),   # IDLE
    (1,  0,  8, True,  6),   # WALK
    (2,  8, 11, False, 4),   # ATTACK
    (4, 19, 24, False, 4),   # SKILL
    (3, 43,  3, False, 3),   # HURT
]

# ---------------------------------------------------------------------------
# 判定框（以 Sprite 中心為原點，px，sheet 角色朝左）
#   Sprite 中心 = (79, 86)（158//2, 173//2）
# ---------------------------------------------------------------------------

_HURT_BODY = HitboxDef(ox=-24, oy=-82, w=60, h=90)   # bottom=0（腳）
_HURT_HURT = HitboxDef(ox=-26, oy=-78, w=48, h=78)

_HIT_ATTACK = HitboxDef(ox=0, oy=-30, w=50, h=35)
_HIT_SKILL = HitboxDef(ox=0, oy=-40, w=80, h=45)

STATE_IDLE, STATE_WALK, STATE_ATTACK, STATE_HURT, STATE_SKILL = 0, 1, 2, 3, 4


class Archer(BaseCharacter):
    def __init__(self):
        super().__init__("Archer")
        self.anchor_x = 15
        self.anchor_y = 78
        self.faceset_path = _FACE_PATH
        self.load_sheet_linear(_SHEET_PATH, _FRAME_W,
                               _FRAME_H, _COLS, _STATE_FRAMES)

        # atk_timer = 11 frames * speed 4 = 44 ticks
        # skl_timer = 24 frames * speed 4 = 96 ticks；spawn_timer=36（第15幀放箭）
        self.stats = CharStats(
            max_hp=60_000,
            max_mp=60_000,
            skill_cost=30_000,
            atk_dmg=15_000,
            skill_dmg=50_000,
            atk_depth=25_000,
            skl_depth=40_000,
            atk_kb_vx=6_000,
            atk_kb_vz=4_000,
            atk_kb_timer=25,
            skl_kb_vx=10_000,
            skl_kb_vz=6_000,
            skl_kb_timer=35,
            skl_projectile_vx=15_000,
            skl_projectile_lifetime=80,
            skl_spawn_timer=12,
            atk_timer=44,
            skl_timer=96,
            atk_projectile_vx=25_000,
            atk_projectile_lifetime=50,
            atk_spawn_timer=15,
            atk_melee_enabled=False,
            skl_melee_enabled=False,
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
            STATE_ATTACK: _HIT_ATTACK,   # 傷害由投射物負責
            STATE_SKILL:  _HIT_SKILL,    # 傷害由投射物負責
            STATE_HURT:   None,
        }

        self.atk_proj_fx = FxDef(
            path=os.path.join(_FX_DIR, "3-b.png"),
            frame_w=127, frame_h=97,
            offset_x=80,
            offset_y=24,
            scale=0.6,
            speed=3,
        )
        # 箭矢實體視覺由 skl_proj_fx 驅動（飛行中持續循環）
        self.skl_proj_fx = FxDef(
            path=os.path.join(_FX_DIR, "3.png"),
            frame_w=127, frame_h=97,
            offset_x=100,
            offset_y=18,
            scale=0.8,
            speed=3,
        )
