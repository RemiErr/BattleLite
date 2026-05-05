from src.python.game_constants import STATE_IDLE, STATE_WALK, STATE_ATTACK, STATE_HURT, STATE_SKILL
import os
from src.python.app_root import ROOT
from src.python.assets_manager.base_character import (
    BaseCharacter, HitboxDef, PhysicsStats, AbilityDef, FxDef,
    SfxDef, CharSfxConfig, INPUT_ATTACK, INPUT_SKILL
)

_SHEET_PATH = os.path.join(ROOT, "src", "assets",
                           "char", "mage", "sprite-sheet-151x100.png")
_FACE_PATH = os.path.join(ROOT, "src", "assets", "char", "mage", "faceset.png")
_FX_DIR = os.path.join(ROOT, "src", "assets", "fx")
_SFX_DIR = os.path.join(ROOT, "src", "assets", "sound")

_FRAME_W = 151
_FRAME_H = 100

# (state, row, num_frames, loop, speed)
_STATE_ROWS = [
    (0, 0, 5, True,  5),  # IDLE:   Row0
    (1, 0, 5, True,  5),  # WALK:   Row0, 5 frames
    (2, 1, 5, False, 4),  # ATTACK: Row1 近身出拳
    (4, 2, 4, False, 8),  # SKILL:  Row2 發射投擲物
    (3, 3, 1, False, 4),  # HURT:   Row3
]

# ---------------------------------------------------------------------------
# 判定框（以 Sprite 中心 (75, 50) 為原點，px，sheet 角色朝左）
# ---------------------------------------------------------------------------

_HURT_BODY = HitboxDef(ox=-25, oy=-87, w=70, h=87)
_HURT_HURT = HitboxDef(ox=-30, oy=-80, w=70, h=80)

_HIT_ATTACK = HitboxDef(ox=-95, oy=-77, w=66, h=86)
_HIT_SKILL = HitboxDef(ox=-70, oy=-32, w=40, h=40)


class Mage(BaseCharacter):
    def __init__(self):
        super().__init__("Mage")
        self.anchor_x = 12
        self.anchor_y = 42
        self.faceset_path = _FACE_PATH
        self.load_sheet(_SHEET_PATH, _FRAME_W, _FRAME_H, _STATE_ROWS)

        self.physics = PhysicsStats(
            max_hp=70_000,
            max_mp=80_000,
        )

        # skl_timer = 4 frames × speed 8 = 32 ticks; spawn_timer_raw=35 → 用舊 timer 值
        # atk_timer = 5 frames × speed 4 = 20 ticks
        self.abilities = [
            AbilityDef(
                trigger_button=INPUT_ATTACK,
                state_id=STATE_ATTACK,
                timer=20,
                dmg=9_000,
                depth=25_000,
                kb_vx=5_000, kb_vz=3_000, kb_timer=20,
                melee_enabled=True,
                hit_box=_HIT_ATTACK,
                fx=FxDef(
                    path=os.path.join(_FX_DIR, "8-b.png"),
                    frame_w=193, frame_h=190,
                    offset_x=0, offset_y=0,
                    scale=0.4, speed=3,
                ),
                is_skill=False,
            ),
            AbilityDef(
                trigger_button=INPUT_SKILL,
                state_id=STATE_SKILL,
                mp_cost=20_000,
                timer=40,
                dmg=8_500,
                depth=40_000,
                kb_vx=6_000, kb_vz=7_500, kb_timer=40,
                melee_enabled=False,
                projectile_vx=1_500,
                projectile_lifetime=300,
                spawn_timer_raw=35,
                hit_box=_HIT_SKILL,
                proj_fx=FxDef(
                    path=os.path.join(_FX_DIR, "1.png"),
                    frame_w=112, frame_h=100,
                    offset_x=70, offset_y=20,
                    scale=0.5, speed=5,
                ),
                is_skill=True,
            ),
        ]

        self.hurt_boxes = {
            STATE_IDLE:   _HURT_BODY,
            STATE_WALK:   _HURT_BODY,
            STATE_ATTACK: _HURT_BODY,
            STATE_SKILL:  _HURT_BODY,
            STATE_HURT:   _HURT_HURT,
        }

        def _s(n): return SfxDef(os.path.join(_SFX_DIR, f"{n}.ogg"))
        self.sfx = CharSfxConfig(
            on_ability={STATE_ATTACK: _s(17)},
            on_hit={},
            on_proj={STATE_SKILL:  _s(26)},
            on_hurt=_s(13), on_jump=_s(27), on_land=_s(23), on_dead=_s(15),
        )
