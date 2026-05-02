from src.python.ai.goap.action      import GOAPAction
from src.python.ai.goap.world_state import HP_VAR
from src.python.game_constants import INPUT_ATTACK

# ── mode 乘數表 ───────────────────────────────────────────────────────────────
_ATTACK_MULT = {
    "gamble":       0.3,   # 孤注一擲：瘋狂攻擊
    "aggressive":   0.5,   # 激進：積極出拳
    "balanced":     1.0,
    "conservative": 1.4,   # 保守：能不打就不打
}
_RETREAT_MULT = {
    "gamble":       2.5,   # 孤注一擲：絕不後退
    "aggressive":   1.8,   # 激進：不輕易撤
    "balanced":     1.0,
    "conservative": 0.5,   # 保守：隨時準備撤
}
# 技能 MP 加權：mode 決定 MP 不足時是否仍積極使用技能
_SKILL_MP_W = {
    "gamble":       {"low": 0.5, "mid": 0.3, "high": 0.2},  # 傾家蕩產也要放
    "aggressive":   {"low": 1.0, "mid": 0.6, "high": 0.3},  # MP 低時也願意放
    "balanced":     {"low": 2.5, "mid": 1.0, "high": 0.3},
    "conservative": {"low": 3.0, "mid": 1.5, "high": 0.6},  # MP 低時節省
}


def attack_mult(ws: dict) -> float:
    return _ATTACK_MULT.get(ws.get("mode", "balanced"), 1.0)


def retreat_mult(ws: dict) -> float:
    return _RETREAT_MULT.get(ws.get("mode", "balanced"), 1.0)


def skill_mp_weights(ws: dict) -> dict:
    return _SKILL_MP_W.get(ws.get("mode", "balanced"), _SKILL_MP_W["balanced"])


# ── 通用 Action 工廠 ──────────────────────────────────────────────────────────

def make_approach(profile) -> GOAPAction:
    return GOAPAction(
        name="靠近",
        preconditions={"in_range": False},
        effects={"in_range": True},
        base_cost=1.0,
        input_mask=0,
        direction="toward",
        duration_frames=12,
        cost_fn=lambda ws: (1.0 - profile.aggression * 0.4) * (
            0.6 if ws.get("mode") in ("aggressive", "gamble") else 1.0),
    )


def make_retreat(profile) -> GOAPAction:
    return GOAPAction(
        name="後退",
        preconditions={"in_danger": True},
        effects={"in_range": False, "in_danger": False},
        base_cost=1.0,
        input_mask=0,
        direction="away",
        duration_frames=12,
        cost_fn=lambda ws: (
            HP_VAR.weighted(ws["self_hp"], {"low": 0.3, "mid": 0.8, "high": 1.5}) *
            retreat_mult(ws)
        ),
    )


def make_y_align(base_cost: float = 0.4, duration_frames: int = 30) -> GOAPAction:
    """遠程角色 Y 軸對位動作：X 遠離保持射程，Y 靠近對齊深度。"""
    return GOAPAction(
        name="Y軸對位",
        preconditions={"y_aligned": False},
        effects={"y_aligned": True, "in_range": False},
        base_cost=base_cost,
        input_mask=0,
        direction="away_x_toward_y",
        duration_frames=duration_frames,
    )


def make_attack() -> GOAPAction:
    return GOAPAction(
        name="普攻",
        preconditions={"in_range": True},
        effects={"opp_hp": ("delta", -5_000)},
        base_cost=1.0,
        input_mask=INPUT_ATTACK,
        duration_frames=6,
        cost_fn=lambda ws: attack_mult(ws),
    )
