from src.python.ai.characters.profile import CharAIProfile
from src.python.ai.controllers.pattern_ai import Pattern, TOWARD, AWAY
from src.python.ai.predicates import can_use_skill, opponent_is_vulnerable
from src.python.ai.goap.action      import GOAPAction
from src.python.ai.goap.world_state import MP_VAR
from src.python.ai.goap.base_actions import make_approach, make_retreat, make_attack
from src.python.game_constants import INPUT_ATTACK as ATK, INPUT_SKILL as SKL

WIZARD_PROFILE = CharAIProfile(
    preferred_range=90_000, skill_mp_threshold=15_000, aggression=0.6)

# ── lv2 Pattern 表 ────────────────────────────────────────────────────────────
WIZARD_PATTERNS = [
    Pattern(
        name="對手受傷 AOE",
        condition=lambda ws: opponent_is_vulnerable(ws) and ws["dist"] <= 120_000,
        action_sequence=[SKL],
        step_duration=[1],
        priority=10, cooldown_frames=20,
    ),
    Pattern(
        name="近戰反向彈",
        condition=lambda ws: ws["dist"] <= 80_000,
        action_sequence=[ATK, AWAY, TOWARD, ATK],
        step_duration=[6, 8, 1, 1],
        priority=9, cooldown_frames=20,
    ),
    Pattern(
        name="AOE 技能",
        condition=lambda ws: can_use_skill(ws, WIZARD_PROFILE) and ws["dist"] <= 120_000,
        action_sequence=[SKL],
        step_duration=[1],
        priority=8, cooldown_frames=40,
    ),
]

# ── lv3 GOAP Action 表 ────────────────────────────────────────────────────────
_WIZARD_AOE = GOAPAction(
    name="AOE 爆炸",
    preconditions={"in_range": True, "self_mp": (">=", 15_000)},
    effects={"opp_hp": ("delta", -12_000), "in_range": False},
    base_cost=0.6,
    input_mask=SKL,
    duration_frames=1,
    cost_fn=lambda ws: MP_VAR.weighted(
        ws["self_mp"], {"low": 2.5, "mid": 1.0, "high": 0.3}),
)

_WIZARD_PROJECTILE = GOAPAction(
    name="投射物",
    preconditions={"in_range": False},
    effects={"opp_hp": ("delta", -4_000)},
    base_cost=0.9,
    input_mask=ATK,
    duration_frames=1,
)

WIZARD_GOAP_ACTIONS = [
    make_approach(WIZARD_PROFILE),
    make_retreat(WIZARD_PROFILE),
    make_attack(),
    _WIZARD_AOE,
    _WIZARD_PROJECTILE,
]
