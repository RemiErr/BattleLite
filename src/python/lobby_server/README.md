伺服器支援比賽結果紀錄功能，若想使用請在伺服器環境變數中設定以下參數：
```bash
# Google Sheets Webhook URL，留空則不推送
SHEETS_WEBHOOK_URL=
```

Lobby Server Ed25519 簽章私鑰（僅伺服器端需要設定，hex 格式 64 字元）
```bash
LOBBY_SIGNING_KEY=
```
公私鑰產生方式：
```bash
# 產生私鑰（填入 LOBBY_SIGNING_KEY）
python -c "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; k=Ed25519PrivateKey.generate(); print('私鑰:', k.private_bytes_raw().hex()); print('公鑰:', k.public_key().public_bytes_raw().hex())"
```
產生後公鑰（hex）用來分發給玩家，設定檔在遊戲目錄的 `config/lobby_pubkey.txt`，私鑰填入伺服器 `.env` 的 `LOBBY_SIGNING_KEY`。