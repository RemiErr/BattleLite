# BattleLite Stage 6 — AI 子規劃書：Level 2 Script / Pattern AI

## 1. 定位

Level 2 以「情境 → 招式序列」表驅動 AI。每個角色維護一份 Pattern 表，
執行引擎依優先序選出第一個滿足條件的 Pattern，然後逐步播放其 action_sequence。

行為比 lv1 更有角色個性；難度調節靠觸發條件的精確度與連段完成率。

---

## 2. 核心資料結構

### 2.1 CharAIProfile（跨等級共用）

```python
# src/python/ai/characters/profile.py
from dataclasses import dataclass, field

@dataclass
class CharAIProfile:
    """角色 AI 知識的單一來源，lv2 與 lv3 共同引用。"""
    preferred_range:    int    # 偏好戰鬥距離（Rust 單位）
    skill_mp_threshold: int    # 放技能所需 MP
    aggression:         float  # 0.0 保守 ～ 1.0 積極，影響觸發條件閾值
```

### 2.2 共用謂詞庫（lv2 與 lv3 共用）

```python
# src/python/ai/predicates.py
from game_constants import STATE_HURT, STATE_DEAD

def is_in_preferred_range(ws: dict, profile: CharAIProfile) -> bool:
    return ws["dist"] <= profile.preferred_range

def can_use_skill(ws: dict, profile: CharAIProfile) -> bool:
    return ws["self_mp"] >= profile.skill_mp_threshold

def opponent_is_vulnerable(ws: dict) -> bool:
    return ws["opp_state"] == STATE_HURT

def self_hp_low(ws: dict, threshold: int = 300) -> bool:
    return ws["self_hp"] < threshold

def opponent_approaching(ws: dict) -> bool:
    """對手正在靠近（用於反應性後退）。"""
    return ws["opp_vx_toward"]   # 在 build_world_state 計算
```

### 2.3 Pattern

```python
# src/python/ai/controllers/pattern_ai.py  (Pattern 定義置於同一模組頂部)
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class Pattern:
    name:            str
    condition:       Callable[[dict], bool]   # 接收 WorldState
    action_sequence: list[int]                # u8 input mask 序列
    step_duration:   list[int]                # 每個步驟持續幾幀，長度需 == action_sequence
    priority:        int                      # 數字越大越優先
    cooldown_frames: int = 0                  # 執行後需等待幾幀才能再次觸發

    def __post_init__(self):
        assert len(self.action_sequence) == len(self.step_duration), \
            f"Pattern '{self.name}': action_sequence 與 step_duration 長度不符"
```

---

## 3. 執行引擎

```python
# src/python/ai/controllers/pattern_ai.py
from ai.controllers.base import AIController

class PatternAIController(AIController):
    def __init__(self, profile: CharAIProfile, patterns: list[Pattern],
                 fallback: AIController):  # fallback 使用 lv1 FSM
        self.profile  = profile
        self.patterns = sorted(patterns, key=lambda p: -p.priority)
        self.fallback = fallback

        self._active: Pattern | None = None
        self._step:   int = 0          # 當前執行到第幾個 action
        self._step_timer: int = 0      # 當前步驟剩餘幀數
        self._cooldowns: dict[str, int] = {}  # pattern name → 剩餘 cooldown

    def decide(self, ai_p, opp_p, entities) -> int:
        ws = build_pattern_world_state(ai_p, opp_p)
        self._tick_cooldowns()

        # 仍在執行中的 Pattern → 繼續下一步
        if self._active and self._step < len(self._active.action_sequence):
            return self._advance_step()

        # 選出最高優先且條件成立的 Pattern
        for p in self.patterns:
            if self._cooldowns.get(p.name, 0) > 0:
                continue
            if p.condition(ws):
                self._activate(p)
                return self._advance_step()

        # 沒有 Pattern 符合 → 使用 lv1 fallback
        return self.fallback.decide(ai_p, opp_p, entities)

    def _activate(self, pattern: Pattern):
        self._active = pattern
        self._step = 0
        self._step_timer = pattern.step_duration[0]

    def _advance_step(self) -> int:
        mask = self._active.action_sequence[self._step]
        self._step_timer -= 1
        if self._step_timer <= 0:
            self._step += 1
            if self._step >= len(self._active.action_sequence):
                # 整個序列完成
                self._cooldowns[self._active.name] = self._active.cooldown_frames
                self._active = None
            else:
                self._step_timer = self._active.step_duration[self._step]
        return mask

    def _tick_cooldowns(self):
        self._cooldowns = {k: max(0, v - 1) for k, v in self._cooldowns.items()}
```

