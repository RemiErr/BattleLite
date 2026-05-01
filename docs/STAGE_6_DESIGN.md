# BattleLite 第六階段規劃書：AI 對手 & 遊戲打磨

## 1. 核心願景

Stage 5 完成了完整的遊戲循環（死亡、結算、多人配對、排行榜）。
Stage 6 有兩條主線：

**主線 A — AI 對手**：讓玩家在離線或自訂房間時有對手可練習，
並以三個等級由淺至深逐步實作，每個等級完成後即可獨立遊玩。

**主線 B — 遊戲打磨**：視覺手感強化（擊中回饋、特效），
讓每一次攻擊都有重量感。

---

## 2. 設計決策

| 項目        | 決定                   | 理由                                     |
| ----------- | ---------------------- | ---------------------------------------- |
| AI 使用場景 | 離線模式 + 自訂房間    | 排位導入 AI 的公平性與跨裝置確定性成本高 |
| 加入方式    | 房主在房間頁面手動新增 | 指定數量、等級、角色，佔用玩家槽         |
| 確定性需求  | 同台機器重播即可       | 不需跨裝置，降低複雜度                   |
| 輸出格式    | `u8` bitmask           | 與人類輸入方式相同，不用改 Rust          |
| AI 等級數量 | 3                      | lv1 FSM、lv2 Pattern、lv3 GOAP           |

---

## 3. AI 等級一覽

| 等級 | 算法                | 技術核心                | 角色特化               | 確定性             |
| ---- | ------------------- | ----------------------- | ---------------------- | ------------------ |
| lv1  | 有限狀態機（FSM）   | 狀態轉移表 + 參數調控   | 無（靠參數值間接反映） | 可選（seeded rng） |
| lv2  | Script / Pattern AI | 條件匹配 + 招式序列播放 | 每角色一份 Pattern 表  | 天生確定           |
| lv3  | GOAP + 模糊邏輯     | A\* 規劃 + 動態 cost    | 每角色一份 Action 表   | 天生確定           |

各等級詳細技術規格見獨立子規劃書：

- **lv1**：[`STAGE_6_AI_LV1_FSM.md`](STAGE_6_AI_LV1_FSM.md)
- **lv2**：[`STAGE_6_AI_LV2_PATTERN.md`](STAGE_6_AI_LV2_PATTERN.md)
- **lv3**：[`STAGE_6_AI_LV3_GOAP.md`](STAGE_6_AI_LV3_GOAP.md)

---

## 4. AI 模組整體架構

```
src/python/ai/
├── fuzzy/                      # 模糊邏輯 API（lv3 專用，無遊戲知識）
│   ├── membership.py           # triangular, trapezoidal 隸屬函數工廠
│   └── variable.py             # FuzzySet, FuzzyVariable
│
├── goap/                       # GOAP 演算法（lv3 專用，無遊戲知識）
│   ├── action.py               # GOAPAction dataclass
│   ├── planner.py              # A* plan() 函數
│   ├── world_state.py          # build_goap_world_state(), should_replan()
│   └── base_actions.py         # 角色共用 Action 工廠
│
├── controllers/
│   ├── base.py                 # AIController ABC
│   ├── fsm_ai.py               # lv1 FSMAIController
│   ├── pattern_ai.py           # lv2 PatternAIController
│   └── goap_ai.py              # lv3 GOAPAIController
│
├── characters/
│   ├── profile.py              # CharAIProfile（lv2 + lv3 共用）
│   ├── knight_ai.py            # KNIGHT_PROFILE + patterns + goap_actions
│   ├── mage_ai.py
│   ├── archer_ai.py
│   ├── paladin_ai.py
│   └── wizard_ai.py
│
└── predicates.py               # 共用條件謂詞（lv2 condition + lv3 precondition 實作）
```

### 跨等級共用關係

```
CharAIProfile ──────────┬──→ lv2 Pattern condition 閾值
                        └──→ lv3 GOAP Action cost 調整

predicates.py ──────────┬──→ lv2 Pattern.condition 函數體
                        └──→ lv3 world_state.py（計算 WorldState 的離散 key 值）

fuzzy/ ─────────────────┬──→ lv3 WorldState 建構（dominant、evaluate）
                        ├──→ lv3 GOAPAction cost_fn（weighted 加權）
                        └──→ lv3 Debug Overlay 隸屬度顯示

lv1 FSMAIController ────┬──→ lv2 PatternAIController.fallback
                        └──→ lv3 GOAPAIController.fallback（計畫失敗時）
```

---

## 5. 任務 33：AI 基礎建設

**前置條件**：無

### 5.1 AIController 抽象基底

```python
# src/python/ai/controllers/base.py
from abc import ABC, abstractmethod

class AIController(ABC):
    @abstractmethod
    def decide(self, ai_p, opp_p, entities: list) -> int:
        """每幀呼叫，回傳 u8 input bitmask。"""
        ...
```

