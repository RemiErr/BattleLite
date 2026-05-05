from src.python.game_constants import STATE_IDLE, STATE_WALK, STATE_ATTACK, STATE_HURT, STATE_SKILL
import os
from src.python.app_root import ROOT
from src.python.assets_manager.base_character import (
    BaseCharacter, HitboxDef, PhysicsStats, AbilityDef, FxDef,
    SfxDef, CharSfxConfig, INPUT_ATTACK, INPUT_SKILL
)

_SHEET_PATH = os.path.join(ROOT, "src", "assets",
                           "char", "wizard", "sprite-sheet-161x106.png")
_FACE_PATH = os.path.join(ROOT, "src", "assets",
                          "char", "wizard", "faceset.png")
_FX_DIR = os.path.join(ROOT, "src", "assets", "fx")
_SFX_DIR = os.path.join(ROOT, "src", "assets", "sound")

_FRAME_W = 161
_FRAME_H = 106
_COLS = 6

# (state, start_frame, num_frames, loop, speed)
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


CHAR_TYPE_WIZARD = 4


class Wizard(BaseCharacter):
    def __init__(self):
        super().__init__("Wizard")
        self.anchor_x = 8
        self.anchor_y = 40
        self.faceset_path = _FACE_PATH
        self.load_sheet_linear(_SHEET_PATH, _FRAME_W,
                               _FRAME_H, _COLS, _STATE_FRAMES)

        self.physics = PhysicsStats(
            max_hp=50_000,
            max_mp=100_000,
        )

        # atk_timer = 28 ticks；atk_hit_frame 3-5 × speed 4 = ticks 12-20
        # skl_timer = 72 ticks；skl_spawn_frame=14 → spawn_timer = 72 - 14*4 = 16
        # atk_spawn_timer=18（舊版 Rust timer 倒數值，直接使用）
        # atk_projectile_vx=-2_000（反向投射物，朝面向反方向發射）
        self.abilities = [
            AbilityDef(
                trigger_button=INPUT_ATTACK,
                state_id=STATE_ATTACK,
                mp_cost=3_000,
                timer=28,
                dmg=8_000,
                depth=25_000,
                kb_vx=5_000, kb_vz=8_000, kb_timer=25,
                melee_enabled=True,
                hit_frame_start=3, hit_frame_end=5,
                projectile_vx=-2_000,
                projectile_lifetime=15,
                spawn_timer_raw=18,
                hit_box=_HIT_ATTACK,
                proj_fx=FxDef(
                    path=os.path.join(_FX_DIR, "11.png"),
                    frame_w=83, frame_h=99,
                    offset_x=160, offset_y=0,
                    scale=0.6, speed=3,
                ),
                is_skill=False,
            ),
            AbilityDef(
                trigger_button=INPUT_SKILL,
                state_id=STATE_SKILL,
                mp_cost=30_000,
                timer=72,
                hp_regen=140,  # 回血量 = hp_regen * timer
                dmg=25_000,
                depth=60_000,
                kb_vx=3_000, kb_vz=16_000, kb_timer=35,
                melee_enabled=False,
                projectile_vx=10_000,
                projectile_lifetime=25,
                spawn_frame=14,
                hit_box=_HIT_SKILL,
                proj_fx=FxDef(
                    path=os.path.join(_FX_DIR, "9.png"),
                    frame_w=79, frame_h=46,
                    offset_x=112, offset_y=20,
                    scale=0.9, speed=3,
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
            on_ability={STATE_ATTACK: _s(1), STATE_SKILL: _s(20)},
            on_hit={},
            on_proj={STATE_ATTACK: _s(15), STATE_SKILL: _s(24)},
            on_hurt=_s(13), on_jump=_s(27), on_land=_s(23), on_dead=_s(15),
        )
