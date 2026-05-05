from src.python.game_constants import STATE_IDLE, STATE_WALK, STATE_ATTACK, STATE_HURT, STATE_SKILL
import os
from app_root import ROOT
from src.python.assets_manager.base_character import (
    BaseCharacter, HitboxDef, PhysicsStats, AbilityDef,
    SfxDef, CharSfxConfig, INPUT_ATTACK, INPUT_SKILL
)

_SHEET_PATH = os.path.join(ROOT, "src", "assets",
                           "char", "knight", "sprite-sheet-183-123.png")
_FACE_PATH = os.path.join(ROOT, "src", "assets",
                          "char", "knight", "faceset.png")
_SFX_DIR = os.path.join(ROOT, "src", "assets", "sound")

_FRAME_W = 182
_FRAME_H = 122

# (state, row, num_frames, loop, speed)
_STATE_ROWS = [
    (0, 0, 6, True,  6),  # IDLE:   Row0, 6 frames
    (1, 0, 6, True,  6),  # WALK:   Row0, 6 frames
    (2, 1, 6, False, 4),  # ATTACK: Row1
    (4, 2, 6, False, 4),  # SKILL:  Row2 (Guard)
    (3, 3, 6, False, 4),  # HURT:   Row3
]

# ---------------------------------------------------------------------------
# 判定框（以 Sprite 中心 (91, 61) 為原點，單位 px，sheet 角色朝左）
# ---------------------------------------------------------------------------

_HURT_BODY = HitboxDef(ox=-35, oy=-80, w=80, h=100)
_HURT_HURT = HitboxDef(ox=-15, oy=-80, w=70, h=90)

_HIT_ATTACK = HitboxDef(ox=-86, oy=-92, w=75, h=110)


class Knight(BaseCharacter):
    def __init__(self):
        super().__init__("Knight")
        self.anchor_y = 41
        self.faceset_path = _FACE_PATH
        self.load_sheet(
            os.path.normpath(_SHEET_PATH),
            _FRAME_W, _FRAME_H,
            _STATE_ROWS,
        )

        self.physics = PhysicsStats(
            max_hp=100_000,
            max_mp=50_000,
        )

        # atk_timer = 6 frames × speed 4 = 24 ticks
        # skl_timer = 6 frames × speed 4 = 24 ticks
        self.abilities = [
            AbilityDef(
                trigger_button=INPUT_ATTACK,
                state_id=STATE_ATTACK,
                timer=24,
                dmg=10_000,
                depth=40_000,
                on_hit_restore=5_000,
                kb_vx=5_000, kb_vz=6_000, kb_timer=30,
                dash_vx=10_000, dash_frame=2,
                melee_enabled=True,
                hit_box=_HIT_ATTACK,
                is_skill=False,
            ),
            AbilityDef(
                trigger_button=INPUT_SKILL,
                state_id=STATE_SKILL,
                mp_cost=10_000,
                timer=24,
                dmg=0,
                depth=40_000,
                damage_absorb=30_000,
                kb_vx=0, kb_vz=0, kb_timer=0,
                melee_enabled=False,
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
            on_ability={STATE_SKILL: _s(29)},
            on_hit={STATE_ATTACK: _s(1)},
            on_hurt=_s(13), on_jump=_s(27), on_land=_s(23), on_dead=_s(15),
        )
