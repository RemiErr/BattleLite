# BattleLite 第二階段：戰鬥核心與系統擴展規劃書

## 1. 角色狀態機 (State Machine)
- **核心設計**: Python (呈現) 與 Rust (邏輯) 的分離。
- **Rust 端 (The Decision Maker)**: 實作角色狀態標籤（IDLE, WALK, JUMP, ATTACK, HURT, SKILL, KNOCKDOWN）與狀態轉換邏輯。
- **Python 端 (The Performer)**: 讀取 Rust 狀態標籤，執行相對應的 Sprite Sheet 動畫與音效播放。
- **優點**: 確保回滾模擬的高效能與邏輯確定性。

## 2. 戰鬥判定機制 (Hitbox System)
- **碰撞箱定義**:
    - **Body Box (受擊框)**: 玩家角色受擊範圍。
    - **Attack Box (攻擊框)**: 攻擊判定範圍。
- **2.5D 判定邏輯**: 
    - X & Y 軸進行 AABB 矩形重疊檢測。
    - Z 軸 (高度) 判定兩者高度差是否在有效範圍內。
- **擴展性**: 支援近戰、投擲物 (Projectiles) 與地面震波。

## 3. 視覺輔助開發工具 (Visual Dev Tools)
- **Debug Overlay**: 
    - 顯示 Body Box (綠色) 與 Attack Box (紅色)。
    - 即時監控資訊：當前幀數 (Frame)、回滾幀數 (Rollback Count)、GGRS 同步狀態、玩家實體座標與速度。

## 4. 多玩家支援 (4-Player Support)
- **架構擴展**: 將原本單人測試的 Session 擴展為支援最多 4 人的 Full-Mesh P2P 連線。
- **房間系統**: 簡單的配置驅動模式，支援 1-4 位玩家加入戰鬥。

## 5. 角色技能與魔力系統 (Skill System)
- **屬性**: 新增 HP (血量) 與 MP (魔力) 系統。
- **觸發**: 透過輸入序列判斷組合鍵（不額外佔用 Bitmask 位元），施放角色專屬技能並扣除 MP。

## 📅 任務優先順序 (Roadmap)
1. **[Task 9] 視覺輔助開發工具**: 建立 Debug 視野。
2. **[Task 10] 多玩家支援擴展**: 奠定多人同步基礎。
3. **[Task 11] 角色狀態機與基礎戰鬥**: 實作揮拳、受擊與判定。
4. **[Task 12] 角色技能與魔力系統**: 完備角色戰鬥樂趣。
