import os
from src.python.assets_manager.base_character import BaseCharacter, HitboxDef, CharStats, FxDef

_SHEET_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "src", "assets", "char", "mage", "sprite-sheet-151x100.png"
))

_FACE_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "src", "assets", "char", "mage", "faceset.png"
))

_FX_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "src", "assets", "fx"
))

_FRAME_W = 151
_FRAME_H = 100

# (state, row, num_frames, loop, speed)
_STATE_ROWS = [
    (0, 0, 5, True,  5),  # IDLE:   Row0 frame 0 static
    (1, 0, 5, True,  5),  # WALK:   Row0, 5 frames
    (2, 1, 5, False, 4),  # ATTACK: Row1 近身出拳
    (4, 2, 4, False, 8),  # SKILL:  Row2 發射投擲物
    (3, 3, 1, False, 4),  # HURT:   Row3
]

# ---------------------------------------------------------------------------
# 判定框（以 Sprite 中心為原點，單位 px，sheet 角色朝左）
#   Sprite 中心 = (75, 50)（151//2, 100//2）
# ---------------------------------------------------------------------------

_HURT_BODY = HitboxDef(ox=-25, oy=-87, w=70, h=87)   # bottom=0（腳）
_HURT_HURT = HitboxDef(ox=-30, oy=-80, w=70, h=80)

_HIT_ATTACK = HitboxDef(ox=-95, oy=-77, w=66, h=86)
_HIT_SKILL = HitboxDef(ox=-70, oy=-32, w=40, h=40)

STATE_IDLE, STATE_WALK, STATE_ATTACK, STATE_HURT, STATE_SKILL = 0, 1, 2, 3, 4


class Mage(BaseCharacter):
    def __init__(self):
        super().__init__("Mage")
        self.anchor_x = 12
        self.anchor_y = 42
        self.faceset_path = _FACE_PATH
        self.load_sheet(_SHEET_PATH, _FRAME_W, _FRAME_H, _STATE_ROWS)

        self.stats = CharStats(
            max_hp=70_000,
            max_mp=80_000,
            skill_cost=15_000,
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
            skl_melee_enabled=False,
            # SKILL 投射物參數 (For Rust)
            skl_projectile_vx=1_500,
            skl_projectile_lifetime=300,
            skl_spawn_timer=35,
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

        # 特效設定（路徑、切幀、位移、縮放、速度均可在此調整）
        self.atk_fx = FxDef(
            path=os.path.join(_FX_DIR, "8-b.png"),
            frame_w=193, frame_h=190,
            offset_x=0,
            offset_y=0,
            scale=0.4,     # 縮放（1.0 = 原始大小）
            speed=3,       # 每幀持續 game tick（越小越快）
        )

        self.skl_proj_fx = FxDef(
            path=os.path.join(_FX_DIR, "1.png"),
            frame_w=112, frame_h=100,
            offset_x=70,
            offset_y=20,
            scale=0.5,
            speed=5,
        )
