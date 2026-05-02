from src.python.ai.characters.profile import CharAIProfile
from src.python.game_constants import STATE_HURT


def is_in_preferred_range(ws: dict, profile: CharAIProfile) -> bool:
    return ws["dist"] <= profile.preferred_range


def can_use_skill(ws: dict, profile: CharAIProfile) -> bool:
    return ws["self_mp"] >= profile.skill_mp_threshold


def opponent_is_vulnerable(ws: dict) -> bool:
    return ws["opp_state"] == STATE_HURT


def self_hp_low(ws: dict, threshold: int = 300) -> bool:
    return ws["self_hp"] < threshold


def opponent_approaching(ws: dict) -> bool:
    return ws["opp_vx_toward"]
