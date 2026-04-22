# BattleLite 第四階段：進階戰鬥、投擲物與角色擴張規劃書

## 1. 核心願景 (Gameplay Evolution)
從基礎的物理與判定進化為具有深度戰鬥策略的遊戲。重點在於實作「實體系統 (Entity System)」以支援投擲物，以及建立具有差異化能力的新角色。

## 2. 實體系統 (Entity System in Rust Core)
為了支援氣功波、飛鏢等不屬於玩家的動態物件，需在 Rust 核心建立統一的實體管理器。
- **Entity 類別**:
    - `OwnerID`: 記錄是誰發射的，避免誤傷。
    - `Lifetime`: 生命週期（幀數或距離）。
    - `Velocity`: 獨立的 X, Y, Z 移動向量。
    - `Behavior`: 直線移動、追蹤、或觸地爆炸。
- **碰撞邏輯**: 實體與玩家 Body Box 的判定，觸發狀態切換（HURT）。

## 3. 進階戰鬥機制 (Advanced Combat Logic)
- **多段判定**: 同一個攻擊動作（或實體）可在特定時間間隔內產生多次傷害。
- **技能序列 (Combo Keys)**: 在 Rust 核心實作輸入緩衝 (Input Buffer)，判斷連續按鍵（如：下、前、攻）來觸發特定狀態。
- **擊飛力道 (Knockback Velocity)**: 不同的招式會賦予受擊者不同的 $X, Y, Z$ 初始受力。

## 4. 新角色：法師 (The Mage)
- **特性**: 脆皮（低 HP）、高法力上限（高 MP）、極快的回魔速度。
- **技能實作**:
    - **普通攻擊**: 短距離小火花。
    - **專屬技能**: 發射「火球術」(產生一個 Projectile Entity)。

## 5. 戰鬥視覺回饋與 HUD
- **視覺強化**: 實作受擊時的微小震動（Hit-stop）感。
- **戰鬥 HUD**: 在 Python 端繪製玩家頭像、動態 HP/MP 條與角色名稱標籤。

## 6. 素材規格 (Asset Specifications)

> 以下資料來自對 `src/assets/char/` 實際量測。GIF 檔為預覽參考，**實作以 sprite sheet 為準**。

### 6.1 各角色 Sprite Sheet 規格

| 角色 | 檔名 | Sheet 總尺寸 | 單幀尺寸 | 欄數 | 列數 | 總幀數 |
|------|------|-------------|---------|------|------|--------|
| Knight  | `sprite-sheet-183-123.png`  | 1092 × 615 | 183 × 123 | 6 | 5 | 25 |
| Archer  | `sprite-sheet-158x173.png`  | 1264 × 1038 | 158 × 173 | 8 | 6 | — |
| Mage    | `sprite-sheet-151x100.png`  | 755 × 400  | 151 × 100 | 5 | 4 | — |
| Paladin | `sprite-sheet-249x100.png`  | 1494 × 700 | 249 × 100 | 6 | 7 | — |
| Wizard  | `sprite-sheet-161x106.png`  | 966 × 636  | 161 × 106 | 6 | 6 | — |

### 6.2 Knight Sheet 列對照表（已確認）

Knight 為 Stage 4 主要實作角色，各列動作已完整分析：

| Row | y 起點 (px) | 幀數 | 對應動作 | Rust State |
|-----|------------|------|---------|------------|
| 0 | 0   | 6 | Walk（奔跑，盾牌前置）     | `STATE_WALK` |
| 1 | 123 | 6 | Attack（弧形劍斬＋斬擊特效）| `STATE_ATTACK` |
| 2 | 246 | 6 | Guard（舉盾格擋＋紅色光效） | `STATE_SKILL` |
| 3 | 369 | 6 | Hit（受擊後退）             | `STATE_HURT` |
| 4 | 492 | 1 | Death / 轉場幀              | （待定） |

- **IDLE** 使用 Row 0 第 0 幀靜止顯示（sheet 內無獨立 idle 列）。
- **WALK** 循環播放 Row 0 全部 6 幀。
- 其餘角色的列對照待實作時逐一量測確認。

### 6.3 Sprite Sheet 切幀公式

```python
frame_x = (frame_index % cols) * frame_w
frame_y = (frame_index // cols) * frame_h
rect = pygame.Rect(frame_x, frame_y, frame_w, frame_h)
```

---
*註：Sprite Sheet 載入與 Launcher UI 升級已移至基礎建設備忘錄，不作為本階段核心。*
