from src.python.ai.characters.profile import CharAIProfile
from src.python.ai.controllers.pattern_ai import Pattern, TOWARD
from src.python.ai.predicates import can_use_skill, opponent_is_vulnerable, self_hp_low
from src.python.game_constants import INPUT_JUMP as J, INPUT_ATTACK as ATK, INPUT_SKILL as SKL

KNIGHT_PROFILE = CharAIProfile(
    preferred_range=70_000, skill_mp_threshold=15_000, aggression=0.8)

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
