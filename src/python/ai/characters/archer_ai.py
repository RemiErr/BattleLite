from src.python.ai.characters.profile import CharAIProfile
from src.python.ai.controllers.pattern_ai import Pattern, TOWARD, AWAY
from src.python.ai.predicates import can_use_skill, opponent_approaching
from src.python.ai.goap.action      import GOAPAction
from src.python.ai.goap.world_state import HP_VAR, MP_VAR
from src.python.ai.goap.base_actions import (
    make_approach, make_retreat, make_y_align, attack_mult, retreat_mult, skill_mp_weights)
from src.python.game_constants import (
    INPUT_JUMP as J, INPUT_ATTACK as ATK, INPUT_SKILL as SKL)

ARCHER_PROFILE = CharAIProfile(
    preferred_range=160_000, skill_mp_threshold=18_000, aggression=0.6,
    attack_range=100_000)  # 超過此距離才用弓箭；近戰觸發跳躍逃脫

# ── lv2 Pattern 表 ────────────────────────────────────────────────────────────
ARCHER_PATTERNS = [
    Pattern(
        name="跳躍閃避",
        condition=lambda ws: opponent_approaching(ws) and ws["dist"] < 100_000,
        action_sequence=[J, J | AWAY],
        step_duration=[1, 12],
        priority=10, cooldown_frames=40,
    ),
    Pattern(
        name="蓄力箭",
        condition=lambda ws: (can_use_skill(ws, ARCHER_PROFILE)
                              and ws["dist"] >= 100_000
                              and ws["dist_y"] <= 20_000),
        action_sequence=[TOWARD, SKL, 0, 0, 0],
        step_duration=[1, 1, 15, 10, 1],
        priority=9, cooldown_frames=35,
    ),
    Pattern(
        name="連射",
        condition=lambda ws: 80_000 <= ws["dist"] <= 200_000 and ws["dist_y"] <= 20_000,
        action_sequence=[ATK, 0, ATK, 0, ATK],
        step_duration=[1, 4, 1, 4, 1],
        priority=7, cooldown_frames=20,
    ),
]

# ── lv3 GOAP Action 表 ────────────────────────────────────────────────────────
_ARCHER_ARROW = GOAPAction(
    name="普通箭矢",
    preconditions={"in_range": False, "y_aligned": True},
    effects={"opp_hp": ("delta", -4_000)},
    base_cost=0.8,
    input_mask=ATK,
    duration_frames=1,
)

_ARCHER_CHARGED = GOAPAction(
    name="蓄力箭",
    preconditions={"in_range": False, "y_aligned": True, "self_mp": (">=", 18_000)},
    effects={"opp_hp": ("delta", -12_000)},
    base_cost=0.5,
    input_mask=SKL,
    duration_frames=1,
    cost_fn=lambda ws: MP_VAR.weighted(ws["self_mp"], skill_mp_weights(ws)) * attack_mult(ws),
)

_ARCHER_JUMP_ESCAPE = GOAPAction(
    name="跳躍逃脫",
    preconditions={"in_range": True, "self_airborne": False},
    effects={"in_range": False, "self_airborne": True},
    base_cost=0.5,
    input_mask=J,
    direction="away",
    duration_frames=1,
    cost_fn=lambda ws: HP_VAR.weighted(
        ws["self_hp"], {"low": 0.2, "mid": 0.5, "high": 1.2}) * retreat_mult(ws),
)

ARCHER_GOAP_ACTIONS = [
    make_approach(ARCHER_PROFILE),
    make_retreat(ARCHER_PROFILE),
    make_y_align(),
    _ARCHER_ARROW,
    _ARCHER_CHARGED,
    _ARCHER_JUMP_ESCAPE,
]
