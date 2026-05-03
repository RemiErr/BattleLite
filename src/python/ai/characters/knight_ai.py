from src.python.ai.characters.profile import CharAIProfile
from src.python.ai.controllers.pattern_ai import Pattern, TOWARD
from src.python.ai.predicates import can_use_skill, opponent_is_vulnerable, self_hp_low
from src.python.ai.goap.action      import GOAPAction
from src.python.ai.goap.world_state import MP_VAR
from src.python.ai.goap.base_actions import (
    make_approach, make_retreat, make_attack, attack_mult, skill_mp_weights)
from src.python.game_constants import (
    INPUT_JUMP as J, INPUT_ATTACK as ATK, INPUT_SKILL as SKL)

KNIGHT_PROFILE = CharAIProfile(
    preferred_range=70_000, skill_mp_threshold=15_000, aggression=0.8,
    attack_range=65_000)

# ── lv2 Pattern 表 ────────────────────────────────────────────────────────────
KNIGHT_PATTERNS = [
    Pattern(
        name="對手受傷追擊",
        condition=lambda ws: opponent_is_vulnerable(ws) and ws["dist"] <= 100_000,
        action_sequence=[ATK, ATK, ATK],
        step_duration=[6, 6, 6],
        priority=10, cooldown_frames=10,
    ),
    Pattern(
        name="衝刺攻擊",
        condition=lambda ws: ws["dist"] > 80_000 and not opponent_is_vulnerable(ws),
        action_sequence=[TOWARD, TOWARD | ATK, ATK, ATK],
        step_duration=[8, 1, 6, 6],
        priority=8, cooldown_frames=20,
    ),
    Pattern(
        name="技能衝入",
        condition=lambda ws: can_use_skill(ws, KNIGHT_PROFILE) and ws["dist"] > 60_000,
        action_sequence=[SKL, ATK, ATK],
        step_duration=[1, 6, 6],
        priority=7, cooldown_frames=40,
    ),
    Pattern(
        name="低血躍進",
        condition=lambda ws: self_hp_low(ws, 250) and ws["dist"] <= 80_000,
        action_sequence=[J | ATK, ATK],
        step_duration=[1, 6],
        priority=6, cooldown_frames=30,
    ),
]

# ── lv3 GOAP Action 表 ────────────────────────────────────────────────────────
_KNIGHT_CHARGE = GOAPAction(
    name="突進斬",
    preconditions={"in_range": False, "y_aligned": True, "self_mp": (">=", 15_000)},
    effects={"in_range": True, "opp_hp": ("delta", -8_000)},
    base_cost=0.8,
    input_mask=SKL,
    duration_frames=1,
    cost_fn=lambda ws: MP_VAR.weighted(ws["self_mp"], skill_mp_weights(ws)) * attack_mult(ws),
)

_KNIGHT_Y_ALIGN = GOAPAction(
    name="Y軸靠近",
    preconditions={"y_aligned": False},
    effects={"y_aligned": True},
    base_cost=0.5,
    input_mask=0,
    direction="toward",
    duration_frames=20,
)

KNIGHT_GOAP_ACTIONS = [
    make_approach(KNIGHT_PROFILE),
    make_retreat(KNIGHT_PROFILE),
    make_attack(),
    _KNIGHT_CHARGE,
    _KNIGHT_Y_ALIGN,
]
