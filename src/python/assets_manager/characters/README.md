# 角色資源設定說明手冊

`characters/` 目錄存放每個角色的 Python 類別，負責 Sprite 動畫、判定框與戰鬥參數定義。
底層由 `base_character.py` 提供共用基礎設施，子類別只需填入各自的數值。

---

## 目錄結構

```
assets_manager/
├── base_character.py        # BaseCharacter、HitboxDef、CharStats、FxDef 定義
└── characters/
    ├── README.md            # 本文件（角色資源 + AI 設定說明）
    ├── knight.py            # 騎士（近戰＋格擋護盾）
    ├── mage.py              # 法師（技能投射物）
    ├── archer.py            # 弓箭手（攻擊＋技能均為投射物）
    ├── paladin.py           # 聖騎士（近戰衝刺）
    └── wizard.py            # 巫師（攻擊附加投射物＋ Entity 指定幀數生成）

ai/characters/
├── profile.py               # CharAIProfile dataclass
├── knight_ai.py
├── mage_ai.py
├── archer_ai.py
├── paladin_ai.py
└── wizard_ai.py
```

---

## 角色結構圖

```
BaseCharacter
├── name                   str
├── faceset_path           str
├── animations             dict[state → list[Surface]]
├── loop_map               dict[state → bool]
├── speed_map              dict[state → int]
├── stats                  CharStats          ← 戰鬥數值
├── hurt_boxes             dict[state → HitboxDef]
├── hit_boxes              dict[state → HitboxDef | None]
├── atk_fx                 FxDef | None       ← 近戰攻擊特效（固定在角色位置）
├── atk_proj_fx            FxDef | None       ← 攻擊投射物視覺（跟隨 Entity）
├── skl_fx                 FxDef | None       ← 技能特效（固定在角色位置）
└── skl_proj_fx            FxDef | None       ← 技能投射物視覺（跟隨 Entity）
```

---

## I. CharStats — 戰鬥參數表

```python
@dataclass
class CharStats:
    ...
```

### 基礎屬性

| 欄位         | 型別 | 單位  | 說明                              |
| ------------ | ---- | ----- | --------------------------------- |
| `max_hp`     | int  | ×1000 | 最大血量（e.g. 100_000 → 100 HP） |
| `max_mp`     | int  | ×1000 | 最大魔力                          |
| `skill_cost` | int  | ×1000 | 施放技能耗費的 MP                 |

### 普通攻擊（ATTACK）

| 欄位                      | 型別 | 單位   | 說明                                                   |
| ------------------------- | ---- | ------ | ------------------------------------------------------ |
| `atk_dmg`                 | int  | ×1000  | 近戰攻擊傷害                                           |
| `atk_depth`               | int  | ×1000  | 攻擊縱深（Y 軸寬容範圍）                               |
| `atk_kb_vx`               | int  | ×1000  | 攻擊擊飛橫向初速                                       |
| `atk_kb_vz`               | int  | ×1000  | 攻擊擊飛縱向初速（垂直）                               |
| `atk_kb_timer`            | int  | ticks  | 受擊持續 tick 數                                       |
| `atk_timer`               | int  | ticks  | ATTACK 動作總時長（幀數 × speed）                      |
| `atk_melee_enabled`       | bool | —      | True=啟用近戰 hit_box                                  |
| `atk_hit_frame_start`     | int  | 幀索引 | 近戰 hit_box 開始生效的動畫幀（含）                    |
| `atk_hit_frame_end`       | int  | 幀索引 | 近戰 hit_box 結束生效的動畫幀（含）                    |
| `atk_projectile_vx`       | int  | ×1000  | 攻擊投射物速度（0=不產生）                             |
| `atk_projectile_lifetime` | int  | ticks  | 攻擊投射物存活 tick 數                                 |
| `atk_spawn_frame`         | int  | 幀索引 | ATTACK 動畫第幾幀發射投射物（**推薦**，0-based）       |
| `atk_spawn_timer`         | int  | ticks  | 舊版：Rust timer 倒數值（`atk_spawn_frame=-1` 時生效） |
| `atk_dash_vx`             | int  | ×1000  | 衝刺距離（0=無衝刺，正值=朝面向方向）                  |
| `atk_dash_frame`          | int  | 幀索引 | 衝刺觸發的動畫幀                                       |

