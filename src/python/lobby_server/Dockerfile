FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 只複製 main.py
COPY main.py .

ENV PORT=8000

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