### 5.2 AI 工廠函數

```python
# src/python/ai/factory.py
def make_ai(char_type: int, level: int, seed: int) -> AIController:
    """
    char_type: 0=Knight 1=Mage 2=Archer 3=Paladin 4=Wizard
    level:     1=FSM  2=Pattern  3=GOAP
    seed:      用於 lv1 隨機跳躍的 seeded RNG
    """
    profile_map = {0: KNIGHT_PROFILE, 1: MAGE_PROFILE, ...}
    profile = profile_map[char_type]
    rng = random.Random(seed)

    fsm = FSMAIController(char_type, _FSM_PARAMS[char_type], rng)
    if level == 1: return fsm

    patterns = _PATTERNS[char_type]
    pattern_ctrl = PatternAIController(profile, patterns, fallback=fsm)
    if level == 2: return pattern_ctrl

    actions = _GOAP_ACTIONS[char_type]
    return GOAPAIController(profile, actions, fallback=fsm)
```

### 5.3 main.py 整合點

`main.py` 每幀依玩家身分決定輸入來源：

```python
# 初始化
ai_controllers: dict[int, AIController] = {}
for p_id, ai_info in payload.get("ai_players", {}).items():
    ai_controllers[int(p_id)] = make_ai(
        ai_info["char_type"], ai_info["level"], payload["seed"])

# 每幀
inputs = []
for pid in range(num_players):
    if pid == local_id:
        inputs.append(read_keyboard())
    elif pid in ai_controllers:
        ai_p   = session.get_player(pid)
        opp_p  = session.get_player(local_id)          # 暫定對手為本地玩家
        entities = [session.get_entity(i) for i in range(session.get_entity_count())]
        inputs.append(ai_controllers[pid].decide(ai_p, opp_p, entities))
    else:
        inputs.append(0)
session.advance(inputs)
```

> **多對手情況**：lv2 / lv3 的 `decide()` 目前只接收單一對手。
> 4 人場時，傳入 HP 最低的存活對手（最易擊倒的目標），此策略可在 factory 層切換。

---

## 6. 任務 34：房間 UI 加入 AI

### 6.1 UI 位置

```
Room Frame
├── [Header] [返回] 房間 XXXXX  [複製]
├── [Players Table]             ← 玩家列表
├── [AI Panel]                  ← AI 列表（空位數 > 0 才顯示，槽位上限 = 空位數）
│   ├── 加入 AI：[−] [lv1 ⌥♞] [lv2 ⌥♜] [lv3 ⌥♚]  角色：[下拉]  [+ 加入]
│   └── 已加入的 AI 列表（可個別移除）
├── [Size Selector] 2人 / 3人 / 4人       ← 人數控制
└── [準備好了] [開始遊戲]
```

### 6.2 AI 玩家顯示規則

| 場景            | 顯示名稱             | tier_badge                       |
| --------------- | -------------------- | -------------------------------- |
| 排位房（queue） | `P{id} {nickname} `  | `☆☆★ / ☆★★ / ★★★` (實際段位符號) |
| 自訂房（AI）    | `P{id} {char_name} ` | `♞⌥𝟭 / ♜⌥𝟮 / ♚⌥𝟯`（lv1/2/3）     |

### 6.3 payload 擴充

`game_start` 的 session_data 新增 `ai_players` 欄位：

```json
{
  "ai_players": {
    "2": {"char_type": 1, "level": 2},
    "3": {"char_type": 0, "level": 1}
  }
}
```

`main.py` 讀取此欄位初始化 AI Controller，**不做任何 Rust 端修改**。

### 6.4 離線模式

`--payload ""` 啟動時，提供選角 + AI 配置 UI（簡易 popup 或 CLI 參數），
確認後直接進入 `OfflineSession`。

---

## 7. 任務 35：AI Level 1（FSM）

技術規格見 [`STAGE_6_AI_LV1_FSM.md`](STAGE_6_AI_LV1_FSM.md)。

**實作重點摘要：**
- 5 個狀態：APPROACH / ATTACK / RETREAT / SKILL / WAIT
- 難度靠 `FSMDifficultyParams` 注入（`reaction_delay`、`jump_prob` 等）
- 角色無關，靠距離參數間接反映角色定位
- 確定性：`seeded_rng` 替換 `random.random()`，種子來自 `payload["seed"]`

**完成條件**：離線 1v1，AI 能持續靠近、攻擊、受傷後退；玩家可明顯感受到 AI 的反應延遲。

---

## 8. 任務 36：AI Level 2（Pattern AI）

技術規格見 [`STAGE_6_AI_LV2_PATTERN.md`](STAGE_6_AI_LV2_PATTERN.md)。

**實作重點摘要：**
- `Pattern` dataclass：condition（謂詞）+ action_sequence（bitmask 序列）+ priority + cooldown
- 執行引擎：priority 選最高符合者，逐幀播放序列；不符合時 fallback 至 lv1
- 5 個角色各有 3–4 個 Pattern，涵蓋進攻、逃跑、補刀情境
- `CharAIProfile`（preferred_range、aggression 等）lv2 / lv3 共用