### 技能（SKILL）

| 欄位                      | 型別 | 單位   | 說明                                                             |
| ------------------------- | ---- | ------ | ---------------------------------------------------------------- |
| `skill_dmg`               | int  | ×1000  | 技能傷害（近戰與 entity 均使用）                                 |
| `skl_depth`               | int  | ×1000  | 技能縱深                                                         |
| `skl_kb_vx`               | int  | ×1000  | 技能擊飛橫向初速                                                 |
| `skl_kb_vz`               | int  | ×1000  | 技能擊飛縱向初速                                                 |
| `skl_kb_timer`            | int  | ticks  | 技能受擊持續 tick 數                                             |
| `skl_timer`               | int  | ticks  | SKILL 動作總時長                                                 |
| `skl_melee_enabled`       | bool | —      | True=啟用近戰 hit_box                                            |
| `skl_hit_frame_start`     | int  | 幀索引 | 近戰 hit_box 開始生效的動畫幀（含）                              |
| `skl_hit_frame_end`       | int  | 幀索引 | 近戰 hit_box 結束生效的動畫幀（含）                              |
| `skl_damage_absorb`       | int  | ×1000  | 護盾：SKILL 狀態下每次命中吸收的傷害（0=無護盾）                 |
| `skl_projectile_vx`       | int  | ×1000  | 技能投射物速度（0=不產生；搭配 `skl_spawn_entity` 可做靜止 AOE） |
| `skl_projectile_lifetime` | int  | ticks  | 技能投射物存活 tick 數                                           |
| `skl_spawn_frame`         | int  | 幀索引 | SKILL 動畫第幾幀發射 entity（**推薦**，0-based）                 |
| `skl_spawn_timer`         | int  | ticks  | 舊版：Rust timer 倒數值（`skl_spawn_frame=-1` 時生效）           |
| `skl_spawn_entity`        | bool | —      | True=強制生成 entity（即使 `skl_projectile_vx=0`，用於靜止 AOE） |

### spawn_frame / spawn_timer 計算方式

**推薦方式（`skl_spawn_frame`）：** 直接填動畫幀索引，`apply_char_config` 自動換算。

```python
skl_spawn_frame = 5   # SKILL 第 5 幀時發射 entity
atk_spawn_frame = 2   # ATTACK 第 2 幀時發射 entity
```

**舊版方式（`skl_spawn_timer`）：** 填 Rust timer 倒數值（`skl_spawn_frame` 設 `-1` 才生效）。

```
timer=skl_timer → ... → timer=spawn_timer → [此 tick 發射] → ... → timer=0 → 結束

換算公式：skl_spawn_timer = skl_timer - (目標幀 × speed)
```

---

## II. HitboxDef — 判定框

```python
@dataclass
class HitboxDef:
    ox: int   # 框左上角相對 Sprite 中心的水平偏移（向右為正）
    oy: int   # 框左上角相對 Sprite 中心的垂直偏移（向下為正）
    w:  int   # 框寬（px）
    h:  int   # 框高（px）
```

### 座標系統

```
    Sprite 中心 (0, 0)
     ←── ox 負值  │  ox 正值 ──→
                  │
                  ↓ oy 正值
```

**量測方式（圖片編輯器）：**
```python
center_x = frame_w // 2
center_y = frame_h // 2

ox = x1 - center_x   # x1 = 框左邊在單幀內的 x 座標
oy = y1 - center_y   # y1 = 框上邊在單幀內的 y 座標
w  = x2 - x1
h  = y2 - y1
```

### 判定框類型

