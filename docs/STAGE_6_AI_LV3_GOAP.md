# BattleLite Stage 6 — AI 子規劃書：Level 3 GOAP（目標導向行動規劃）

## 1. 定位

Level 3 採用 GOAP（Goal-Oriented Action Planning）：AI 依據當前世界狀態與目標，
透過 A\* 搜尋自動規劃行動序列。行為有邏輯感、能自動適應局勢，
且 A\* 天生確定性，無需額外處理重播需求。

難度調節靠動態 Action cost（模糊邏輯加權）與 re-planning 頻率。

---

## 2. 模糊邏輯 API（`ai/fuzzy/`）

模糊邏輯層完全不知道遊戲存在，可獨立測試與複用。

### 2.1 隸屬函數工廠（`fuzzy/membership.py`）

```python
from typing import Callable

def triangular(a: float, b: float, c: float) -> Callable[[float], float]:
    """三角形：在 a 為 0，b 為峰值 1.0，c 為 0。"""
    def fn(x: float) -> float:
        if x <= a or x >= c: return 0.0
        if x <= b: return (x - a) / (b - a)
        return (c - x) / (c - b)
    return fn

def trapezoidal(a: float, b: float, c: float, d: float) -> Callable[[float], float]:
    """梯形：a→b 線性升，b→c 平台為 1.0，c→d 線性降。"""
    def fn(x: float) -> float:
        if x <= a or x >= d: return 0.0
        if x <= b: return (x - a) / (b - a) if b > a else 1.0
        if x <= c: return 1.0
        return (d - x) / (d - c) if d > c else 1.0
    return fn
```

> **為什麼選梯形而非三角形用於 low / high 端**：
> HP 在極低或極高時應「穩定地」完全隸屬該集合，三角形在端點仍會線性下降（不自然）；
> 梯形在端點有平台，AI 在這段範圍內行為一致，不會因 1 HP 差距改變決策。

### 2.2 FuzzyVariable API（`fuzzy/variable.py`）

```python
from dataclasses import dataclass
from typing import Callable

@dataclass
class FuzzySet:
    name: str
    fn:   Callable[[float], float]

    def membership(self, value: float) -> float:
        return max(0.0, min(1.0, self.fn(value)))


class FuzzyVariable:
    """語言變數：持有多個 FuzzySet，提供查詢介面。"""

    def __init__(self, name: str, sets: list[FuzzySet]):
        self.name  = name
        self._sets = sets

    def evaluate(self, value: float) -> dict[str, float]:
        """回傳各集合的正規化隸屬度向量（總和 ≈ 1.0）。"""
        raw   = {s.name: s.membership(value) for s in self._sets}
        total = sum(raw.values()) or 1.0
        return {k: v / total for k, v in raw.items()}

    def dominant(self, value: float) -> str:
        """回傳隸屬度最高的集合名稱（用於離散化觸發）。"""
        m = self.evaluate(value)
        return max(m, key=m.get)

    def weighted(self, value: float, weights: dict[str, float]) -> float:
        """依隸屬度加權計算純量（用於動態 cost）。
        示例：weights={"low":2.0,"mid":1.0,"high":0.3}
        → HP 越低，輸出越接近 2.0
        """
        m = self.evaluate(value)
        return sum(m[k] * weights.get(k, 1.0) for k in m)
```

### 2.3 遊戲專用變數定義（`ai/goap/world_state.py` 頂部）

