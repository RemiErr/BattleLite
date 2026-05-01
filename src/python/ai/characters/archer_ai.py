from src.python.ai.characters.profile import CharAIProfile
from src.python.ai.controllers.pattern_ai import Pattern, TOWARD, AWAY
from src.python.ai.predicates import can_use_skill, opponent_approaching
from src.python.game_constants import INPUT_JUMP as J, INPUT_ATTACK as ATK, INPUT_SKILL as SKL

ARCHER_PROFILE = CharAIProfile(
    preferred_range=160_000, skill_mp_threshold=18_000, aggression=0.6)

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
        condition=lambda ws: can_use_skill(ws, ARCHER_PROFILE) and ws["dist"] >= 100_000,
        action_sequence=[TOWARD, SKL, 0, 0, 0],
        step_duration=[1, 1, 15, 10, 1],
        priority=9, cooldown_frames=35,
    ),
    Pattern(
        name="連射",
        condition=lambda ws: 80_000 <= ws["dist"] <= 200_000,
        action_sequence=[ATK, 0, ATK, 0, ATK],
        step_duration=[1, 4, 1, 4, 1],
        priority=7, cooldown_frames=20,
    ),
]