| 屬性         | key          | Debug 色 | 用途                                  |
| ------------ | ------------ | -------- | ------------------------------------- |
| `hurt_boxes` | state（int） | 綠色     | 角色「被打到」的身體範圍              |
| `hit_boxes`  | state（int） | 紅色     | 攻擊「可命中」範圍；`None` 表示不傷人 |

**左右翻轉：** 框以 sheet 預設朝向定義，`facing_right` 時自動鏡像，不需手動寫兩份。

**近戰命中觸發條件：** 紅框與敵人綠框重疊，Rust 公式為  
`dx < atk_half_w + 15`（15 = CHAR_WIDTH/2，受害者身體補正）。

---

## III. FxDef — 特效定義

```python
@dataclass
class FxDef:
    path:     str    # 特效 sprite sheet 路徑
    frame_w:  int    # 單幀寬（px）
    frame_h:  int    # 單幀高（px）
    offset_x: int    # 相對角色前方偏移（px）；投射物視覺起始位置
    offset_y: int    # 向下偏移（px）
    scale:    float  # 縮放比例（1.0 = 原始大小）
    speed:    int    # 每幀持續 game tick（越小動畫越快）
```

### 四個 FX 屬性

| 屬性          | 使用時機             | 跟隨對象       | 翻轉行為               |
| ------------- | -------------------- | -------------- | ---------------------- |
| `atk_fx`      | ATTACK 狀態切換時    | 固定在角色位置 | 依 `facing_right` 翻轉 |
| `atk_proj_fx` | ATTACK entity 飛行中 | 跟隨 entity    | 依 `entity.vx` 翻轉    |
| `skl_fx`      | SKILL 狀態切換時     | 固定在角色位置 | 依 `facing_right` 翻轉 |
| `skl_proj_fx` | SKILL entity 飛行中  | 跟隨 entity    | 依 `entity.vx` 翻轉    |

---

## IV. 動畫切幀方法

### load_sheet（每列一個動作）

適用於每個動作占用完整一列的 sprite sheet：

```python
# (state, row, num_frames, loop, speed)
_STATE_ROWS = [
    (0, 0, 1, True,  6),   # IDLE:   第 0 列，1 幀，循環
    (1, 0, 5, True,  6),   # WALK:   第 0 列，5 幀，循環
    (2, 1, 5, False, 4),   # ATTACK: 第 1 列，5 幀，不循環
    (4, 2, 4, False, 8),   # SKILL:  第 2 列，4 幀，不循環
    (3, 3, 1, False, 4),   # HURT:   第 3 列，1 幀
]
self.load_sheet(sheet_path, frame_w, frame_h, _STATE_ROWS)
```

### load_sheet_linear（跨列線性索引）

適用於動畫幀跨越多列的 sprite sheet，以全局幀編號指定起始位置：

```python
_COLS = 8   # 每列有幾欄

# (state, start_frame, num_frames, loop, speed)
_STATE_FRAMES = [
    (0,  0,  1, True,  6),   # IDLE:   從第 0 幀起，1 幀
    (1,  0,  8, True,  6),   # WALK:   從第 0 幀起，8 幀（整列）
    (2,  8, 11, False, 4),   # ATTACK: 從第 8 幀起（第1列第0格），11 幀（跨兩列）
    (4, 19, 24, False, 4),   # SKILL:  從第 19 幀起，24 幀（跨多列）
    (3, 45,  3, False, 4),   # HURT:   從第 45 幀起，3 幀
]
self.load_sheet_linear(sheet_path, frame_w, frame_h, _COLS, _STATE_FRAMES)
```

**幀編號換算：**
```
全局幀編號 = 列索引 × COLS + 欄索引
列索引     = 全局幀編號 // COLS
欄索引     = 全局幀編號 % COLS
```

---

## V. 完整角色範例

### 範例 A：近戰＋格擋護盾（如騎士）

