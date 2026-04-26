import os
from src.python.assets_manager.base_character import (
    BaseCharacter, HitboxDef, PhysicsStats, AbilityDef, FxDef,
    SfxDef, CharSfxConfig, INPUT_ATTACK, INPUT_SKILL
)

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

_SFX_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "src", "assets", "sound"
))

_FRAME_W = 158
_FRAME_H = 173
_COLS = 8

# (state, start_frame, num_frames, loop, speed)
_STATE_FRAMES = [
    (0,  0,  8, True,  8),   # IDLE
    (1,  0,  8, True,  8),   # WALK
    (2,  8, 11, False, 4),   # ATTACK
    (4, 19, 24, False, 4),   # SKILL
    (3, 43,  3, False, 3),   # HURT
]

# ---------------------------------------------------------------------------
# 判定框（以 Sprite 中心 (79, 86) 為原點，px，sheet 角色朝左）
# ---------------------------------------------------------------------------

_HURT_BODY = HitboxDef(ox=-24, oy=-82, w=60, h=90)
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

        self.physics = PhysicsStats(
            max_hp=60_000,
            max_mp=60_000,
        )

        # atk_timer = 11 frames × speed 4 = 44 ticks；第 15 幀觸發（atk_spawn_timer=15）
        # skl_timer = 24 frames × speed 4 = 96 ticks；第 12 幀觸發（skl_spawn_timer=12 → Rust timer=84）
        self.abilities = [
            AbilityDef(
                trigger_button=INPUT_ATTACK,
                state_id=STATE_ATTACK,
                timer=44,
                dmg=15_000,
                depth=25_000,
                kb_vx=6_000, kb_vz=4_000, kb_timer=25,
                melee_enabled=False,
                projectile_vx=25_000,
                projectile_lifetime=50,
                spawn_timer_raw=15,
                hit_box=_HIT_ATTACK,
                proj_fx=FxDef(
                    path=os.path.join(_FX_DIR, "3-b.png"),
                    frame_w=127, frame_h=97,
                    offset_x=80, offset_y=24,
                    scale=0.6, speed=3,
                ),
                is_skill=False,
            ),
            AbilityDef(
                trigger_button=INPUT_SKILL,
                state_id=STATE_SKILL,
                mp_cost=30_000,
                timer=96,
                dmg=50_000,
                depth=40_000,
                kb_vx=10_000, kb_vz=6_000, kb_timer=35,
                melee_enabled=False,
                projectile_vx=15_000,
                projectile_lifetime=80,
                spawn_timer_raw=12,
                hit_box=_HIT_SKILL,
                proj_fx=FxDef(
                    path=os.path.join(_FX_DIR, "3.png"),
                    frame_w=127, frame_h=97,
                    offset_x=100, offset_y=18,
                    scale=0.8, speed=3,
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
            on_ability={STATE_SKILL: _s(20)},
            on_proj={STATE_ATTACK: _s(12), STATE_SKILL: _s(11)},
            on_hurt=_s(13), on_jump=_s(27), on_land=_s(23), on_dead=_s(15),
        )
