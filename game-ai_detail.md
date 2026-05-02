# BattleLite AI 技術實作詳解

這份文件記錄了 **BattleLite** 遊戲中三種等級的 AI 演算法運作邏輯，以及在測試過程中發現的行為異常分析。

---

## 1. AI 演算法架構概覽

遊戲 AI 採用層級化設計（Layered Architecture），將 AI 行為分為「反射」、「肌肉記憶」與「戰略思考」三個層次：

| 等級    | 演算法                 | 模擬對象 | 技術核心                      |
| :------ | :--------------------- | :------- | :---------------------------- |
| **LV1** | **FSM (有限狀態機)**   | 脊椎反射 | 狀態轉移表 + 反應延遲         |
| **LV2** | **Pattern AI**         | 肌肉記憶 | 腳本序列播放 + 符號化方向解析 |
| **LV3** | **GOAP + Fuzzy Logic** | 戰略大腦 | A* 規劃 + 模糊邏輯動態成本    |

---

## 2. 演算法細節說明

### 層級一：FSM (Finite State Machine)
*   **運作原理**：將 AI 行為劃分為 `APPROACH`、`ATTACK`、`RETREAT` 等離散狀態。每幀檢查環境數值，滿足條件即切換狀態。
*   **特色**：為了模擬人類反應，實作了 `reaction_delay`（反應延遲）。即使環境改變，AI 也需等待數幀後才會改變動作。

### 層級二：Pattern AI
*   **運作原理**：基於「招式表」驅動。當滿足特定謂詞（Predicate）時，AI 會鎖定並播放一段預設的 `action_sequence`（按鍵序列）。
*   **符號化輸入**：支援 `TOWARD` (朝向對手) 與 `AWAY` (遠離對手) 符號，在執行時動態解析為實際的左右方向鍵，解決了 AI 在不同側時的指令適應問題。

### 層級三：GOAP + Fuzzy Logic
*   **Fuzzy Logic (感官層)**：將精確數值（如 HP: 40%）轉換為模糊集合隸屬度（如 Danger: 0.7）。這讓 AI 具有「程度感」，能評估局勢的危險或安全係數。
*   **GOAP (規劃層)**：
    1.  **設定目標**：根據模糊感官決定目標（如 `SURVIVE` 或 `WIN`）。
    2.  **路徑規劃**：利用 A* 搜尋演算法，在所有可用 Action 中尋找總 Cost 最低的路徑。
    3.  **動態成本**：Action 的 Cost 會受 Fuzzy 影響。在危險時，「靠近」的 Cost 會變貴，「防禦」會變便宜。

---

## 3. 測試問題與行為分析 (Troubleshooting)

在測試 Level 3 GOAP 時觀察到的異常現象及其背後理由：

### Q1：AI 出現左右擺動（舞步現象）
*   **理由**：**重複規劃 (High-frequency Replanning)**。
*   **技術細節**：`should_replan` 函數對邊界狀態過於敏感。當 AI 處於攻擊範圍邊緣（例如 X 距離在 79,999 與 80,001 之間跳動），導致 `in_range` 布林值每幀切換，觸發 AI 不斷廢棄舊計畫並生成新計畫，視覺上呈現抖動。

### Q2：GOAP 是否整合了 Pattern 或 FSM？
*   **FSM 整合**：**是**。GOAP 擁有 Fallback 機制。當 A* 搜尋找不到合法計畫時，會直接呼叫 LV1 FSM 來接管輸入。
*   **Pattern 整合**：**否**。目前兩者為平行系統，GOAP 傾向於自行組合原子動作而非調用預設腳本。

### Q3：AI 站在斜對角揮空（Y 軸未對齊）
這屬於 **「規劃條件」與「物理數值」的不一致**：
*   **規劃失誤**：GOAP Action 的 `preconditions` (先決條件) 可能只檢查了 `in_range` (X 軸)，而漏掉了 `y_aligned` (Y 軸) 的強制要求，導致 AI 認為不需要對齊就能攻擊。
*   **數值失誤**：Python AI 判斷 `y_aligned` 的閾值（例如 50,000）大於 Rust 核心實際碰撞判定的深度（`ATK_DEPTH_REACH` = 25,000）。這導致 AI「以為」打得到，但物理引擎判定未碰撞。
*   **執行修正能力不足**：雖然執行層會嘗試加入 `y_toward` 方向，但若動作持續時間太短，AI 來不及在攻擊幀結束前修正巨大的 Y 軸偏差。

---

## 4. 修復方案與紀錄 (2026-05-02)

針對上述觀察到的異常行為，已完成以下修復工作：

### 4.1 決策抖動修復：遲滯補償 (Hysteresis)
*   **診斷**：AI 在攻擊範圍邊緣因 `dist` 微小跳動導致每幀 `in_range` 布林值改變，觸發無窮重新規劃。
*   **修復**：在 `world_state.py` 中實作遲滯邏輯。
    *   **進入條件**：目標進入 90% 範圍才判定為 `in_range`。
    *   **離開條件**：目標離開 110% 範圍才判定為 `in_range` 失效。
*   **結果**：AI 在邊緣處表現更為穩定，不再左右瘋狂擺動。

### 4.2 對角線攻擊修復：Y 軸對齊強制化
*   **診斷**：Python 層對位閾值 (80,000) 過大，且 Action 缺乏 Y 軸先決條件。
*   **修復方案**：
    1.  **數值同步**：將 `Y_ALIGN_THRESHOLD` 下調至 **20,000** (嚴於 Rust 核心的 25,000)，確保攻擊絕對有效。
    2.  **條件補強**：
        *   **GOAP**：在 `base_actions.py` 的 `make_attack` 與各角色的技能 Action（如 Knight 的突進斬、Mage 的近戰）中加入 `y_aligned: True` 的先決條件。
        *   **Pattern AI**：更新 `mage_ai.py` 與 `archer_ai.py` 的腳本觸發條件，將 `dist_y` 判定從 80,000 修改為 20,000。
        *   **FSM**：在 `fsm_ai.py` 的狀態轉換中強制加入 `is_y_aligned` 檢查。
    3.  **規劃優化**：移除 `make_y_align` 中強制 `in_range: False` 的副作用，讓規劃器能更靈活地在範圍內進行微調對位。

### 4.3 修正範圍彙整
*   `src/python/ai/goap/world_state.py` (遲滯邏輯、閾值下調)
*   `src/python/ai/controllers/goap_ai.py` (啟用歷史 WorldState 傳遞)
*   `src/python/ai/controllers/fsm_ai.py` (LV1 對齊檢查)
*   `src/python/ai/goap/base_actions.py` (通用動作條件補強)
*   `src/python/ai/characters/*_ai.py` (全角色技能條件同步修復)