```python
self.stats = CharStats(
    max_hp=120_000,
    atk_dmg=12_000,  skill_dmg=0,
    atk_kb_vx=6_000, atk_kb_vz=4_000, atk_kb_timer=20,
    atk_timer=20,    skl_timer=40,
    atk_melee_enabled=True,
    skl_melee_enabled=False,   # SKILL 為格擋，不打人
    skl_damage_absorb=50_000,  # 格擋時每次吸收最多 50 HP 傷害
)
self.atk_fx = FxDef(path=..., frame_w=200, frame_h=200,
                    offset_x=60, offset_y=10, scale=0.5, speed=3)
```

### 範例 B：純投射物角色（如弓箭手）

```python
self.stats = CharStats(
    max_hp=60_000,
    atk_dmg=15_000,  skill_dmg=35_000,
    atk_timer=44,    skl_timer=96,
    atk_melee_enabled=False,
    skl_melee_enabled=False,
    atk_projectile_vx=1_000,
    atk_projectile_lifetime=40,
    atk_spawn_frame=8,          # ATTACK 第 8 幀發射
    skl_projectile_vx=1_000,
    skl_projectile_lifetime=150,
    skl_spawn_frame=15,         # SKILL 第 15 幀發射
)
self.atk_proj_fx = FxDef(path=..., frame_w=100, frame_h=100,
                          offset_x=55, offset_y=0, scale=0.6, speed=3)
self.skl_proj_fx = FxDef(path=..., frame_w=127, frame_h=97,
                          offset_x=50, offset_y=30, scale=0.8, speed=3)
```

### 範例 C：近戰攻擊＋技能投射物（如法師）

```python
self.stats = CharStats(
    max_hp=70_000,
    atk_dmg=8_000,  skill_dmg=20_000,
    atk_timer=20,   skl_timer=32,
    atk_melee_enabled=True,
    skl_melee_enabled=False,
    skl_projectile_vx=1_500,
    skl_projectile_lifetime=300,
    skl_spawn_frame=1,          # SKILL 第 1 幀發射
)
self.atk_fx    = FxDef(path=..., frame_w=193, frame_h=190, scale=0.4, speed=3)
self.skl_proj_fx = FxDef(path=..., frame_w=112, frame_h=100, scale=0.5, speed=5)
```

### 範例 D：衝刺近戰（如聖騎士）

```python
self.stats = CharStats(
    max_hp=120_000,
    atk_dmg=15_000,  skill_dmg=30_000,
    atk_timer=44,    skl_timer=72,
    atk_hit_frame_start=4, atk_hit_frame_end=7,   # 僅第 4–7 幀有判定
    skl_hit_frame_start=13, skl_hit_frame_end=17,
    atk_dash_vx=80_000,    # 衝刺距離 80 px
    atk_dash_frame=4,       # 第 4 幀觸發衝刺
)
```

### 範例 E：近戰攻擊 + 反向投射物（如巫師）

```python
self.stats = CharStats(
    max_hp=50_000,
    atk_dmg=10_000,  skill_dmg=25_000,
    atk_timer=28,    skl_timer=72,
    atk_melee_enabled=True,
    skl_melee_enabled=False,      # 技能傷害由 entity 負責
    atk_hit_frame_start=3,        # ATTACK 第 3–5 幀才有近戰判定
    atk_hit_frame_end=5,
    atk_projectile_vx=-2_000,     # ATTACK 同時往反方向發射投射物
    atk_projectile_lifetime=15,
    atk_spawn_timer=18,
    skl_projectile_vx=10_000,     # SKILL 發射向前移動的投射物
    skl_projectile_lifetime=25,
    skl_spawn_frame=14,           # SKILL 第 14 幀發射
)
self.atk_proj_fx = FxDef(path=..., frame_w=83, frame_h=99, scale=0.6, speed=4)
self.skl_proj_fx = FxDef(path=..., frame_w=79, frame_h=46, scale=0.8, speed=4)
```

### 範例 F：靜止 AOE entity

