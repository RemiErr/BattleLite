from src.python.ai.characters.profile import CharAIProfile
from src.python.ai.controllers.pattern_ai import Pattern, TOWARD, AWAY
from src.python.ai.predicates import can_use_skill, opponent_is_vulnerable, opponent_approaching
from src.python.ai.goap.action      import GOAPAction
from src.python.ai.goap.world_state import HP_VAR, MP_VAR
from src.python.ai.goap.base_actions import (
    make_approach, make_retreat, attack_mult, retreat_mult, skill_mp_weights)
from src.python.game_constants import (
    INPUT_JUMP as J, INPUT_ATTACK as ATK, INPUT_SKILL as SKL)

MAGE_PROFILE = CharAIProfile(
    preferred_range=200_000, skill_mp_threshold=20_000, aggression=0.4,
    attack_range=120_000)  # 超過此距離才用魔法彈；近戰觸發跳躍逃脫

# ── lv2 Pattern 表 ────────────────────────────────────────────────────────────
MAGE_PATTERNS = [
    Pattern(
        name="近戰逃脫",
        condition=lambda ws: ws["dist"] < 100_000,
        action_sequence=[J, AWAY, AWAY, TOWARD, SKL],
        step_duration=[1, 8, 8, 1, 1],
        priority=10, cooldown_frames=20,
    ),
    Pattern(
        name="遠距魔法彈",
        condition=lambda ws: can_use_skill(ws, MAGE_PROFILE) and ws["dist"] >= 120_000,
        action_sequence=[SKL],
        step_duration=[1],
        priority=9, cooldown_frames=30,
    ),
    Pattern(
        name="對手受傷補刀",
        condition=lambda ws: opponent_is_vulnerable(ws) and ws["dist"] < 200_000,
        action_sequence=[SKL],
        step_duration=[1],
        priority=8, cooldown_frames=15,
    ),
    Pattern(
        name="拉距後放",
        condition=lambda ws: opponent_approaching(ws) and ws["dist"] < 160_000,
        action_sequence=[AWAY, AWAY, AWAY, TOWARD, SKL],
        step_duration=[10, 8, 8, 1, 1],
        priority=7, cooldown_frames=25,
    ),
]

# ── lv3 GOAP Action 表 ────────────────────────────────────────────────────────
_MAGE_FIREBALL = GOAPAction(
    name="魔法彈",
    preconditions={"in_range": False, "self_mp": (">=", 20_000)},
    effects={"opp_hp": ("delta", -15_000)},
    base_cost=0.5,
    input_mask=SKL,
    duration_frames=1,
    cost_fn=lambda ws: MP_VAR.weighted(ws["self_mp"], skill_mp_weights(ws)) * attack_mult(ws),
)

_MAGE_CLOSE_ATTACK = GOAPAction(
    name="被迫近戰",
    preconditions={"in_range": True},
    effects={"opp_hp": ("delta", -3_000)},
    base_cost=2.0,
    input_mask=ATK,
    duration_frames=6,
)

_MAGE_JUMP_RETREAT = GOAPAction(
    name="跳躍逃脫",
    preconditions={"in_range": True, "self_airborne": False},
    effects={"in_range": False, "self_airborne": True},
    base_cost=0.6,
    input_mask=J,
    duration_frames=1,
    cost_fn=lambda ws: HP_VAR.weighted(
        ws["self_hp"], {"low": 0.2, "mid": 0.6, "high": 1.2}) * retreat_mult(ws),
)

MAGE_GOAP_ACTIONS = [
    make_approach(MAGE_PROFILE),
    make_retreat(MAGE_PROFILE),
    _MAGE_CLOSE_ATTACK,
    _MAGE_FIREBALL,
    _MAGE_JUMP_RETREAT,
]
