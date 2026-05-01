from src.python.ai.characters.profile import CharAIProfile
from src.python.ai.controllers.pattern_ai import Pattern, TOWARD, AWAY
from src.python.ai.predicates import can_use_skill, opponent_is_vulnerable, opponent_approaching
from src.python.game_constants import INPUT_JUMP as J, INPUT_SKILL as SKL

MAGE_PROFILE = CharAIProfile(
    preferred_range=200_000, skill_mp_threshold=20_000, aggression=0.4)

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