```python
self.stats = CharStats(
    skill_dmg=25_000,
    skl_timer=72,
    skl_melee_enabled=False,   # 傷害由 entity 負責
    skl_projectile_vx=0,       # 靜止
    skl_spawn_entity=True,     # 強制生成 entity（vx=0 時必須設此旗標）
    skl_projectile_lifetime=15,
    skl_spawn_frame=3,         # SKILL 第 3 幀生成 AOE
    skl_kb_vz=10_000,          # 強力上擊
)
# AOE 範圍由 _HIT_SKILL hitbox 的 w/h 決定（越大覆蓋越廣）
self.skl_proj_fx = FxDef(path=..., frame_w=124, frame_h=124, scale=0.8, speed=4)
```

---

## VI. 新增角色步驟

1. **建立 `characters/<name>.py`**，繼承 `BaseCharacter`
2. **定義切幀**：依 sheet 排布選擇 `load_sheet` 或 `load_sheet_linear`
3. **填入 `CharStats`**：參考上方參數表設定戰鬥數值
4. **設定 `hurt_boxes` / `hit_boxes`**：每個 state 各一個 HitboxDef（或 None）
5. **設定 FxDef**：依需求設定 `atk_fx`、`atk_proj_fx`、`skl_fx`、`skl_proj_fx`
6. **在 `main.py` 註冊**：
   ```python
   from src.python.assets_manager.characters.<name> import <ClassName>
   char_assets = {0: Knight(), 1: Mage(), 2: Archer(), 3: Paladin(), 4: Wizard(), 5: <ClassName>()}
   ```
   並在 Rust `Session::new()` 中新增對應的 `configs.push(CharConfig::default());`

---

## VII. Debug 模式

遊戲中按 **F1** 切換 Debug Overlay（含 AI 資訊面板）：

| 顯示元素     | 顏色 | 說明                                                    |
| ------------ | ---- | ------------------------------------------------------- |
| 角色 hurt 框 | 綠色 | `hurt_boxes[state]`                                     |
| 角色 hit 框  | 紅色 | `hit_boxes[state]`（None 時不顯示；僅在判定視窗內亮起） |
| 投射物框     | 紅色 | 以 `_HIT_SKILL` 或 `_HIT_ATTACK` 為基準                 |
| 投射物影子   | 灰色 | 顯示投射物在地面的投影                                  |

判定框僅為視覺參考，實際碰撞由 Rust 核心的固定點座標計算負責，
Python 端的 `HitboxDef` 數值須與 `CharConfig` 中對應的 `half_w/h/depth` 保持一致。

---

## VIII. AI 對手設定

AI 控制器以 **1-byte input bitmask** 的形式輸出，與真人玩家走完全相同的路徑進入 `perform_tick()`。每個角色只需提供「戰鬥知識」（Profile + Pattern 表 + GOAP 表），控制器負責所有決策邏輯。

```
make_ai(char_type, level, seed)
  ├─ level=1 → FSMAIController
  ├─ level=2 → PatternAIController ──fallback──▶ FSM
  └─ level=3 → GOAPAIController ──fallback──▶ Pattern ──fallback──▶ FSM
```

每個角色在 `ai/characters/<name>_ai.py` 定義三份資料，並在 `ai/factory.py` 的 `_CHAR_DATA` 以 `char_type` index 登錄：

```python
_CHAR_DATA = {
    0: (KNIGHT_PROFILE,  KNIGHT_PATTERNS,  KNIGHT_GOAP_ACTIONS),
    1: (MAGE_PROFILE,    MAGE_PATTERNS,    MAGE_GOAP_ACTIONS),
    ...
}
```

---

### CharAIProfile — 角色 AI 知識

```python
@dataclass
class CharAIProfile:
    preferred_range:    int    # 偏好的最佳戰鬥距離（Rust 單位，×1000）
    skill_mp_threshold: int    # 放技能所需 MP（Rust 單位，×1000）
    aggression:         float  # 0.0 保守 ～ 1.0 積極，影響 GOAP 靠近 cost
    attack_range:       int    # in_range 判定閾值（必須小於 Rust atk_depth）
```

