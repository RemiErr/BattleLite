from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass
class GOAPAction:
    name:            str
    preconditions:   dict[str, Any]
    effects:         dict[str, Any]
    base_cost:       float
    input_mask:      int
    duration_frames: int = 1
    # "toward" / "away" 時忽略 input_mask，執行時依位置動態解算方向
    direction:       str | None = None
    cost_fn: Callable[[dict], float] | None = field(default=None, repr=False)

    def cost(self, world_state: dict) -> float:
        return self.cost_fn(world_state) if self.cost_fn else self.base_cost

    def is_applicable(self, world_state: dict) -> bool:
        for key, val in self.preconditions.items():
            ws_val = world_state.get(key)
            if isinstance(val, tuple):
                op, threshold = val
                if op == ">=" and not (ws_val >= threshold): return False
                if op == "<=" and not (ws_val <= threshold): return False
                if op == ">"  and not (ws_val >  threshold): return False
                if op == "<"  and not (ws_val <  threshold): return False
            elif ws_val != val:
                return False
        return True

    def apply(self, world_state: dict) -> dict:
        new_ws = dict(world_state)
        for key, val in self.effects.items():
            if isinstance(val, tuple) and val[0] == "delta":
                new_ws[key] = new_ws.get(key, 0) + val[1]
            else:
                new_ws[key] = val
        return new_ws
