# 使用輕量級 Python 映像檔
FROM python:3.12-slim

# 設定工作目錄
WORKDIR /app

# 複製依賴清單
COPY requirements.txt .

# 安裝依賴 (包含 uvicorn[standard])
RUN pip install --no-cache-dir -r requirements.txt

# 複製伺服器原始碼
# 注意：這裡我們只複製大廳相關的代碼以保持映像檔精簡
COPY src/python/lobby_server/ /app/lobby_server/

# 設定環境變數預設值
ENV PORT=8000

# 啟動指令：使用 uvicorn 執行，並讀取環境變數 PORT
# 綁定 0.0.0.0 是雲端部署的必要條件
CMD uvicorn lobby_server.main:app --host 0.0.0.0 --port ${PORT}