**完成條件**：每個角色的 AI 行為明顯有角色感（Mage 保持距離、Knight 積極追擊）。

---

## 9. 任務 37：AI Level 3（GOAP）

技術規格見 [`STAGE_6_AI_LV3_GOAP.md`](STAGE_6_AI_LV3_GOAP.md)。

**實作重點摘要：**

| 元件              | 描述                                                                            |
| ----------------- | ------------------------------------------------------------------------------- |
| `fuzzy/`          | 隸屬函數（梯形為主）+ `FuzzyVariable` API，零遊戲知識                           |
| `WorldState`      | Layer 1 原始值（規劃用）+ Layer 2 主導集合（觸發用）+ Layer 3 隸屬度（cost 用） |
| `should_replan()` | 離散鍵直接比對；連續值比主導集合；超齡（30 幀）強制更新                         |
| `GOAPAction`      | preconditions + effects + `cost_fn(ws)`（動態模糊 cost）                        |
| `planner.py`      | A\* 搜尋，`max_nodes=200` 防止過深搜尋                                          |
| 目標切換          | HP_dom="low" → SURVIVE；MP_dom="low" + 低攻擊性 → RECOVER；其餘 → WIN           |
| fallback          | 計畫為空時呼叫 lv1 FSM                                                          |

**完成條件**：lv3 AI 能依局勢自動切換目標（追擊 / 後退 / 等 MP），
行為比 lv2 更難預測但仍有角色個性。

---

## 10. 任務 38：遊戲打磨

優先聚焦手感，與 AI 任務可並行推進。

### 10.1 受擊閃白

命中時角色 sprite 整體閃白 1–2 幀，強化打擊感。

```python
# renderer.py
if player.hitstop > 0 and player.state == STATE_HURT:
    # 用 pygame.Surface.fill 疊加白色半透明遮罩
    flash = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
    flash.fill((255, 255, 255, 160))
    sprite.blit(flash, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
```

### 10.2 落地粉塵特效

`z == 0` 且前幀 `z > 0`（著地瞬間）在角色腳底播放 dust FX。
使用現有 `FxManager.attach_player_fx`，FX 播完自動停止。

### 10.3 候補（視進度推進）

| 項目         | 技術描述                                                                     |
| ------------ | ---------------------------------------------------------------------------- |
| 蓄力機制     | 長按 ATTACK/SKILL 進入 STATE_CHARGE，鬆開才發射；需 Rust 新增 `charge_timer` |
| 距離傷害衰減 | Entity 記錄 `spawn_x`，命中時依 `travel_distance` 線性遞減（Archer 優先）    |
| 情境感知觸發 | 同按鍵依地面/空中/MP 選不同 ability，不改 GGRS Input 型別                    |

---

## 11. Debug Overlay 擴充（任務 38 附屬）

現有 `debug_manager.py` 新增 AI 面板（F4 切換）：

```
┌─ AI Debug ───────────────────────────────────────────┐
│ P2  Mage  lv3-GOAP                                   │
│ Goal:  WIN   Plan: [靠近→魔法彈]  step 0/2  age 12    │
│ Replan count: 47                                     │
├──────────────────────────────────────────────────────┤
│ HP ████████░  672  [low:0.0 mid:0.3 high:0.7]        │
│ MP █████░░░░  22k  [low:0.0 mid:0.6 high:0.4]        │
│ Dist ── 135k  [close:0.0 mid:0.8 far:0.2]            │
└──────────────────────────────────────────────────────┘
```

lv1 / lv2 顯示各自的當前狀態 / 當前 Pattern 名稱，無需 fuzzy 資訊列。

---

## 12. 開發順序

| 優先序 | 任務                                                 | 前置條件                                                  |
| ------ | ---------------------------------------------------- | --------------------------------------------------------- |
| 1      | 任務 33：AI 基礎建設（ABC + factory + main.py 整合） | 無                                                        |
| 2      | 任務 34：房間 UI 加入 AI                             | 任務 33                                                   |
| 3      | 任務 35：lv1 FSM                                     | 任務 33                                                   |
| 4      | 任務 38：受擊閃白 + 落地特效                         | 無（可與任務 35 並行）                                    |
| 5      | 任務 36：lv2 Pattern AI                              | 任務 35（需要 fallback）                                  |
| 6      | 任務 37：lv3 GOAP                                    | 任務 35（需要 fallback）、任務 36（CharAIProfile 已存在） |

---

*子規劃書：[lv1 FSM](STAGE_6_AI_LV1_FSM.md) ／ [lv2 Pattern](STAGE_6_AI_LV2_PATTERN.md) ／ [lv3 GOAP](STAGE_6_AI_LV3_GOAP.md)*
