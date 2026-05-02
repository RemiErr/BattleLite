# BattleLite Stage 6 — AI 子規劃書：Level 1 有限狀態機（FSM）

## 1. 定位

Level 1 是最輕量的 AI 等級，角色無關、無外部依賴，作為整個 AI 系統的基礎層。
難度調節完全靠參數（延遲幀數、隨機率），不改邏輯。

---

## 2. 狀態機設計

### 2.1 狀態清單

| 狀態常數   | 意義                 |
| ---------- | -------------------- |
| `APPROACH` | 朝目標靠近           |
| `ATTACK`   | 在攻擊距離內執行普攻 |
| `RETREAT`  | 受傷或 HP 偏低後退   |
| `SKILL`    | MP 足夠時施放技能    |
| `WAIT`     | 冷卻等待，原地不動   |

### 2.2 轉移條件表

| 當前狀態 | 觸發條件                                    | 下一狀態 |
| -------- | ------------------------------------------- | -------- |
| APPROACH | dist <= ATTACK_RANGE                        | ATTACK   |
| APPROACH | self_hp < LOW_HP and dist < FLEE_DIST       | RETREAT  |
| APPROACH | self_mp >= SKILL_MP and dist <= SKILL_RANGE | SKILL    |
| ATTACK   | dist > ATTACK_RANGE                         | APPROACH |
| ATTACK   | attack_count >= COMBO_MAX                   | WAIT     |
| ATTACK   | self_mp >= SKILL_MP                         | SKILL    |
| RETREAT  | retreat_timer <= 0                          | APPROACH |
| SKILL    | skill_timer <= 0                            | WAIT     |
| WAIT     | wait_timer <= 0                             | APPROACH |

### 2.3 狀態機圖

```
                 ┌──────────────────┐
   dist <= range │                  │ dist > range
        ┌────────▼───┐       ┌──────┴──────┐
        │   ATTACK   │       │  APPROACH   │◄────┐
        └────────────┘       └─────────────┘     │
            │ combo = max            ▲           │ timer = 0
            │ mp >= skill            │ hp < LOW  │ (WAIT → APPROACH)
            ▼                        │           │
        ┌────────────┐       ┌─────────────┐     │
        │    WAIT    │       │   RETREAT   │     │
        └────────────┘       └─────────────┘     │
            │ timer = 0 ─────────────────────────┘
            │ mp >= skill
            ▼
        ┌────────────┐
        │   SKILL    │
        └────────────┘
            │ timer = 0
            ▼
        ┌────────────┐
        │    WAIT    │
        └────────────┘
```

---

## 3. WorldState（FSM 讀取的輸入）

FSM 只讀取粗粒度的遊戲狀態。

```python
def build_fsm_world_state(ai_p, opp_p) -> dict:
    dist = abs(ai_p.x - opp_p.x)
    return {
        "dist":           dist,
        "facing_toward":  (ai_p.facing_right and opp_p.x > ai_p.x) or
                          (not ai_p.facing_right and opp_p.x < ai_p.x),
        "self_hp":        ai_p.hp,
        "self_mp":        ai_p.mp,
        "self_airborne":  ai_p.z > 0,
        "opp_state":      opp_p.state,
        "opp_airborne":   opp_p.z > 0,
    }
```

---

## 4. 難度參數

所有數字從外部注入，`FSMAI` 本身不 hardcode 任何閾值。

```python
@dataclass
class FSMDifficultyParams:
    reaction_delay:   int   = 6      # 狀態切換前等待幾幀（模擬反應時間）
    attack_range:     int   = 80_000 # 決定切入 ATTACK 的距離（Rust 單位）
    skill_range:      int   = 160_000
    flee_dist:        int   = 120_000
    low_hp_threshold: int   = 300    # HP 低於此值進 RETREAT
    skill_mp:         int   = 20_000
    combo_max:        int   = 3      # 連續攻擊幾下後強制進 WAIT
    retreat_frames:   int   = 30
    wait_frames:      int   = 15
    jump_prob:        float = 0.02   # 每幀隨機跳躍機率
```

Level 1 建議值：`reaction_delay=8, jump_prob=0.03`（稍慢、稍隨機）

---

## 5. 輸入遮罩生成

```python
def _state_to_input(self, state: str, ai_p, opp_p) -> int:
    move_toward = INPUT_RIGHT if opp_p.x > ai_p.x else INPUT_LEFT
    move_away   = INPUT_LEFT  if opp_p.x > ai_p.x else INPUT_RIGHT

    if state == "APPROACH":
        mask = move_toward
        if random.random() < self.params.jump_prob and ai_p.z == 0:
            mask |= INPUT_JUMP
        return mask
    if state == "ATTACK":
        return INPUT_ATTACK
    if state == "RETREAT":
        return move_away
    if state == "SKILL":
        return INPUT_SKILL
    return 0  # WAIT
```

> `random` 只用於跳躍機率。若需確定性重播，以 `seeded_rng.random()` 替換，
> 種子從 `game_start` 的 `seed` 欄位注入。

---

## 6. 實作骨架

```python
# src/python/ai/controllers/fsm_ai.py
from ai.controllers.base import AIController

class FSMAIController(AIController):
    def __init__(self, char_type: int, params: FSMDifficultyParams,
                 rng: random.Random):
        self.params = params
        self.rng = rng
        self._state = "APPROACH"
        self._timer = 0          # 通用倒數計時器
        self._attack_count = 0
        self._reaction_delay = 0

    def decide(self, ai_p, opp_p, entities) -> int:
        ws = build_fsm_world_state(ai_p, opp_p)
        self._transition(ws)
        return self._state_to_input(self._state, ai_p, opp_p)

    def _transition(self, ws: dict):
        # reaction_delay：狀態切換前需等待 N 幀確認
        if self._reaction_delay > 0:
            self._reaction_delay -= 1
            return
        new_state = self._evaluate_transition(ws)
        if new_state != self._state:
            self._enter_state(new_state)
            self._reaction_delay = self.params.reaction_delay

    def _evaluate_transition(self, ws: dict) -> str:
        # 依表 2.2 順序判斷
        ...

    def _enter_state(self, state: str):
        self._state = state
        if state == "RETREAT": self._timer = self.params.retreat_frames
        if state == "WAIT":    self._timer = self.params.wait_frames
        if state == "ATTACK":  self._attack_count = 0
```

---

## 7. 角色無關性說明

FSM 不讀取角色種類。所有技能都對應 `INPUT_SKILL` bitmask，攻擊對應 `INPUT_ATTACK`。
角色特有行為（Mage 保持距離）透過 `FSMDifficultyParams` 的距離閾值間接反映：
- Mage：`attack_range=200_000`（大），`flee_dist=150_000`（大）
- Knight：`attack_range=70_000`（小），`flee_dist=80_000`（小）

---

## 8. 檔案清單

```
src/python/ai/
├── controllers/
│   ├── base.py      # AIController ABC：decide(ai_p, opp_p, entities) -> int
│   └── fsm_ai.py    # FSMAIController + FSMDifficultyParams
└── world_state.py   # build_fsm_world_state()（lv1 用）
```
