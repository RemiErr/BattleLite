# BattleLite

BattleLite 是一款致敬《小朋友齊打交》(LF2) 的 2D 橫向捲軸混戰遊戲。採用 **Python (Pygame)** 進行渲染，並使用 **Rust (GGRS)** 實作 P2P 回滾式網路代碼 (Rollback Netcode)。

## 🛠️ 環境需求 (Ubuntu/WSL2)

在編譯前，請確保系統已安裝必要的開發工具：

```bash
# 1. 安裝編譯工具與 Python 開發庫
sudo apt update && sudo apt install build-essential python3-dev python3-venv

# 2. 安裝 Rust 官方工具鏈
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
```

## 🏗️ 快速啟動 (Build & Setup)

1. **建立虛擬環境**:
   ```bash
   python3 -m venv venv --without-pip
   source venv/bin/activate
   curl https://bootstrap.pypa.io/get-pip.py | python3
   pip install maturin pygame pytest
   ```

2. **編譯 Rust 核心**:
   ```bash
   cd src/rust_core
   maturin develop
   ```

## 🧪 開發流程 (TDD)

本專案遵循 **Red → Green → Refactor** 開發循環：
- 所有的功能實作必須先從 `tests/` 下的一個失敗測試開始。
- 只有在測試通過後，才能進行代碼重構。
- 所有的測試結果必須保留並記錄。

## 📜 專案文件
- `DEVELOPMENT_STANDARDS.md`: 技術規範、架構定義與 TDD 流程。
- `GEMINI.md`: AI 助手的操作指令與溝通規範。
- `DEV_LOG.md`: 開發日誌與決策紀錄。