```python
from ai.fuzzy.membership import triangular, trapezoidal
from ai.fuzzy.variable   import FuzzyVariable, FuzzySet

_MAX_HP = 1000
_MAX_MP = 50_000

HP_VAR = FuzzyVariable("hp", [
    FuzzySet("low",  trapezoidal(0.0, 0.0, 0.20, 0.50)),
    FuzzySet("mid",  triangular (0.20, 0.50, 0.80)),
    FuzzySet("high", trapezoidal(0.50, 0.80, 1.00, 1.00)),
])

MP_VAR = FuzzyVariable("mp", [
    FuzzySet("low",  trapezoidal(0.0, 0.0, 0.20, 0.50)),
    FuzzySet("mid",  triangular (0.20, 0.50, 0.80)),
    FuzzySet("high", trapezoidal(0.50, 0.80, 1.00, 1.00)),
])

DIST_VAR = FuzzyVariable("dist", [
    FuzzySet("close",  trapezoidal(0.0,      0.0,      60_000,  120_000)),
    FuzzySet("mid",    triangular (60_000,   140_000,  220_000)),
    FuzzySet("far",    trapezoidal(160_000,  240_000,  1e9, 1e9)),
])
```

---

## 3. WorldState 結構

WorldState 包含三層資料，由下層函數統一建構：

```
Layer 1 — 規劃器原始值    用於 precondition 比對（A* 搜尋節點）
Layer 2 — 模糊主導集合    用於 should_replan() 觸發偵測
Layer 3 — 模糊隸屬度向量  用於動態 Action cost 計算
```

```python
def build_goap_world_state(ai_p, opp_p) -> dict:
    dist = abs(ai_p.x - opp_p.x)
    hp_ratio  = ai_p.hp / _MAX_HP
    mp_ratio  = ai_p.mp / _MAX_MP

    opp_moving_toward = (
        (opp_p.vx > 0 and opp_p.x < ai_p.x) or
        (opp_p.vx < 0 and opp_p.x > ai_p.x)
    )

    return {
        # ── Layer 1：規劃器原始值 ──────────────────────────────
        "dist":          dist,
        "in_range":      dist <= 100_000,
        "self_hp":       ai_p.hp,
        "self_mp":       ai_p.mp,
        "opp_hp":        opp_p.hp,
        "opp_state":     opp_p.state,
        "opp_vx_toward": opp_moving_toward,
        "self_airborne": ai_p.z > 0,

        # ── Layer 2：主導集合（用於 re-planning 觸發）──────────
        "self_hp_dom":   HP_VAR.dominant(hp_ratio),
        "self_mp_dom":   MP_VAR.dominant(mp_ratio),
        "dist_dom":      DIST_VAR.dominant(dist),

        # ── Layer 3：隸屬度向量（用於動態 cost）────────────────
        "self_hp_fuzzy": HP_VAR.evaluate(hp_ratio),
        "self_mp_fuzzy": MP_VAR.evaluate(mp_ratio),
        "dist_fuzzy":    DIST_VAR.evaluate(dist),
    }
```

---

## 4. 混合式重新規劃策略

### 4.1 設計原則

- **離散狀態改變** → 立即重新規劃（in_range、opp_state）
- **連續值的主導集合切換** → 立即重新規劃（HP 從 mid→low、MP 從 high→mid）
- **最長計畫壽命** → 超過 `MAX_PLAN_AGE` 幀強制更新

```python
_DISCRETE_KEYS   = {"in_range", "opp_state"}
_FUZZY_DOM_KEYS  = {"self_hp_dom", "self_mp_dom", "dist_dom"}
MAX_PLAN_AGE     = 30   # 約 0.5 秒

def should_replan(prev_ws: dict, curr_ws: dict) -> bool:
    discrete_changed = any(
        prev_ws.get(k) != curr_ws.get(k) for k in _DISCRETE_KEYS
    )
    fuzzy_shifted = any(
        prev_ws.get(k) != curr_ws.get(k) for k in _FUZZY_DOM_KEYS
    )
    return discrete_changed or fuzzy_shifted
```

### 4.2 HP 主導集合切換示意

mid/high 交叉點 ≈ HP 650，low/mid 交叉點 ≈ HP 350（由 HP_VAR 梯形/三角形定義推導）。

```
HP=680  → dominant="high"
HP=660  → dominant="high"   (無切換，不重新規劃)
HP=640  → dominant="mid"    ← 切換！重新規劃
HP=370  → dominant="mid"    (無切換)
HP=320  → dominant="low"    ← 切換！重新規劃
```

---

