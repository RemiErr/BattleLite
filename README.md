# BattleLite — 開發者完整說明手冊

BattleLite 是一款 2D 橫向捲軸多人對戰遊戲，最多支援 4 人透過 P2P 連線對戰，延遲對策採用 GGRS (Rollback Netcode) 回滾機制。

<img width="1024" height="640" alt="image" src="https://github.com/user-attachments/assets/fb78512b-a059-4db5-96d0-e906b2c9958f" />

---

## 目錄

- [BattleLite — 開發者完整說明手冊](#battlelite--開發者完整說明手冊)
  - [目錄](#目錄)
  - [一、 架構總覽](#一-架構總覽)
  - [二、 2.5D 物理系統](#二-25d-物理系統)
  - [三、 固定點算術與確定性](#三-固定點算術與確定性)
  - [四、 角色狀態機](#四-角色狀態機)
  - [五、 碰撞系統](#五-碰撞系統)
    - [判定框種類](#判定框種類)
    - [3D AABB 碰撞公式（Rust 實作）](#3d-aabb-碰撞公式rust-實作)
    - [近戰命中觸發時間窗](#近戰命中觸發時間窗)
  - [六、 投射物（Entity）系統](#六-投射物entity系統)
    - [Entity 資料結構](#entity-資料結構)
    - [投射物生命週期](#投射物生命週期)
    - [投射物碰撞判定](#投射物碰撞判定)
    - [近戰 vs 投射物控制旗標](#近戰-vs-投射物控制旗標)
  - [七、 網路架構](#七-網路架構)
    - [整體連線流程](#整體連線流程)
    - [Lobby Server（Signaling Server）](#lobby-serversignaling-server)
  - [八、 STUN 探測與 NAT 打洞](#八-stun-探測與-nat-打洞)
    - [為什麼需要 STUN？](#為什麼需要-stun)
    - [STUN 探測實作](#stun-探測實作)
    - [NAT 打洞（UDP Hole Punching）](#nat-打洞udp-hole-punching)
    - [端點選擇策略](#端點選擇策略)
  - [九、 GGRS 回滾機制](#九-ggrs-回滾機制)
    - [什麼是 Rollback Netcode？](#什麼是-rollback-netcode)
    - [GGRS 在 BattleLite 的實作](#ggrs-在-battlelite-的實作)
    - [確定性要求](#確定性要求)
    - [輸入延遲（Input Delay）](#輸入延遲input-delay)
  - [十、 Session 啟動流程](#十-session-啟動流程)
    - [安全的 Session 資料傳遞](#安全的-session-資料傳遞)
  - [十一、 快速啟動](#十一-快速啟動)
    - [環境安裝（Ubuntu）](#環境安裝ubuntu)
    - [常用指令](#常用指令)
    - [遊戲內快捷鍵](#遊戲內快捷鍵)
  - [引用資源](#引用資源)

---

## 一、 架構總覽

```
┌─────────────────────────────────────────────────────────────────┐
│                        BattleLite 架構                          │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      Python 應用層                        │   │
│  │                                                          │   │
│  │  launcher.py          main.py         lobby_server/      │   │
│  │  ┌──────────┐    ┌─────────────┐  ┌──────────────────┐   │   │
│  │  │ 配對大廳  │    │  遊戲主循環  │  │ Signaling Server │   │   │
│  │  │ (Tkinter)│    │  (Pygame)   │  │     (FastAPI)    │   │   │
│  │  └────┬─────┘    └──────┬──────┘  └──────────────────┘   │   │
│  │       │ 加密 payload    │ 讀取/渲染狀態                   │   │
│  └───────┼─────────────────┼────────────────────────────────┘   │
│          │ CLI 參數        │ PyO3 綁定                          │
│  ┌───────▼─────────────────▼────────────────────────────────┐   │
│  │                       Rust 運算層                         │   │
│  │                                                          │   │
│  │    OfflineSession          GGRSSession                   │   │
│  │    ┌──────────────┐    ┌──────────────────┐              │   │
│  │    │  本機模擬     │    │  P2P 回滾同步    │              │   │
│  │    └──────┬───────┘    └────────┬─────────┘              │   │
│  │           └─────────┬───────────┘                        │   │
│  │                     │                                    │   │
│  │                perform_tick()                            │   │
│  │              ┌──────────────────┐                        │   │
│  │              │  物理 / 碰撞 /    │                        │   │
│  │              │  狀態機 / 實體    │                        │   │
│  │              └──────────────────┘                        │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**設計原則：**
- **Rust 主運算**：提供影響遊戲結果的邏輯運算（物理、碰撞、傷害），確保效率與穩定性。
- **Python 主互動**：Pygame 負責讀取 Rust 算好的座標並繪製 Sprite，不直接參與邏輯運算。
- **PyO3 橋接**：透過 `maturin` 將 Rust 編譯為 Python 擴充模組（`.so`），Python 以 `import battlelite_core` 呼叫。

---

## 二、 2.5D 物理系統

BattleLite 採用 LF2 風格的 2.5D 座標系：

```
         Z（高度 / 跳躍）
         │
         │          ● 玩家
         │         /│
         │        / │
         │       /  │ z（離地高度）
         │      /   │
 ────────┼─────/────┼──────────────── 地面 (z=0)
        /│    /     │
       / │   x──────┘
      /  │  （左右）
     /   │
    Y（深度 / 前後）

  螢幕投影:
  screen_x = world_x / 1000
  screen_y = world_y / 1000 - world_z / 1000   ← Z 軸在畫面上表現為垂直偏移
```

| 軸  | 方向     | 影響                              |
| --- | -------- | --------------------------------- |
| X   | 左右移動 | 角色橫向位置                      |
| Y   | 前後深度 | 決定繪製遮擋順序（Y 大 = 在前面） |
| Z   | 高低跳躍 | 受重力下拉；Z=0 為地面            |

**重力實作（Rust）：**
```
每幀: vz -= GRAVITY (400)
每幀: z  += vz
落地: if z <= 0 → z = 0, vz = 0
HURT 狀態落地時: vx /= 2（摩擦力）
```

**跳躍：**
```
按 JUMP 且 z == 0 → vz = JUMP_IMPULSE (9000)
跳躍高度 ≈ (9000)² / (2 × 400) = 101.25 單位（×1000 scale 後 ≈ 101 px）
```

---

## 三、 固定點算術與確定性

P2P 回滾的核心要求：**兩台機器跑同樣 inputs，必須得到完全相同的結果。**
浮點數（`f32`/`f64`）在不同 CPU/OS 上會有微小誤差，導致同步失敗（Desync）。

**解決方案：所有數值放大 1000 倍，以 `i32` 整數運算。**

```
現實單位      內部單位（×1000）   範例
─────────────────────────────────────────────────────
 1.5 px    →    1500            WALK_SPEED_X = 5000  (= 5 px/frame)
 9.0 px/f  →    9000            JUMP_IMPULSE = 9000  (= 9 px/frame)
 0.4 px/f² →     400            GRAVITY      = 400   (= 0.4 px/frame²)
```

**規則（不可違反）：**
- Rust 核心 `lib.rs` 內嚴禁 `f32`/`f64`。
- Python 只在渲染時做 `/ 1000` 轉換，不回寫 Rust。
- 隨機數只能用 session 初始化時提供的 seed，不能用 `std::rand`。

---

## 四、 角色狀態機

```
              ┌──────────────────────────────────────────┐
              │                                          │
              ▼                                          │
   ┌──────────────────┐   移動鍵     ┌──────────────────┐ │
   │                  │ ──────────▶ │                  │ │
   │       IDLE       │              │      WALK       │ │
   │       (0)        │ ◀────────── │       (1)        │ │
   └────────┬─────────┘   無移動     └────────┬─────────┘ │
            │                               │            │
      ATTACK鍵                        ATTACK鍵           │
            │                               │            │
            ▼                               ▼            │
   ┌──────────────────┐           ┌──────────────────┐   │
   │      ATTACK      │           │      ATTACK      │   │
   │       (2)        │           │       (2)        │   │
   │  timer倒數完畢    │           │  timer倒數完畢   │   │
   └────────┬─────────┘           └────────┬─────────┘   │
            │ timer==0                     │ timer==0    │
            └──────────────┬───────────────┘             │
                           │ → IDLE                      │
                           │                             │
   SKILL鍵（有足夠MP）      │       被攻擊命中             │
            │              │            │                │
            ▼              │            ▼                │
   ┌──────────────────┐    │   ┌──────────────────┐      │
   │      SKILL       │    │   │       HURT       │      │
   │       (4)        │    │   │       (3)        │      │
   │  timer倒數完畢    │    │   │  timer倒數完畢   │      │
   └────────┬─────────┘    │   └────────┬─────────┘      │
            │ timer==0     │            │ timer==0       │
            └──────────────┘            └────────────────┘
```

**狀態轉換規則：**
- `ATTACK` / `SKILL` 期間忽略移動輸入（`vx=0, vy=0`）。
- `HURT` 期間忽略所有輸入，僅受物理（重力、慣性衰減）影響。
- 命中後觸發 **Hitstop**（4幀），攻擊者與受擊者同時停頓，強化打擊感。

---

## 五、 碰撞系統

### 判定框種類

```
            角色 Sprite
   ┌────────────────────────────┐
   │    ┌──────────────────┐    │
   │    │                  │    │  ← HURT BOX（綠）
   │    │     HURT BOX     │    │    身體碰撞範圍，被攻擊時觸發
   │    │                  │    │
   │    └──────────────────┘    │
   │                            │  ┌──────┐
   │                            │  │ HIT  │  ← HIT BOX（紅）
   │                            │  │ BOX  │    攻擊動作觸發
   │                            │  └──────┘
   └────────────────────────────┘
           角色中心 (0,0)
     ←── ox 負值  │  ox 正值 ──→
                  ↓ oy 正值
```

### 3D AABB 碰撞公式（Rust 實作）

```
攻擊方中心 = attacker.x + (facing_right ? +front : -front)
受害方中心 = victim.x   + (facing_right ? +hurt_front : -hurt_front)

命中條件:
  |atk_center_x - vic_center_x| < atk_half_w + hurt_half_w   (X 軸)
  |attacker.y   - victim.y    | < atk_depth                  (Y 軸深度)
  |atk_center_z - vic_center_z| < atk_half_h + hurt_half_h   (Z 軸高度)
```

### 近戰命中觸發時間窗

```
timer 值:  atk_timer → ... → 15 → 14 → ... → 5 → 4 → ... → 0
                               ╔══════════════╗
                               ║  命中判定窗   ║  (timer: 15 → 5)
                               ╚══════════════╝
```

---

## 六、 投射物（Entity）系統

### Entity 資料結構

```
Entity {
  owner_id  : usize   // 發射者 player index
  x, y, z   : i32     // 當前位置
  vx, vy    : i32     // 速度（每幀位移）
  lifetime  : u32     // 剩餘存活幀數（降到 0 自動消失）
  is_skill  : bool    // true=SKILL投射物, false=ATTACK投射物
}
```

### 投射物生命週期

```
SKILL 動作開始
  │
  │  timer = skl_timer (例: 96)
  │
  ▼  每幀 timer--
  .
  .  timer == spawn_timer (例: 36)
  │  ─────────────────────────────────▶ 產生 Entity
  .                                         │
  .                                         │ 每幀: x += vx
  .                                         │       lifetime--
  ▼  timer == 0 → 狀態回 IDLE                │
                                            ▼  lifetime == 0
                                          Entity 消失

距離衰減傷害:
  ratio  = entity.lifetime / total_lifetime   (0.0~1.0)
  damage = base_dmg × ratio
  ↑ 投射物剛發射時傷害最高，飛愈遠傷害愈低
```

### 投射物碰撞判定

```
投射物使用與近戰相同的 AABB 判定，
尺寸來源:
  is_skill=true  → skl_half_w / skl_depth / skl_half_h
  is_skill=false → atk_half_w / atk_depth / atk_half_h

視覺（Python）: FxDef 定義的 sprite sheet，動畫循環播放
               跟隨 Entity.x/y/z 位置渲染
```

### 近戰 vs 投射物控制旗標

| 旗標                  | 效果                                         |
| --------------------- | -------------------------------------------- |
| `atk_melee_enabled`   | True → ATTACK 狀態啟用近戰 hit_box 判定      |
| `skl_melee_enabled`   | True → SKILL 狀態啟用近戰 hit_box 判定       |
| `atk_projectile_vx≠0` | ATTACK 動作在 `atk_spawn_timer` 幀發射投射物 |
| `projectile_vx≠0`     | SKILL 動作在 `spawn_timer` 幀發射投射物      |

兩者完全獨立，可同時開啟（近戰＋遠程）或各自關閉。

---

## 七、 網路架構

### 整體連線流程

```
玩家 A                        Lobby Server                   玩家 B
   │                               │                            │
   │── WS 連線 /ws/{room}/{name} ─▶│                            │
   │                               │◀─── WS 連線 ───────────────│
   │                               │                            │
   │◀── room_update ──────────────│── room_update ────────────▶│
   │                               │                            │
   │── report_endpoint ──────────▶│◀── report_endpoint ────────│
   │   { pub_ip, pub_port,         │    { pub_ip, pub_port,     │
   │     local_ip, local_port }    │      local_ip, local_port} │
   │                               │                            │
   │                               │    (所有玩家皆回報完畢)      │
   │                               │                            │
   │◀── punch_start ──────────────│── punch_start ────────────▶│
   │    { seed, players[] }        │   { seed, players[] }      │
   │                               │                            │
   │  [互相發送 UDP 打洞封包]       │                            │
   │ ────────────────────────────────────────────────────────▶ │
   │ ◀──────────────────────────────────────────────────────── │
   │                              │                             │
   │                         (等待 2 秒)                         │
   │                              │                             │
   │◀── game_start ───────────────│── game_start ─────────────▶│
   │    { seed, players[] }       │    { seed, players[] }      │
   │                              │                             │
   │  [啟動 GGRSSession P2P]       │     [啟動 GGRSSession P2P]  │
   │ ◀════════════ GGRS UDP 封包（只傳 Input） ═════════════════ │
```

### Lobby Server（Signaling Server）

- **技術**：FastAPI + WebSocket
- **職責**：收集玩家的公網端點，協調打洞時序，廣播 `game_start`
- **不傳遞**：遊戲狀態、位置座標
- **部署**：Docker 容器，URL 由 `.env` 中 `LOBBY_SERVER_URL` 設定

```
WebSocket 訊息類型:
  room_update     → 房間玩家列表更新
  report_endpoint → 玩家上報自己的 pub/lan IP:Port
  punch_start     → 觸發打洞，攜帶 seed 和所有玩家端點
  game_start      → 打洞等待後，通知正式開始（2 秒延遲）
```

---

## 八、 STUN 探測與 NAT 打洞

### 為什麼需要 STUN？

```
玩家 A 的視角:                    玩家 B 的視角:
  LAN IP: 192.168.1.10              LAN IP: 192.168.1.20
  LAN Port: 5000                    LAN Port: 5001

              ┌─────────────────────────────┐
              │           Router            │
              │  A ─▶ NAT ─▶ 1.2.3.4:10001 │
              │  B ─▶ NAT ─▶ 5.6.7.8:20002 │
              └─────────────────────────────┘

A 不知道自己對外的 IP:Port 是什麼 → 需要 STUN 探測
```

### STUN 探測實作

```python
# stun_utils.py 核心邏輯

# 1. 在指定 port 綁定 UDP socket
sock.bind(('0.0.0.0', local_port))

# 2. 發送 STUN Binding Request（RFC 5389）
#    封包格式: [Type(2B)] [Length(2B)] [Magic(4B)] [TransactionID(12B)]
request = struct.pack("!HHI12s", 0x0001, 0, 0x2112A442, transaction_id)
sock.sendto(request, ("stun.l.google.com", 19302))

# 3. 解析回應的 XOR-MAPPED-ADDRESS 屬性
#    port = x_port XOR (Magic >> 16)
#    ip   = x_ip   XOR Magic
public_ip, public_port = parse_response(data)
```

### NAT 打洞（UDP Hole Punching）

```
目標: 讓 A 和 B 能直接 P2P 通訊，繞過 NAT

步驟:
  1. 大廳交換端點後，A 和 B 同時向對方的公網端點發送 UDP 封包
  2. 發送封包的動作會在各自的 NAT 上「打開一個洞」
  3. 對方的封包抵達時，NAT 認為這是已知連線，允許通過

     A (1.2.3.4:10001)                B (5.6.7.8:20002)
          │                                  │
          │── UDP → 5.6.7.8:20002 ─────────▶│  A 的 NAT 記錄此連線
          │                                  │
          │◀──────── UDP ← 5.6.7.8:20002 ───│  B 的封包通過 A 的 NAT
          │                                  │
          │  P2P 通道建立！                   │

```
> 問題： 時序敏感，兩端必須「幾乎同時」發送  
> 解法： Lobby 的 `punch_start` 訊息作為同步信號，固定等待 2 秒後才發 `game_start`

### 端點選擇策略

同網域優先選擇，若玩家處於不同網路端點才走打洞路線

```
Launcher 上報兩個端點:
  pub_ip / pub_port       ← STUN 探測到的公網端點
  local_ip / local_port   ← 本機 LAN IP（路由探測）

連線建立邏輯:
  if A.pub_ip == B.pub_ip:
      # 同一個 NAT 後面（同網域）→ 使用 LAN IP
      connect(B.local_ip, B.local_port)
  else:
      # 不同網域 → 使用公網端點（打洞）
      connect(B.pub_ip, B.pub_port)
```

> 本專案未實作 TURN

---

## 九、 GGRS 回滾機制

### 什麼是 Rollback Netcode？

```
傳統「延遲式」網路代碼:
  等對方輸入到了才處理 → 畫面停頓（Lag）

回滾式網路代碼（GGRS）:
  用「預測」填補網路延遲，等真實輸入到了再「回滾重算」

  Frame 60: B 的 input 未到 → 預測 B 還在走路
  Frame 62: B 的 input 到了 → 發現 B 其實跳躍了！
              → 回滾到 Frame 60，用真實 input 重新計算 60/61/62
              → 畫面快速追上，幾乎無感
```

### GGRS 在 BattleLite 的實作

[GGRS](https://github.com/gschup/ggrs)：全稱 Good Game Rollback System，是在 Rust 上實作 [GGPO](https://www.ggpo.net) (Good Game Peace Out) 的一種 P2P 連線方式。

```
GGRSSession::advance() 每幀呼叫流程:

  session.poll_remote_clients()     ← 接收遠端封包
  session.add_local_input(input)    ← 提交本地輸入
  session.advance_frame()           ← GGRS 決定要做什麼

  回傳 GgrsRequest:
  ┌─────────────────────────────────────────────────────┐
  │ AdvanceFrame { inputs }                             │
  │   → perform_tick(state, inputs, configs)            │
  │   → 正常推進一幀                                     │
  ├─────────────────────────────────────────────────────┤
  │ SaveGameState { cell, frame }                       │
  │   → cell.save(frame, state.clone())                 │
  │   → 快照當前狀態（回滾的「存檔點」）                    │
  ├─────────────────────────────────────────────────────┤
  │ LoadGameState { cell }                              │
  │   → state = cell.load()                             │
  │   → 恢復快照（回滾的「讀檔」）                         │
  └─────────────────────────────────────────────────────┘
```

### 確定性要求

```
SaveGameState → LoadGameState → N × AdvanceFrame
  必須與不做回滾直接推進 N 幀得到完全相同的 GameState

這要求 perform_tick() 必須:
  >  只依賴 GameState（不讀取外部狀態）
  >  只用整數運算（固定點計算）
  >  不使用 std::rand（用 seed 初始化的 PRNG）
  >  不依賴時間（wall clock）
```

### 輸入延遲（Input Delay）

```
GGRS 預設加入 2 幀人工輸入延遲:
  Frame 1: 你按了跳躍
  Frame 3: 你看到角色跳起來（延遲 2 幀）

好處: 減少需要回滾的頻率
代價: 操作有 ~33ms 的輕微延遲感

設定位置: SessionBuilder::with_input_delay(2)
```

---

## 十、 Session 啟動流程

### 安全的 Session 資料傳遞

由於 Launcher 需要把 IP、Port、Seed 等資訊傳給 `main.py`，但透過 CLI 參數傳遞明文資料並不安全，因此在傳遞前先透過 [ChaCha20-Poly1305](https://en.wikipedia.org/wiki/ChaCha20-Poly1305) 演算法加密。

```
 Launcher                             main.py
    │                                    │
    │  payload = {                       │
    │    "local_id": 0,                  │
    │    "players": [                    │
    │      {"ip": "1.2.3.4",             │
    │       "port": 10001, "id": 1}      │
    │    ],                              │
    │    "seed": 123456                  │
    │  }                                 │
    │                                    │
    │  nonce = os.urandom(12)            │
    │  ciphertext = ChaCha20(payload)    │
    │  encoded = base64(nonce + cipher)  │
    │                                    │
    │── python main.py --payload <B64>─▶│
    │                                    │
    │                decrypt_payload()   │
    │                → 取得 ip/port/seed │
    │                → 建立 GGRSSession  │
```

> **格式：** `Base64(Nonce[12 bytes] + Ciphertext)`  

---

## 十一、 快速啟動

### 環境安裝（Ubuntu）

```bash
# 1. 系統依賴
sudo apt update && sudo apt install build-essential python3-dev python3-venv

# 2. Rust 工具鏈
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# 3. Python 虛擬環境
python3 -m venv venv --without-pip
source venv/bin/activate
curl https://bootstrap.pypa.io/get-pip.py | python3
pip install maturin pygame pytest httpx fastapi uvicorn customtkinter \
            cryptography websockets python-dotenv

# 4. 若你需要重新編譯 Rust 核心
cd src/rust_core && maturin develop && cd ../..
```

### 常用指令

```bash
# 單機開發模式（無網路）
python src/python/main.py --payload ""

# 啟動 Launcher UI（含配對大廳）
python src/python/launcher.py

# 啟動 Signaling Server（本機測試用）
uvicorn src.python.lobby_server.main:app --reload --port 8000

# 執行所有測試
pytest tests/

# 執行單一測試檔
pytest tests/test_physics.py -v
```

### 遊戲內快捷鍵

| 按鍵     | 功能                     |
| -------- | ------------------------ |
| F1       | 切換 Debug Overlay       |
| F2       | 切換受控角色（沙盒模式） |
| F3       | 切換角色職業（沙盒模式） |
| 上下左右 | 移動                     |
| Z        | 攻擊                     |
| X        | 技能                     |
| Space    | 跳躍                     |

---

## 引用資源

- Superpowers Asset Packs
  - 來源：<https://github.com/sparklinlabs/superpowers-asset-packs>
  - 授權：Creative Commons Zero v1.0 Universal (CC0-1.0)
  - 說明：本專案使用其中部分美術素材作為遊戲資源，感謝 Sparklin Labs 與素材作者 Pixel-boy。

- Noto Sans TC
  - 來源：<https://fonts.google.com/noto/specimen/Noto+Sans+TC>
  - 授權：SIL Open Font License 1.1（詳見 `src/assets/fonts/OFL.txt`）
  - 版權：Copyright 2014-2021 Adobe
  - 說明：用於遊戲介面的繁體中文字型顯示。

- Chakra Petch
  - 來源：<https://fonts.google.com/specimen/Chakra+Petch>
  - 授權：SIL Open Font License 1.1（詳見 `src/assets/fonts/OFL.txt`）
  - 版權：Copyright 2014 Cadson Demak
  - 說明：用於 HUD 的英文字型顯示。