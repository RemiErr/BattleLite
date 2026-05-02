from src.python.ai.fuzzy.membership import triangular, trapezoidal
from src.python.ai.fuzzy.variable   import FuzzyVariable, FuzzySet

# 用絕對值而非比例，避免各角色 max_hp 不同造成 fuzzy 錯位
# HP 範圍：Archer 40k ～ Knight 100k
HP_VAR = FuzzyVariable("hp", [
    FuzzySet("low",  trapezoidal(0,       0,      12_000,  25_000)),
    FuzzySet("mid",  triangular (12_000, 45_000,  75_000)),
    FuzzySet("high", trapezoidal(45_000, 75_000, 300_000, 300_000)),
])

# MP 範圍：Knight 50k ～ Wizard 100k
MP_VAR = FuzzyVariable("mp", [
    FuzzySet("low",  trapezoidal(0,       0,      10_000,  20_000)),
    FuzzySet("mid",  triangular (10_000, 35_000,  60_000)),
    FuzzySet("high", trapezoidal(35_000, 60_000, 200_000, 200_000)),
])

DIST_VAR = FuzzyVariable("dist", [
    FuzzySet("close", trapezoidal(0.0,     0.0,      60_000,  120_000)),
    FuzzySet("mid",   triangular (60_000,  140_000,  220_000)),
    FuzzySet("far",   trapezoidal(160_000, 240_000,  1e9,     1e9)),
])

# in_range 與 y_aligned 加入離散鍵，用於觸發 re-planning
_DOM_RANK       = {"low": 0, "mid": 1, "high": 2}
_DISCRETE_KEYS  = {"opp_state", "hp_adv", "y_aligned", "in_range"}
_FUZZY_DOM_KEYS = {"self_hp_dom", "self_mp_dom", "dist_dom", "opp_hp_dom"}

# 必須小於或等於 Rust Core 的 ATK_DEPTH_REACH (25,000)
Y_ALIGN_THRESHOLD = 20_000


def _hp_advantage(self_hp: int, opp_hp: int, self_dom: str, opp_dom: str) -> str:
    sr = _DOM_RANK[self_dom]
    or_ = _DOM_RANK[opp_dom]
    if sr != or_:
        return "ahead" if sr > or_ else "behind"
    if opp_hp < self_hp * 0.8:
        return "ahead"
    if opp_hp > self_hp * 1.25:
        return "behind"
    return "even"


MAX_PLAN_AGE = 45


def build_goap_world_state(ai_p, opp_p, attack_range: int = 80_000, prev_ws: dict = None) -> dict:
    dx   = abs(ai_p.x - opp_p.x)
    dy   = abs(ai_p.y - opp_p.y)
    dist = max(dx, dy)

    # 引入遲滯機制（Hysteresis）防止在邊界處抖動
    if prev_ws and "in_range" in prev_ws:
        # 如果原本在範圍內，給予 10% 的緩衝空間才判定為離開
        if prev_ws["in_range"]:
            in_range = dist <= attack_range * 1.1
        else:
            in_range = dist <= attack_range * 0.9
    else:
        in_range = dist <= attack_range

    if prev_ws and "y_aligned" in prev_ws:
        if prev_ws["y_aligned"]:
            y_aligned = dy <= Y_ALIGN_THRESHOLD * 1.2
        else:
            y_aligned = dy <= Y_ALIGN_THRESHOLD * 0.8
    else:
        y_aligned = dy <= Y_ALIGN_THRESHOLD

    opp_moving_toward = (
        (opp_p.vx > 0 and opp_p.x < ai_p.x) or
        (opp_p.vx < 0 and opp_p.x > ai_p.x)
    )

    return {
        # Layer 1：規劃器原始值
        "dist":          dist,
        "in_range":      in_range,
        "in_danger":     dist <= 180_000,
        "y_aligned":     y_aligned,
        "self_hp":       ai_p.hp,
        "self_mp":       ai_p.mp,
        "opp_hp":        opp_p.hp,
        "opp_state":     opp_p.state,
        "opp_vx_toward": opp_moving_toward,
        "self_airborne": ai_p.z > 0,

        # Layer 2：主導集合（用於 re-planning 觸發）
        "self_hp_dom":  HP_VAR.dominant(ai_p.hp),
        "self_mp_dom":  MP_VAR.dominant(ai_p.mp),
        "dist_dom":     DIST_VAR.dominant(dist),
        "opp_hp_dom":   HP_VAR.dominant(opp_p.hp),
        "hp_adv":       _hp_advantage(ai_p.hp, opp_p.hp,
                                      HP_VAR.dominant(ai_p.hp),
                                      HP_VAR.dominant(opp_p.hp)),

        # Layer 3：隸屬度向量（用於動態 cost）
        "self_hp_fuzzy": HP_VAR.evaluate(ai_p.hp),
        "self_mp_fuzzy": MP_VAR.evaluate(ai_p.mp),
        "dist_fuzzy":    DIST_VAR.evaluate(dist),
    }


def should_replan(prev_ws: dict, curr_ws: dict) -> bool:
    discrete_changed = any(
        prev_ws.get(k) != curr_ws.get(k) for k in _DISCRETE_KEYS
    )
    fuzzy_shifted = any(
        prev_ws.get(k) != curr_ws.get(k) for k in _FUZZY_DOM_KEYS
    )
    return discrete_changed or fuzzy_shifted