## 5. GOAPAction 資料結構

```python
# src/python/ai/goap/action.py
from dataclasses import dataclass, field
from typing import Callable, Any

@dataclass
class GOAPAction:
    name:            str
    preconditions:   dict[str, Any]         # {"in_range": True, "self_mp": (">=", 15000)}
    effects:         dict[str, Any]         # {"opp_hp": ("delta", -300), "in_range": False}
    base_cost:       float
    input_mask:      int                    # 輸出給 session.advance() 的 u8
    duration_frames: int = 1               # 此行動持續幾幀
    cost_fn: Callable[[dict], float] | None = None  # 覆寫 base_cost 的動態 cost

    def cost(self, world_state: dict) -> float:
        return self.cost_fn(world_state) if self.cost_fn else self.base_cost

    def is_applicable(self, world_state: dict) -> bool:
        for key, val in self.preconditions.items():
            ws_val = world_state.get(key)
            if isinstance(val, tuple):          # (">=", 15000)
                op, threshold = val
                if op == ">="  and not (ws_val >= threshold): return False
                if op == "<="  and not (ws_val <= threshold): return False
                if op == ">"   and not (ws_val >  threshold): return False
                if op == "<"   and not (ws_val <  threshold): return False
            elif ws_val != val:
                return False
        return True

    def apply(self, world_state: dict) -> dict:
        """回傳套用此行動後的新 WorldState（shallow copy + 修改）。"""
        new_ws = dict(world_state)
        for key, val in self.effects.items():
            if isinstance(val, tuple) and val[0] == "delta":
                new_ws[key] = new_ws.get(key, 0) + val[1]
            else:
                new_ws[key] = val
        return new_ws
```

---

## 6. A\* 規劃器

```python
# src/python/ai/goap/planner.py
import heapq

def plan(start_ws: dict, goal: dict, actions: list[GOAPAction],
         max_nodes: int = 200) -> list[GOAPAction]:
    """
    A* 搜尋最低 cost 的行動序列使 world_state 滿足 goal。
    回傳行動序列；若無解則回傳空列表。
    """
    # (accumulated_cost, node_id, world_state, action_list)
    open_set = [(0.0, 0, start_ws, [])]
    visited  = set()
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

    return []   # 無解，呼叫端 fallback 至 lv1 FSM


def _satisfies_goal(ws: dict, goal: dict) -> bool:
    for key, val in goal.items():
        if isinstance(val, tuple):
            op, threshold = val
            ws_val = ws.get(key, 0)
            if op == "<=" and not (ws_val <= threshold): return False
            if op == ">=" and not (ws_val >= threshold): return False
        elif ws.get(key) != val:
            return False
    return True


def _heuristic(ws: dict, goal: dict) -> float:
    """啟發值：對手剩餘 HP 除以單次攻擊傷害估算。"""
    opp_hp = ws.get("opp_hp", 0)
    return max(0.0, opp_hp / 300.0)


def _ws_to_key(ws: dict) -> tuple:
    """將 WorldState 的 Layer 1 離散欄位轉為可雜湊 key（排除 fuzzy 向量）。"""
    keys = ("in_range", "self_hp", "self_mp", "opp_hp", "opp_state")
    return tuple(ws.get(k) for k in keys)
```

---

## 7. 各角色 GOAP Action 表

共用基底 action（每個角色都有），`cost_fn` 依角色特性調整。

### 共用基底 Action

