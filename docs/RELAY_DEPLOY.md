# Self-hosted Lobby + Relay 部署指引

> 用途：當 Render 雲端 lobby 失效，或某幾位玩家遇到對稱 NAT 連不上時，
> 由值班人員在 30 分鐘內於一台主機架起完整備援。
>
> 本方案**僅作備援方案**：無 auto-healing、無監控儀表板，靠人員看 stdout log。

---

## 1. 主機需求

- Python 3.12（與 client `maturin develop` 時的 ABI 對齊）
- 對 client 可達的 IP（同網段填 LAN IP，公網填 VPS public IP）
- 開放 `8000/tcp`（lobby WebSocket）與 `9000/udp`（relay）

---

## 2. 一次性 setup

```bash
git clone <repo> BattleLite && cd BattleLite
python3 -m venv venv --without-pip
source venv/bin/activate
curl https://bootstrap.pypa.io/get-pip.py | python3
pip install -r requirements.txt
```

---

## 3. 產生 Ed25519 keypair

```bash
python scripts/gen_lobby_keypair.py
```

腳本會印出：
- **私鑰** → 貼到本機 `.env` 的 `LOBBY_SIGNING_KEY=`
- **公鑰** → 覆寫本機 `config/lobby_pubkey.txt`，**並分發給所有 client**
- **fingerprint** → 比對用，讓 client 確認 pubkey 對得上 server

> ⚠️ **不要**沿用 Render 主機的私鑰——應為這台主機獨立產生 keypair，
> 把信任邊界縮到「該值班人員 + 該網段」。

---

## 4. 設定 `.env`

```bash
cp .env.example .env
```

填入：
```
LOBBY_SIGNING_KEY=<上一步產生的私鑰>
RELAY_PUBLIC_IP=192.168.1.50         # 本機對 client 可達的 IP
RELAY_UDP_PORT=9000
SHEETS_WEBHOOK_URL=                  # 留空即可，急救方案不需要排行榜
```

---

## 5. 防火牆

| 平台        | 指令                                                 |
| ----------- | ---------------------------------------------------- |
| Linux (ufw) | `sudo ufw allow 8000/tcp && sudo ufw allow 9000/udp` |
| Windows     | 進階防火牆 → 輸入規則 → 新增 TCP 8000 + UDP 9000     |
| macOS       | 系統設定 → 網路 → 防火牆 → 允許 python               |

**WSL2 注意**：需 `networkingMode=mirrored`（見 CLAUDE.md），否則 Windows 主機外的同網段機器看不到 WSL 內的服務。

---

## 6. 啟動

```bash
source venv/bin/activate
uvicorn src.python.lobby_server.main:app --host 0.0.0.0 --port 8000
```

**注意**：
- 必須 `--host 0.0.0.0`，預設只綁 `127.0.0.1` 同網段連不進來
- **不要**加 `--reload`（會重複起 relay）
- Lobby 啟動時應印 `[RELAY] listening on 0.0.0.0:9000`

---

## 7. Client 端切換（每台同網段電腦）

1. 覆寫 `config/lobby_pubkey.txt`（貼上 step 3 的公鑰）
2. 編輯 `.env`：
   ```
   LOBBY_USE_LOCAL=true
   LOBBY_SERVER_URL_LOCAL=ws://192.168.1.50:8000
   ```
3. 啟動 launcher 確認可連到

順序**先換 pubkey 再切 URL**，否則會驗章失敗。

---

## 8. 連線測試

```bash
# 同網段另一台
curl http://192.168.1.50:8000/        # lobby 應回應
nc -uvz 192.168.1.50 9000             # relay UDP port 探測
```

---

## 9. 監控（人員觀察）

正常運作時 stdout 會看到：

```
[OK] Sheets pushed: ...                    # 排行榜（可忽略）
[RELAY] listening on 0.0.0.0:9000
[RELAY] match=abc123 registered peers=4   # 自動切 relay 時
[RELAY] matches=1 total_bytes=204800 dropped=0   # 每 30s
```

警示訊號：
- `[RELAY] dropped=N`（N 持續成長）→ Client proxy 沒對齊 match
- `[WARN] LOBBY_SIGNING_KEY 格式錯誤` → 私鑰沒填或格式錯
- 沒有 `[RELAY] listening` → relay 起不來，檢查 port 衝突

---

## 10. 切回 Render 雲端

1. Client：`.env` 改回 `LOBBY_USE_LOCAL=false`
2. Client：`config/lobby_pubkey.txt` 還原為 Render 公鑰（建議事先備份）
3. 第三方主機可直接 Ctrl-C 停 uvicorn
