from src.python.ai.characters.profile import CharAIProfile
from src.python.ai.controllers.pattern_ai import Pattern
from src.python.ai.predicates import can_use_skill, self_hp_low
from src.python.game_constants import INPUT_ATTACK as ATK, INPUT_SKILL as SKL

PALADIN_PROFILE = CharAIProfile(
    preferred_range=80_000, skill_mp_threshold=12_000, aggression=0.5)

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