`attack_range` 是最重要的欄位，**必須小於角色真實的碰撞深度**（`atk_depth` / `skl_depth`）。設定過大會讓 AI 自認在範圍內卻打不到；設定過小則降低攻擊頻率。

| 角色    | `attack_range` | 說明                    |
| ------- | -------------- | ----------------------- |
| Knight  | 65,000         | 近戰，短兵相接          |
| Mage    | 65,000         | 近戰兼投射物，中近距離  |
| Archer  | 220,000        | 純投射物，保持遠距離    |
| Paladin | 70,000         | 近戰衝刺，略大於 Knight |
| Wizard  | 80,000         | 近遠混合                |

---

### LV1：FSM（有限狀態機）

**無需角色專屬設定。** `FSMAIController` 使用統一的 `FSM_PARAMS_LV1` 難度參數，所有角色相同。

5 個離散狀態轉移邏輯：

```
APPROACH ──(dist ≤ attack_range)───▶ ATTACK
ATTACK   ──(動作完成)──────────────▶ RETREAT
RETREAT  ──(dist > safe_distance)──▶ APPROACH
APPROACH ──(MP ≥ threshold)────────▶ SKILL
任意狀態  ──(機率觸發)──────────────▶ WAIT
```

`reaction_delay`：環境改變後需等待數幀才切換狀態，模擬人類反應時間。難度越高延遲越短。

---

### LV2：Pattern AI（招式腳本）

Pattern 表定義角色的「肌肉記憶」：滿足條件時鎖定並播放一段按鍵序列。

```python
Pattern(
    name="技能名稱（debug 用）",
    condition=lambda ws: <謂詞>,          # 觸發條件，回傳 True/False
    action_sequence=[INPUT_A, INPUT_B],   # 按鍵序列
    step_duration=[6, 6],                 # 每步持續 tick 數（與序列等長）
    priority=8,                           # 多個同時觸發時選最高優先
    cooldown_frames=30,                   # 上次執行後的冷卻 tick 數
)
```

**方向符號**：`TOWARD`（朝向對手）與 `AWAY`（遠離對手）在執行時動態轉為實際左右鍵，不需根據站位調整：

```python
from src.python.ai.controllers.pattern_ai import Pattern, TOWARD, AWAY
action_sequence=[TOWARD, TOWARD | INPUT_ATTACK]  # 衝向對手同時普攻
```

**常用謂詞**（`ai/predicates.py`）：

| 謂詞函數                             | 說明                                |
| ------------------------------------ | ----------------------------------- |
| `can_use_skill(ws, profile)`         | MP ≥ `profile.skill_mp_threshold`   |
| `opponent_is_vulnerable(ws)`         | 對手正處於 HURT 狀態                |
| `self_hp_low(ws, threshold)`         | 自身 HP 低於 threshold（Rust 單位） |
| `opponent_approaching(ws)`           | 對手正在靠近                        |
| `is_in_preferred_range(ws, profile)` | 距離在偏好戰鬥範圍內                |

`ws` 為當幀的 world state dict，包含 `dist`、`self_hp`、`opp_hp`、`self_mp`、`opp_state`、`opp_vx_toward` 等欄位。

---

### LV3：GOAP（目標導向行動規劃）

GOAP 表定義所有可用的「行動選項」，由 A* 規劃器根據目標自動組合出最低成本序列。

```python
GOAPAction(
    name="動作名稱",
    preconditions={"in_range": True, "y_aligned": True},   # 執行前的世界狀態要求
    effects={"opp_hp": ("delta", -10_000)},                # 執行後的預期效果
    base_cost=1.0,                                          # 靜態基礎成本
    input_mask=INPUT_ATTACK,                                # 輸出的按鍵 bitmask
    direction="toward",                                     # 移動方向（可選）
    duration_frames=6,                                      # 動作持續幀數
    cost_fn=lambda ws: attack_mult(ws),                    # 動態成本函數
)
```