---

## 4. WorldState（lv2 用）

在 lv1 基礎上增加速度方向資訊（供 `opponent_approaching` 謂詞使用）。

```python
def build_pattern_world_state(ai_p, opp_p) -> dict:
    dist = abs(ai_p.x - opp_p.x)
    opp_moving_toward = (
        (opp_p.vx > 0 and opp_p.x < ai_p.x) or
        (opp_p.vx < 0 and opp_p.x > ai_p.x)
    )
    return {
        "dist":            dist,
        "self_hp":         ai_p.hp,
        "self_mp":         ai_p.mp,
        "self_airborne":   ai_p.z > 0,
        "opp_state":       opp_p.state,
        "opp_vx_toward":   opp_moving_toward,
        "opp_airborne":    opp_p.z > 0,
    }
```

---

## 5. 各角色 Pattern 表

> 下列 action_sequence 使用 bitmask 常數縮寫：
> R=INPUT_RIGHT, L=INPUT_LEFT, ATK=INPUT_ATTACK, SKL=INPUT_SKILL,
> J=INPUT_JUMP, 0=空輸入

### Knight
```python
KNIGHT_PROFILE = CharAIProfile(preferred_range=70_000, skill_mp_threshold=15_000, aggression=0.8)

KNIGHT_PATTERNS = [
    Pattern(
        name="衝刺攻擊",
        condition=lambda ws: ws["dist"] > 80_000 and ws["opp_state"] != STATE_HURT,
        action_sequence=[R, R|ATK, ATK, ATK],
        step_duration=[8, 1, 6, 6],
        priority=8, cooldown_frames=20,
    ),
    Pattern(
        name="對手受傷追擊",
        condition=lambda ws: opponent_is_vulnerable(ws) and ws["dist"] <= 100_000,
        action_sequence=[ATK, ATK, ATK],
        step_duration=[6, 6, 6],
        priority=10, cooldown_frames=10,
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
        action_sequence=[J|ATK, ATK],
        step_duration=[1, 6],
        priority=6, cooldown_frames=30,
    ),
]
```

### Mage
```python
MAGE_PROFILE = CharAIProfile(preferred_range=200_000, skill_mp_threshold=20_000, aggression=0.4)

MAGE_PATTERNS = [
    Pattern(
        name="遠距魔法彈",
        condition=lambda ws: can_use_skill(ws, MAGE_PROFILE) and ws["dist"] >= 120_000,
        action_sequence=[SKL],
        step_duration=[1],
        priority=9, cooldown_frames=30,
    ),
    Pattern(
        name="近戰逃脫",
        condition=lambda ws: ws["dist"] < 100_000,
        action_sequence=[J, L, L, SKL],  # 跳起後後退再放技能
        step_duration=[1, 8, 8, 1],
        priority=10, cooldown_frames=20,
    ),
    Pattern(
        name="對手受傷補刀",
        condition=lambda ws: opponent_is_vulnerable(ws) and ws["dist"] < 200_000,
        action_sequence=[SKL],
        step_duration=[1],
        priority=8, cooldown_frames=15,
    ),
    Pattern(
        name="拉距後放",
        condition=lambda ws: ws["opp_vx_toward"] and ws["dist"] < 160_000,
        action_sequence=[L, L, L, SKL],
        step_duration=[10, 8, 8, 1],
        priority=7, cooldown_frames=25,
    ),
]
```

