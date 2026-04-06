import pytest
from fastapi.testclient import TestClient
import sys
import os

# 確保路徑正確以匯入 lobby_server
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def test_websocket_lobby_connection():
    """
    驗證是否能成功連上 WebSocket 大廳。
    """
    try:
        from src.python.lobby_server.main import app
    except ImportError:
        pytest.fail("找不到 lobby_server 模組。")

    client = TestClient(app)
    # 測試連線
    with client.websocket_connect("/ws/test_room/player1") as websocket:
        # 預期連線成功且不報錯
        assert websocket is not None

def test_room_broadcasting():
    """
    驗證當玩家 B 加入時，玩家 A 是否能收到廣播訊息。
    這是配對系統的核心：交換對手資訊。
    """
    from src.python.lobby_server.main import app
    client = TestClient(app)

    # 1. 玩家 A 加入房間 'battle_123'
    with client.websocket_connect("/ws/battle_123/PlayerA") as ws_a:
        # 2. 玩家 B 加入同一個房間
        with client.websocket_connect("/ws/battle_123/PlayerB") as ws_b:
            # 3. 玩家 A 應該收到一則廣播，通知 PlayerB 已加入
            data = ws_a.receive_json()
            assert data["type"] == "room_update"
            assert len(data["players"]) == 2
            assert data["players"][1]["name"] == "PlayerB"
