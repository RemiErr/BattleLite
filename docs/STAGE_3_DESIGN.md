# BattleLite 第三階段：真實連線與角色演化設計文件

## 1. 核心願景 (The Transition)
從「單機物理實驗室」轉向「可供網際網路對戰的 P2P 遊戲原型」。重點在於解決 NAT 穿透、連線安全性以及資源管理的高擴展性。

## 2. 安全啟動與手遞手協議 (Secure Handoff)
為了防止對手 IP 等敏感資訊在系統進程中以明文顯示，實作了加密啟動機制。
- **加密演算法**: 使用 `ChaCha20-Poly1305` 對稱加密。
- **流程**:
    1.  **Launcher**: 獲取房間資訊後，將 JSON 資料打包並使用預共享金鑰 (PSK) 加密。
    2.  **CLI 傳參**: 透過 `--payload [Base64_String]` 啟動遊戲本體。
    3.  **Rust 核心**: 遊戲啟動後立即呼叫 Rust 內部的 `decrypt_payload` 進行解密。
- **解耦合設計**: 啟動模組與 GGRS 邏輯完全獨立，確保安全性檢查不干擾連線引擎。

## 3. 連線架構與打洞機制 (P2P Connectivity)
- **信令大廳 (Signaling Lobby)**:
    - 採用 **FastAPI + WebSockets** 實作。
    - 職責：負責媒合玩家、交換公網 Endpoint、同步隨機種子 (Seed)。
    - 部署：支援 Docker 容器化，已部署至雲端環境。
- **STUN 探測 (Method A)**:
    - 為了重複利用埠號，Launcher 會先開啟 UDP Socket 進行 STUN 探測。
    - 獲取公網 IP/Port 後，**立即釋放 (Close)** 該 Socket。
    - 隨後由 Rust 核心重新綁定 (Bind) 同一埠號進行 GGRS 同步，確保 NAT 映射有效。
- **WSL2 環境適配**: 使用鏡像網路模式 (`mirrored`) 以解決虛擬隔離導致的打洞失敗。

## 4. 組合模式重構 (Composition Pattern)
為了解決單人測試與多人連線的邏輯分歧，重構為雙軌 Session 架構：
- **OfflineSession**: 純 Rust 物理模擬，無網路依賴，秒開秒測。
- **GGRSSession**: 完整回滾連線模式。
- **統一接口**: Python 端僅需根據 `is_offline` 標籤實例化對應物件，其餘呼叫完全對等。

## 5. OOP 動畫與資源系統 (Assets Manager)
- **架構**:
    - `BaseCharacter`: 封裝 Sprite Sheet 切割、動畫計時與選幀邏輯。
    - 角色類別 (如 `Knight`): 繼承基類，定義各狀態的幀數、播放速度與循環模式。
- **動畫驅動**: 由 Rust 核心回傳的 `state` 與 `timer` 作為基準，Python 負責渲染相對應的 Frame Index。
- **目錄規範**: 一角色一目錄，內含 `config.json` 描述碰撞箱偏移。

## 6. 待完善與技術債備忘
- **自動更新**: 未來可以實作 `.so/.pyd` 核心文件的熱更新。
- **動態金鑰**: 目前使用固定 PSK，未來應由 Launcher 在啟動前動態產生。
- **大廳持久化**: 目前為純記憶體，若需負載平衡需引入 Redis。
