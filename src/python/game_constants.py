try:
    from battlelite_core import STATE_IDLE, STATE_WALK, STATE_HURT, STATE_DEAD
except ImportError:
    STATE_IDLE, STATE_WALK, STATE_HURT, STATE_DEAD = 0, 1, 3, 5

# Ability state IDs — defined by Python, passed into Rust via set_ability()
STATE_ATTACK: int = 2
STATE_SKILL:  int = 4

__all__ = [
    "STATE_IDLE", "STATE_WALK", "STATE_ATTACK",
    "STATE_HURT", "STATE_SKILL", "STATE_DEAD",
]
