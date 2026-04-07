import pytest
import asyncio
import sys
import os

# 確保路徑正確
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def test_lobby_client_logic():
    """
    驗證 Launcher 的連線客戶端邏輯。
    """
    try:
        from src.python.lobby_client import LobbyClient
    except ImportError:
        pytest.fail("找不到 'src.python.lobby_client' 模組。")

    # 這裡我們定義 LobbyClient 的基本接口
    client = LobbyClient(server_url="ws://localhost:8000")
    assert hasattr(client, 'join_room'), "應具備 join_room 方法"
    assert hasattr(client, 'listen'), "應具備 listen 方法"
