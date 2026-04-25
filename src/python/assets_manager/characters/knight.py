import os
from src.python.assets_manager.base_character import BaseCharacter, HitboxDef, CharStats

_SHEET_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "src", "assets", "char", "knight", "sprite-sheet-183-123.png"
)

_FACE_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "src", "assets", "char", "knight", "faceset.png"
))

_FRAME_W = 182
_FRAME_H = 122

# (state, row, num_frames, loop, speed)
_STATE_ROWS = [
    (0, 0, 1, True,  6),  # IDLE:   Row0, 1 frame
    (1, 0, 6, True,  6),  # WALK:   Row0, 6 frames
    (2, 1, 6, False, 4),  # ATTACK: Row1
    (4, 2, 6, False, 4),  # SKILL:  Row2 (Guard)
    (3, 3, 6, False, 4),  # HURT:   Row3
]

# ---------------------------------------------------------------------------
# 判定框（以 Sprite 中心為原點，單位 px，預設 sheet 角色朝左）
#
#   Sprite 中心 = (91, 61)（183//2, 123//2）
#
#   hurt_box（身體被打到的範圍）
#     Row0 量測：角色身體大約 frame x=18–85, y=10–108
#     → ox = 18-91 = -73, oy = 10-61 = -51, w=67, h=98
#
#   hit_box（攻擊傷害範圍）
#     ATTACK Row1 幀2–3 的弧形特效大約 frame x=0–55, y=8–82
#     （角色朝左，弧形出現在 frame 左側 = 角色前方）
#     → ox = 0-91 = -91, oy = 8-61 = -53, w=55, h=74
#
#     SKILL Row2 幀4–5 的盾牌光暈大約 frame x=40–100, y=15–90
#     → ox = 40-91 = -51, oy = 15-61 = -46, w=60, h=75
# ---------------------------------------------------------------------------

_HURT_BODY = HitboxDef(ox=-35, oy=-80, w=80, h=100)   # bottom=0（腳）
_HURT_HURT = HitboxDef(ox=-15, oy=-80, w=70, h=90)

_HIT_ATTACK = HitboxDef(ox=-86, oy=-92, w=75, h=110)
_HIT_SKILL = HitboxDef(ox=-60, oy=-72, w=66, h=85)

STATE_IDLE, STATE_WALK, STATE_ATTACK, STATE_HURT, STATE_SKILL = 0, 1, 2, 3, 4


class Knight(BaseCharacter):
    def __init__(self):
        super().__init__("Knight")
        self.anchor_y = 41   # 幀中心偏移量 (向下)
        self.faceset_path = _FACE_PATH
        self.load_sheet(
            os.path.normpath(_SHEET_PATH),
            _FRAME_W, _FRAME_H,
            _STATE_ROWS,
        )

        self.stats = CharStats(
            max_hp=100_000,
            max_mp=50_000,
            skill_cost=20_000,
            atk_dmg=10_000,
            skill_dmg=15_000,
            atk_depth=25_000,
            skl_depth=40_000,
            atk_kb_vx=8_000,
            atk_kb_vz=4_000,
            atk_kb_timer=30,
            skl_kb_vx=8_000,
            skl_kb_vz=6_000,
            skl_kb_timer=40,
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