**通用行動工廠**（`ai/goap/base_actions.py`）：大多數角色可直接使用：

| 工廠函數                            | 效果                                |
| ----------------------------------- | ----------------------------------- |
| `make_approach(profile)`            | 靠近對手，成本受 `aggression` 影響  |
| `make_retreat(profile)`             | 後退，成本受 HP fuzzy 與 mode 影響  |
| `make_attack()`                     | 普攻，前提 `in_range + y_aligned`   |
| `make_y_align(base_cost, duration)` | 遠程角色 Y 軸對位（X 遠離、Y 靠近） |

**`preconditions` 常用 key**：

| key         | 型別  | 說明                        |
| ----------- | ----- | --------------------------- |
| `in_range`  | bool  | 是否在 `attack_range` 以內  |
| `y_aligned` | bool  | Y 軸深度差 ≤ 20,000 單位    |
| `in_danger` | bool  | HP 低或對手近距攻擊         |
| `self_mp`   | tuple | 比較式，如 `(">=", 15_000)` |
| `opp_hp`    | tuple | 比較式，如 `("<", 30_000)`  |

**`effects` 常用 key**：

| key         | 型別        | 說明                            |
| ----------- | ----------- | ------------------------------- |
| `in_range`  | bool        | 設定 in_range 狀態              |
| `y_aligned` | bool        | 設定 y_aligned 狀態             |
| `in_danger` | bool        | 設定 in_danger 狀態             |
| `opp_hp`    | delta tuple | `("delta", -N)` 預期減少對手 HP |

**`direction` 可選值**：

| 值                  | 行為                                 |
| ------------------- | ------------------------------------ |
| `"toward"`          | 朝對手移動                           |
| `"away"`            | 遠離對手                             |
| `"away_x_toward_y"` | X 軸遠離、Y 軸靠近（遠程角色對位用） |
| `None`（省略）      | 無移動（技能原地釋放）               |

> **重要**：技能 Action 的 `preconditions` **必須包含 `y_aligned: True`**，否則 AI 會在斜角位置釋放技能，因 Rust 碰撞深度（25,000）小於觸發閾值導致揮空。

---

## IX. 新增角色的 AI 設定步驟

1. **建立 `ai/characters/<name>_ai.py`**

2. **定義 `CharAIProfile`**：
   ```python
   <NAME>_PROFILE = CharAIProfile(
       preferred_range=...,      # 偏好的交戰距離
       skill_mp_threshold=...,   # 使用技能的 MP 門檻（與 CharStats.skill_cost 對齊）
       aggression=0.7,           # 侵略性
       attack_range=...,         # 近戰 ≈ 65,000；遠程依投射物有效射程設定
   )
   ```

3. **撰寫 LV2 Pattern 表**（`<NAME>_PATTERNS`）：
   - 通常 3–5 個 Pattern 覆蓋主要戰術
   - 各 Pattern 的觸發條件不應完全重疊，避免優先級競爭
   - 使用 `TOWARD`/`AWAY` 符號，不要硬編碼方向鍵

4. **撰寫 LV3 GOAP Action 表**（`<NAME>_GOAP_ACTIONS`）：
   - 必須包含 `make_approach(profile)` 和 `make_attack()`
   - 角色技能需個別定義 `GOAPAction`，`preconditions` 必須含 `y_aligned: True`
   - 遠程角色改用 `make_y_align()` 替代 `make_retreat()`

5. **在 `ai/factory.py` 的 `_CHAR_DATA` 登錄**：
   ```python
   from src.python.ai.characters.<name>_ai import (
       <NAME>_PROFILE, <NAME>_PATTERNS, <NAME>_GOAP_ACTIONS)

   _CHAR_DATA = {
       ...,
       N: (<NAME>_PROFILE, <NAME>_PATTERNS, <NAME>_GOAP_ACTIONS),
   }
   ```
   `N` 必須與 `assets_manager/characters/` 及 `game/loop.py` 的角色 index 一致。
