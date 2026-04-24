# BattleLite 第五階段：遊戲循環完整化規劃書

## 1. 核心願景 (Stage 5 Goals)

Stage 4 完成了戰鬥基礎（判定、HUD、Hit-stop），Stage 4 追加任務負責角色擴張（Mage → Wizard）。Stage 5 的目標是讓遊戲從「無限沙盒」升級為**具有完整遊戲循環的對戰遊戲**：

1. **死亡與回合系統**：有勝負才算對戰。
2. **角色選擇畫面**：多角色框架完成後，玩家需要選角入口。
3. **Combo Keys 輸入緩衝**：技能觸發深度化。
4. **音效系統**：打擊感與沉浸感。
5. **Launcher 升級**：設定選單與社交功能。

---

## 2. 任務 28：死亡與回合系統

### 2.1 Rust 端

新增 `STATE_DEAD = 5`，`hp <= 0` 時進入此狀態：

```rust
// perform_tick() 中，hp 歸零觸發
if self.hp <= 0 && self.state != STATE_DEAD {
    self.state = STATE_DEAD;
    self.timer = 0;
    self.vx = 0; self.vz = 0;
}
// STATE_DEAD 不接受任何輸入
if self.state == STATE_DEAD { return; }
```

`GameState`（或 `OfflineSession`）新增回合計數與存活判定：

```rust
pub fn alive_count(&self) -> u32  // 存活玩家數
pub fn winner_id(&self) -> Option<u32>  // 最後存活者 ID
pub fn round(&self) -> u32  // 當前回合數
```

### 2.2 Python 端

- 每幀檢查 `session.winner_id()`，有值時暫停輸入並顯示結算畫面。
- 結算畫面顯示：勝者名稱、各玩家剩餘 HP、回合數。
- 按任意鍵重置場地（呼叫 `session.reset_round()`）。

### 2.3 HUD 整合

死亡玩家的 HP 條顯示為灰色，名稱加上刪除線或淡出效果。

---

## 3. 任務 29：角色選擇畫面

### 3.1 流程

```
Launcher 選角 → 寫入 session payload → main.py 讀取 char_type → 套用 CharConfig
```

線上模式：雙方選角透過 Lobby Server 交換，`session payload` 中增加 `char_type` 欄位。

### 3.2 Launcher 端

在「開始遊戲」前新增選角畫面（CustomTkinter），顯示各角色頭像與基本數值（HP、MP、定位說明）。

### 3.3 main.py 端

`char_asset` 從單一物件改為依 `char_type` 查詢字典：

```python
char_assets: dict[int, BaseCharacter] = {
    0: Knight(), 1: Mage(), 2: Archer(), 3: Paladin(), 4: Wizard()
}
# 渲染時
char_type = p.character_type
sprite = char_assets[char_type].get_sprite(p.state, ...)
```

HUD 的 `char_assets` 直接傳入此字典，自動支援多角色頭像。

---

## 4. 任務 30：Combo Keys 輸入緩衝

### 4.1 設計目標

讓玩家可以用**序列按鍵**觸發進階技能，例如：`↓ → ATTACK` 觸發衝刺斬。

此機制必須在 **Rust 核心**實作，確保回滾時狀態可快照還原。

### 4.2 Rust 端設計

```rust
pub struct Player {
    // ... 現有欄位 ...
    pub input_buf: [u8; 8],  // 最近 8 幀的輸入歷史（環形緩衝）
    pub buf_head: u8,        // 環形緩衝索引
}
```

序列辨識在 `perform_tick()` 中，讀取 `input_buf` 判斷特定模式後觸發對應 state。

### 4.3 注意事項

- `input_buf` 與 `buf_head` 必須納入 GGRS 狀態快照。
- 初期先為每個角色各實作 1 個 combo，驗證框架後再擴充。

---

## 5. 任務 31：音效系統整合

### 5.1 架構

音效完全在 **Python 端**，不影響 Rust 確定性物理。

```
src/assets/sfx/
├── hit_light.wav
├── hit_heavy.wav
├── jump.wav
├── skill_mage_fireball.wav
└── bgm/
    └── stage01.ogg
```

### 5.2 觸發點

| 事件 | 觸發條件 | 音效 |
|------|---------|------|
| 命中（普攻） | `hitstop` 由 0 升起（rising edge） | `hit_light.wav` |
| 命中（技能） | 同上，來源 state == SKILL | `hit_heavy.wav` |
| 跳躍 | `vz > 0` 且前幀 `vz == 0` | `jump.wav` |
| 技能施放 | state 切換到 SKILL | `skill_<char>.wav` |
| 背景音樂 | 遊戲啟動 | `bgm/stage01.ogg`（循環）|

### 5.3 實作步驟

1. 建立 `src/python/sfx_manager.py`（封裝 `pygame.mixer`）。
2. 在 `main.py` 渲染迴圈末端，比對前後幀狀態差，呼叫 `sfx_manager`。
3. 音量設定從 `settings.json` 讀取，`pygame.mixer` 初始化時套用。

---

## 6. 任務 32：Launcher 功能升級

### 6.1 設定選單

| 設定項目 | 類型 | 存放位置 |
|---------|------|---------|
| 主音量 | 滑桿 0–100 | `settings.json` → `"volume"` |
| 音效音量 | 滑桿 0–100 | `settings.json` → `"sfx_volume"` |
| 解析度 | 下拉選單 | `settings.json` → `"resolution"` |
| 全螢幕 | 開關 | `settings.json` → `"fullscreen"` |

### 6.2 社交功能

- **房間碼複製**：點擊房間碼旁的「複製」按鈕，寫入系統剪貼簿（`pyperclip` 或 `tkinter.clipboard`）。
- **線上人數顯示**：Launcher WebSocket 訂閱 Lobby Server 的 `/online_count` 推播。

---

## 7. 開發順序建議

| 優先序 | 任務 | 依賴 |
|-------|------|------|
| 1 | 任務 28：死亡與回合系統 | 無 |
| 2 | 任務 31：音效系統 | 無（可平行） |
| 3 | 任務 29：角色選擇畫面 | Stage 4 追加任務（角色擴張） |
| 4 | 任務 32：Launcher 升級 | 任務 31（音量設定） |
| 5 | 任務 30：Combo Keys | 多角色框架穩定後 |

---

## 8. 長期目標（Stage 6 候補）

- **重播系統**：記錄每幀輸入序列，利用 Rust 確定性物理還原整場對戰，無需錄影。
- **自建 coturn**：替換 Metered.ca 免費 TURN，取得完整流量控制權。
- **4 人負載優化**：回滾深度 ≤ 8 幀、穩定 ≥ 55 FPS、`perform_tick()` < 0.5 ms。

---

*此規劃書依 `TODO.md` Stage 5 任務撰寫，角色擴張（Mage/Archer/Paladin/Wizard）詳見 `STAGE_4_DESIGN.md` 追加任務節。*
