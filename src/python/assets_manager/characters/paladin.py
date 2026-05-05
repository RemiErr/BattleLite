from src.python.game_constants import STATE_IDLE, STATE_WALK, STATE_ATTACK, STATE_HURT, STATE_SKILL
import os
from src.python.app_root import ROOT
from src.python.assets_manager.base_character import (
    BaseCharacter, HitboxDef, PhysicsStats, AbilityDef,
    SfxDef, CharSfxConfig, INPUT_ATTACK, INPUT_SKILL
)

_SHEET_PATH = os.path.join(ROOT, "src", "assets",
                           "char", "paladin", "sprite-sheet-249x100.png")
_FACE_PATH = os.path.join(ROOT, "src", "assets",
                          "char", "paladin", "faceset.png")
_SFX_DIR = os.path.join(ROOT, "src", "assets", "sound")

_FRAME_W = 249
_FRAME_H = 100
_COLS = 6

# (state, start_frame, num_frames, loop, speed)
_STATE_FRAMES = [
    (0,  0,  8, True,  8),   # IDLE
    (1,  0,  8, True,  8),   # WALK
    (2,  8, 11, False, 6),   # ATTACK  speed=6
    (4, 22, 18, False, 4),   # SKILL   speed=4
    (3, 19,  3, False, 3),   # HURT
]

# ---------------------------------------------------------------------------
# 判定框（以 Sprite 中心 (124, 50) 為原點，px，sheet 角色朝左）
# ---------------------------------------------------------------------------

_HURT_BODY = HitboxDef(ox=-20, oy=-82, w=60, h=82)
_HURT_HURT = HitboxDef(ox=-15, oy=-78, w=48, h=78)

_HIT_ATTACK = HitboxDef(ox=-140, oy=-62, w=130, h=36)
_HIT_SKILL = HitboxDef(ox=-160, oy=-92, w=180, h=100)


CHAR_TYPE_PALADIN = 3


class Paladin(BaseCharacter):
    def __init__(self):
        super().__init__("Paladin")
        self.anchor_x = 20
        self.anchor_y = 42
        self.faceset_path = _FACE_PATH
        self.load_sheet_linear(_SHEET_PATH, _FRAME_W,
                               _FRAME_H, _COLS, _STATE_FRAMES)

        self.physics = PhysicsStats(
            max_hp=90_000,
            max_mp=75_000,
        )

        # atk_timer = 44 ticks（與舊 CharStats 對齊）；atk_spd=6 用於 hit/dash 幀轉 ticks
        # skl_timer = 18 frames × speed 4 = 72 ticks
        # atk_hit_frame 4-7 × speed 6 = ticks 24-42
        # skl_hit_frame 13-17 × speed 4 = ticks 52-68
        # dash_frame 4 × speed 6 = tick 24
        self.abilities = [
            AbilityDef(
                trigger_button=INPUT_ATTACK,
                state_id=STATE_ATTACK,
                mp_cost=5_000,
                timer=44,
                dmg=10_000,
                depth=20_000,
                kb_vx=8_500, kb_vz=5_000, kb_timer=30,
                melee_enabled=True,
                hit_frame_start=4, hit_frame_end=7,
                dash_vx=80_000, dash_frame=4,
                on_hit_restore=15_000,
                hit_box=_HIT_ATTACK,
                is_skill=False,
            ),
            AbilityDef(
                trigger_button=INPUT_SKILL,
                state_id=STATE_SKILL,
                mp_cost=25_000,
                timer=72,
                dmg=30_000,
                depth=40_000,
                kb_vx=16_500, kb_vz=12_000, kb_timer=65,
                melee_enabled=True,
                hit_frame_start=13, hit_frame_end=17,
                damage_absorb=10_000,
                hit_box=_HIT_SKILL,
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
            on_hit={STATE_ATTACK: _s(14), STATE_SKILL: _s(24)},
            on_hurt=_s(13), on_jump=_s(27), on_land=_s(23), on_dead=_s(15),
        )
