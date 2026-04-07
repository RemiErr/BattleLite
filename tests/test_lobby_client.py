import pytest
import asyncio
from src.python.lobby_server.main import app
from fastapi.testclient import TestClient
import sys
import os

def test_launcher_lobby_flow():
    """
    模擬 Launcher 的大廳通訊流程。
    """
    from src.python.lobby_server.main import app
    client = TestClient(app)

    # 模擬玩家連線到大廳
    with client.websocket_connect("/ws/room_999/AlphaPlayer") as ws:
        # 1. 應收到初始房間狀態
        data = ws.receive_json()
        assert data["type"] == "room_update"
        assert len(data["players"]) == 1
        assert data["players"][0]["name"] == "AlphaPlayer"
        
        # 此測試目前僅驗證連線與初始接收，後續會整合真實 Client
