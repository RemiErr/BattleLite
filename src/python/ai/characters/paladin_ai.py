from src.python.ai.characters.profile import CharAIProfile
from src.python.ai.controllers.pattern_ai import Pattern
from src.python.ai.predicates import can_use_skill, self_hp_low
from src.python.ai.goap.action      import GOAPAction
from src.python.ai.goap.world_state import HP_VAR, MP_VAR
from src.python.ai.goap.base_actions import make_approach, make_retreat, make_attack
from src.python.game_constants import INPUT_ATTACK as ATK, INPUT_SKILL as SKL

PALADIN_PROFILE = CharAIProfile(
    preferred_range=80_000, skill_mp_threshold=12_000, aggression=0.5)

# ── lv2 Pattern 表 ────────────────────────────────────────────────────────────
PALADIN_PATTERNS = [
    Pattern(
        name="防護盾反",
        condition=lambda ws: self_hp_low(ws, 400) and ws["dist"] <= 100_000,
        action_sequence=[SKL, 0, 0, ATK, ATK],
        step_duration=[1, 20, 10, 6, 6],
        priority=10, cooldown_frames=60,
    ),
    Pattern(
        name="技能強攻",
        condition=lambda ws: can_use_skill(ws, PALADIN_PROFILE) and ws["dist"] <= 90_000,
        action_sequence=[SKL, ATK, ATK],
        step_duration=[1, 6, 6],
        priority=8, cooldown_frames=40,
    ),
    Pattern(
        name="穩定輸出",
        condition=lambda ws: ws["dist"] <= 80_000,
        action_sequence=[ATK, 0, ATK, 0, ATK],
        step_duration=[6, 4, 6, 4, 6],
        priority=6, cooldown_frames=15,
    ),
]

# ── lv3 GOAP Action 表 ────────────────────────────────────────────────────────
_PALADIN_SHIELD = GOAPAction(
    name="防護盾",
    preconditions={"in_range": True, "self_mp": (">=", 12_000)},
    effects={"in_range": False},
    base_cost=0.5,
    input_mask=SKL,
    duration_frames=1,
    cost_fn=lambda ws: HP_VAR.weighted(
        ws["self_hp"], {"low": 0.2, "mid": 0.6, "high": 2.0}),
)

_PALADIN_HEAVY = GOAPAction(
    name="重擊",
    preconditions={"in_range": True, "self_mp": (">=", 12_000)},
    effects={"opp_hp": ("delta", -8_000)},
    base_cost=0.7,
    input_mask=SKL,
    duration_frames=6,
    cost_fn=lambda ws: MP_VAR.weighted(
        ws["self_mp"], {"low": 2.0, "mid": 1.0, "high": 0.6}),
)

PALADIN_GOAP_ACTIONS = [
    make_approach(PALADIN_PROFILE),
    make_retreat(PALADIN_PROFILE),
    make_attack(),
    _PALADIN_SHIELD,
    _PALADIN_HEAVY,
]