```python
# src/python/ai/goap/base_actions.py
from game_constants import INPUT_RIGHT, INPUT_LEFT, INPUT_ATTACK, INPUT_SKILL, INPUT_JUMP

def make_approach(profile):
    return GOAPAction(
        name="靠近",
        preconditions={"in_range": False},
        effects={"in_range": True},
        base_cost=1.0,
        input_mask=0,  # 執行時依朝向動態決定，見 GOAPAIController._execute()
        duration_frames=12,
        cost_fn=lambda ws: 1.0 - profile.aggression * 0.4,
    )

def make_retreat(profile):
    return GOAPAction(
        name="後退",
        preconditions={"in_range": True},
        effects={"in_range": False},
        base_cost=1.0,
        input_mask=0,  # 同上，動態決定
        duration_frames=12,
        cost_fn=lambda ws: HP_VAR.weighted(
            ws["self_hp"] / _MAX_HP,
            {"low": 0.3, "mid": 0.8, "high": 1.5}
        ),  # HP 越低越傾向後退（cost 越低）
    )

def make_attack():
    return GOAPAction(
        name="普攻",
        preconditions={"in_range": True},
        effects={"opp_hp": ("delta", -200)},
        base_cost=1.0,
        input_mask=INPUT_ATTACK,
        duration_frames=6,
    )
```

### 角色特化 Action 示例（Mage）

```python
# src/python/ai/characters/mage_ai.py

MAGE_SKILL = GOAPAction(
    name="魔法彈",
    preconditions={
        "in_range": False,
        "self_mp":  (">=", MAGE_PROFILE.skill_mp_threshold),
    },
    effects={"opp_hp": ("delta", -500)},
    base_cost=0.5,
    input_mask=INPUT_SKILL,
    duration_frames=1,
    # MP 越滿，技能費用越低；Mage 天生傾向用技能
    cost_fn=lambda ws: MP_VAR.weighted(
        ws["self_mp"] / _MAX_MP,
        {"low": 2.5, "mid": 1.0, "high": 0.3}
    ),
)

MAGE_CLOSE_ATTACK = GOAPAction(
    name="被迫近戰",
    preconditions={"in_range": True},
    effects={"opp_hp": ("delta", -150)},
    base_cost=2.0,     # Mage 不擅近戰，cost 高
    input_mask=INPUT_ATTACK,
    duration_frames=6,
)

MAGE_JUMP_RETREAT = GOAPAction(
    name="跳躍逃脫",
    preconditions={"in_range": True, "self_airborne": False},
    effects={"in_range": False, "self_airborne": True},
    base_cost=0.6,
    input_mask=INPUT_JUMP,
    duration_frames=1,
    # HP 越低越傾向逃
    cost_fn=lambda ws: HP_VAR.weighted(
        ws["self_hp"] / _MAX_HP,
        {"low": 0.2, "mid": 0.6, "high": 1.2}
    ),
)

MAGE_GOAP_ACTIONS = [make_approach(MAGE_PROFILE), make_retreat(MAGE_PROFILE),
                     MAGE_CLOSE_ATTACK, MAGE_SKILL, MAGE_JUMP_RETREAT]
```

---

## 8. 目標（Goal）設計

AI 同時只有一個 active goal，依情境切換：

```python
GOAL_WIN      = {"opp_hp": ("<=", 0)}
GOAL_SURVIVE  = {"in_range": False}   # 拉開距離
GOAL_RECOVER  = {"in_range": False}   # 退開等 MP 回復

def select_goal(ws: dict, profile: CharAIProfile) -> dict:
    if ws["self_hp_dom"] == "low":
        return GOAL_SURVIVE
    if ws["self_mp_dom"] == "low" and profile.aggression < 0.6:
        return GOAL_RECOVER
    return GOAL_WIN
```

---

## 9. GOAPAIController 骨架

