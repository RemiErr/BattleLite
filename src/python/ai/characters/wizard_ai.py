from src.python.ai.characters.profile import CharAIProfile
from src.python.ai.controllers.pattern_ai import Pattern, TOWARD, AWAY
from src.python.ai.predicates import can_use_skill, opponent_is_vulnerable
from src.python.game_constants import INPUT_ATTACK as ATK, INPUT_SKILL as SKL

WIZARD_PROFILE = CharAIProfile(
    preferred_range=90_000, skill_mp_threshold=15_000, aggression=0.6)

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