### Archer
```python
ARCHER_PROFILE = CharAIProfile(preferred_range=160_000, skill_mp_threshold=18_000, aggression=0.6)

ARCHER_PATTERNS = [
    Pattern(
        name="蓄力箭",
        condition=lambda ws: can_use_skill(ws, ARCHER_PROFILE) and ws["dist"] >= 100_000,
        action_sequence=[SKL, 0, 0, 0],   # 長按技能蓄力
        step_duration=[1, 15, 10, 1],
        priority=9, cooldown_frames=35,
    ),
    Pattern(
        name="連射",
        condition=lambda ws: ws["dist"] >= 80_000 and ws["dist"] <= 200_000,
        action_sequence=[ATK, 0, ATK, 0, ATK],
        step_duration=[1, 4, 1, 4, 1],
        priority=7, cooldown_frames=20,
    ),
    Pattern(
        name="跳躍閃避",
        condition=lambda ws: ws["opp_vx_toward"] and ws["dist"] < 100_000,
        action_sequence=[J, J|L],
        step_duration=[1, 12],
        priority=10, cooldown_frames=40,
    ),
]
```

### Paladin
```python
PALADIN_PROFILE = CharAIProfile(preferred_range=80_000, skill_mp_threshold=12_000, aggression=0.5)

PALADIN_PATTERNS = [
    Pattern(
        name="防護盾反",
        condition=lambda ws: self_hp_low(ws, 400) and ws["dist"] <= 100_000,
        action_sequence=[SKL, 0, 0, ATK, ATK],  # 先開盾，等對手攻擊，反擊
        step_duration=[1, 20, 10, 6, 6],
        priority=10, cooldown_frames=60,
    ),
    Pattern(
        name="穩定輸出",
        condition=lambda ws: ws["dist"] <= 80_000,
        action_sequence=[ATK, 0, ATK, 0, ATK],
        step_duration=[6, 4, 6, 4, 6],
        priority=6, cooldown_frames=15,
    ),
    Pattern(
        name="技能強攻",
        condition=lambda ws: can_use_skill(ws, PALADIN_PROFILE) and ws["dist"] <= 90_000,
        action_sequence=[SKL, ATK, ATK],
        step_duration=[1, 6, 6],
        priority=8, cooldown_frames=40,
    ),
]
```

### Wizard
```python
WIZARD_PROFILE = CharAIProfile(preferred_range=90_000, skill_mp_threshold=15_000, aggression=0.6)

WIZARD_PATTERNS = [
    Pattern(
        name="近戰反向彈",
        condition=lambda ws: ws["dist"] <= 80_000,
        action_sequence=[ATK, L, ATK],   # 近戰 → 後退 → 投射物
        step_duration=[6, 8, 1],
        priority=9, cooldown_frames=20,
    ),
    Pattern(
        name="AOE 技能",
        condition=lambda ws: can_use_skill(ws, WIZARD_PROFILE) and ws["dist"] <= 120_000,
        action_sequence=[SKL],
        step_duration=[1],
        priority=8, cooldown_frames=40,
    ),
    Pattern(
        name="對手受傷 AOE",
        condition=lambda ws: opponent_is_vulnerable(ws) and ws["dist"] <= 120_000,
        action_sequence=[SKL],
        step_duration=[1],
        priority=10, cooldown_frames=20,
    ),
]
```

---

## 6. 與 lv3 的共用關係

| 元件 | lv2 用途 | lv3 用途 |
|------|---------|---------|
| `CharAIProfile` | preferred_range 影響 Pattern 條件 | preferred_range 影響 Action cost |
| `predicates.py` | Pattern 的 `condition` 函數 | lv3 `world_state.py` 離散 key 計算的輔助函數 |
| `build_pattern_world_state` | 直接使用 | lv3 的 WorldState 是超集，包含此函數所有欄位 |

lv3 的 `WorldState` 是 lv2 的超集（多出 fuzzy 欄位），兩者共用相同的離散欄位定義。

---

## 7. 檔案清單

```
src/python/ai/
├── predicates.py                   # 共用謂詞（lv2 + lv3 共用）
├── controllers/
│   └── pattern_ai.py               # PatternAIController 執行引擎
└── characters/
    ├── profile.py                  # CharAIProfile dataclass
    ├── knight_ai.py                # KNIGHT_PROFILE + KNIGHT_PATTERNS
    ├── mage_ai.py                  # MAGE_PROFILE + MAGE_PATTERNS
    ├── archer_ai.py                # ARCHER_PROFILE + ARCHER_PATTERNS
    ├── paladin_ai.py               # PALADIN_PROFILE + PALADIN_PATTERNS
    └── wizard_ai.py                # WIZARD_PROFILE + WIZARD_PATTERNS
```