```python
# src/python/ai/controllers/goap_ai.py
from ai.goap.planner     import plan
from ai.goap.world_state import build_goap_world_state, should_replan
from ai.controllers.base import AIController

class GOAPAIController(AIController):
    def __init__(self, profile: CharAIProfile, actions: list[GOAPAction],
                 fallback: AIController, max_plan_age: int = 30):
        self.profile  = profile
        self.actions  = actions
        self.fallback = fallback  # lv1 FSM，計畫失敗時使用
        self.max_plan_age = max_plan_age

        self._plan:      list[GOAPAction] = []
        self._plan_step: int = 0
        self._step_timer: int = 0
        self._plan_age:  int = 0
        self._prev_ws:   dict = {}

    def decide(self, ai_p, opp_p, entities) -> int:
        ws = build_goap_world_state(ai_p, opp_p)

        needs_replan = (
            not self._plan
            or self._plan_age >= self.max_plan_age
            or should_replan(self._prev_ws, ws)
        )

        if needs_replan:
            goal = select_goal(ws, self.profile)
            self._plan = plan(ws, goal, self.actions)
            self._plan_step = 0
            self._step_timer = 0
            self._plan_age = 0

        self._prev_ws = ws
        self._plan_age += 1

        if not self._plan:
            return self.fallback.decide(ai_p, opp_p, entities)

        return self._execute(ai_p, opp_p)

    def _execute(self, ai_p, opp_p) -> int:
        action = self._plan[self._plan_step]
        self._step_timer += 1

        # 靠近/後退的 input_mask 依即時朝向決定
        if action.name in ("靠近", "被迫近戰 → 靠近"):
            mask = INPUT_RIGHT if opp_p.x > ai_p.x else INPUT_LEFT
        elif action.name == "後退":
            mask = INPUT_LEFT if opp_p.x > ai_p.x else INPUT_RIGHT
        else:
            mask = action.input_mask

        if self._step_timer >= action.duration_frames:
            self._step_timer = 0
            self._plan_step += 1
            if self._plan_step >= len(self._plan):
                self._plan = []  # 計畫執行完畢，下幀重新規劃

        return mask
```

---

## 10. Debug Overlay 擴充

在 `debug_manager.py` 新增 AI 資訊面板，以 F4 切換顯示：

```
┌─ AI Debug ──────────────────────────────────────────┐
│ P2  Mage  lv3-GOAP                                  │
│ Goal:    WIN                                        │
│ Plan:    [靠近 → 魔法彈]  step 0/2  age 12           │
│ Replan:  47 times                                   │
├─────────────────────────────────────────────────────┤
│ HP  ████████░░  672  [low:0.0  mid:0.3  high:0.7]   │
│ MP  █████░░░░░  22k  [low:0.0  mid:0.6  high:0.4]   │
│ Dist  ──  135k  [close:0.0  mid:0.8  far:0.2]       │
├─────────────────────────────────────────────────────┤
│ in_range: False  opp_state: IDLE  dist_dom: mid     │
└─────────────────────────────────────────────────────┘
```

顯示資料來源：
- `_plan`、`_plan_step`、`_plan_age`（直接讀 controller 屬性）
- `ws["self_hp_fuzzy"]`、`ws["self_mp_fuzzy"]` 等（由 `build_goap_world_state` 提供）

---

## 11. 檔案清單

```
src/python/ai/
├── fuzzy/
│   ├── membership.py          # triangular, trapezoidal 工廠函數
│   └── variable.py            # FuzzySet, FuzzyVariable
├── goap/
│   ├── action.py              # GOAPAction dataclass
│   ├── planner.py             # A* plan()
│   ├── world_state.py         # build_goap_world_state(), should_replan()
│   └── base_actions.py        # 角色共用基底 Action 工廠
├── controllers/
│   └── goap_ai.py             # GOAPAIController
└── characters/
    ├── mage_ai.py             # MAGE_PROFILE + MAGE_GOAP_ACTIONS
    ├── knight_ai.py
    ├── archer_ai.py
    ├── paladin_ai.py
    └── wizard_ai.py
```

---

## 12. 各層依賴關係

```
fuzzy/           ← 純數學，無任何遊戲知識，可獨立 import 與測試
  ↓
goap/action.py   ← 純資料結構，知道 cost/precondition 概念，不知道遊戲
  ↓
goap/planner.py  ← 純演算法（A*），只知道 action.is_applicable / apply
  ↓
goap/world_state.py ← 唯一接觸 Rust Player 物件的地方，輸出 dict
  ↓
goap_ai.py       ← 薄膠合層：WorldState → should_replan → planner → execute
  ↑
characters/*.py  ← 角色知識（Action 表、Profile），注入進 GOAPAIController
```
