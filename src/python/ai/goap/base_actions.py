from src.python.ai.goap.action      import GOAPAction
from src.python.ai.goap.world_state import HP_VAR
from src.python.game_constants import INPUT_ATTACK


def make_approach(profile) -> GOAPAction:
    return GOAPAction(
        name="靠近",
        preconditions={"in_range": False},
        effects={"in_range": True},
        base_cost=1.0,
        input_mask=0,
        direction="toward",
        duration_frames=12,
        cost_fn=lambda ws: 1.0 - profile.aggression * 0.4,
    )


def make_retreat(profile) -> GOAPAction:
    return GOAPAction(
        name="後退",
        preconditions={"in_range": True},
        effects={"in_range": False},
        base_cost=1.0,
        input_mask=0,
        direction="away",
        duration_frames=12,
        # 直接傳入原始 HP（已改為絕對值）
        cost_fn=lambda ws: HP_VAR.weighted(
            ws["self_hp"],
            {"low": 0.3, "mid": 0.8, "high": 1.5},
        ),
    )


def make_attack() -> GOAPAction:
    return GOAPAction(
        name="普攻",
        preconditions={"in_range": True},
        effects={"opp_hp": ("delta", -5_000)},   # 符合實際 HP 數量級
        base_cost=1.0,
        input_mask=INPUT_ATTACK,
        duration_frames=6,
    )
