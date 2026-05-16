import heapq
from src.python.ai.goap.action import GOAPAction


def plan(start_ws: dict, goal: dict, actions: list[GOAPAction],
         max_nodes: int = 200) -> list[GOAPAction]:
    """
    A* 搜尋最低 cost 的行動序列使 world_state 滿足 goal。
    回傳行動序列；若無解則回傳空列表（呼叫端 fallback 至 lv1 FSM）。
    """
    open_set   = [(0.0, 0, start_ws, [])]
    visited    = set()
    node_count = 0

    while open_set and node_count < max_nodes:
        cost, _, ws, actions_taken = heapq.heappop(open_set)
        node_count += 1

        state_key = _ws_to_key(ws)
        if state_key in visited:
            continue
        visited.add(state_key)

        if _satisfies_goal(ws, goal):
            return actions_taken

        for action in actions:
            if not action.is_applicable(ws):
                continue
            new_ws   = action.apply(ws)
            new_cost = cost + action.cost(ws)
            h        = _heuristic(new_ws, goal)
            heapq.heappush(
                open_set,
                (new_cost + h, id(new_ws), new_ws, actions_taken + [action])
            )

    return []


def _satisfies_goal(ws: dict, goal: dict) -> bool:
    for key, val in goal.items():
        ws_val = ws.get(key, 0)
        if isinstance(val, tuple):
            op, threshold = val
            if op == "<=" and not (ws_val <= threshold): return False
            if op == ">=" and not (ws_val >= threshold): return False
        elif ws_val != val:
            return False
    return True


def _heuristic(ws: dict, goal: dict) -> float:
    """啟發值：對手剩餘 HP 除以單次攻擊傷害估算（5000/hit）。"""
    return max(0.0, ws.get("opp_hp", 0) / 5_000.0)


def _ws_to_key(ws: dict) -> tuple:
    """取 Layer 1 離散欄位做 visited 去重（排除 fuzzy 向量，避免 unhashable）。"""
    keys = ("in_range", "in_danger", "y_aligned", "self_hp", "self_mp", "opp_hp", "opp_state",
            "self_airborne")
    return tuple(ws.get(k) for k in keys)
