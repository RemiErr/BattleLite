# BattleLite - 系統架構說明書 (Architecture)

本文件詳述 BattleLite 的設計哲學與技術實作細節。

## 1. 設計哲學：Python 主導，Rust 輔助
- **Python (大腦)**: 負責處理遊戲循環、動畫狀態切換、Tileset 場景管理、UI 與音效。開發者應在此層編寫大部分的遊戲邏輯。
- **Rust (引擎)**: 負責 GGRS 網路同步與確定性物理運算。當需要進行 Rollback (回滾) 時，Rust 能快速重新模擬物理狀態。

## 2. 空間與物理系統 (LF2 Style)
- **2.5D 座標系**:
    - **X**: 左右移動。
    - **Y**: 深淺移動 (Depth)，影響繪製順序 (Z-order)。
    - **Z**: 高低移動 (Height/Jumping)，受重力影響。
- **物理計算**:
    - 採用 **物理模擬 (Physics Simulation)** 處理 Z 軸。
    - **確定性 (Determinism)**: 所有數值在傳入 Rust 前會縮放 1000 倍（例如 1.5 變為 1500），以整數 (i32) 運算避免浮點數造成的同步誤差 (Desync)。

## 3. 數據流與同步 (The Bridge)
1. **輸入獲取 (Python)**: Pygame 讀取鍵盤/手把，轉換為 Bitmask (1 Byte)。
2. **狀態推進 (Rust)**:
    - Python 呼叫 `core.advance_frame(input_mask)`。
    - Rust 根據 GGRS 指令決定是「預測前進」還是「回滾重算」。
    - Rust 更新所有實體 (Entities) 的 X, Y, Z 座標。
3. **渲染更新 (Python)**:
    - Python 讀取 Rust 算好的座標。
    - 根據 Y 座標進行排序，繪製 Sprite Sheet 動畫。

## 4. 角色狀態機 (State Machine)
- 雖然邏輯在 Python，但核心狀態標籤 (如 `IDLE`, `WALK`, `ATTACK`, `HURT`, `JUMP`) 會存儲於 Rust 的 `GameState` 中，以便 GGRS 進行快照 (Snapshot)。

## 5. 連線架構
- **P2P Rollback (GGRS)**: 玩家之間僅交換 Input，不交換位置。
- **確定性隨機**: 使用種子碼 (Seed) 初始化 Rust 的偽隨機生成器 (PRNG)。
