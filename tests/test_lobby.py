import pytest
from fastapi.testclient import TestClient
import sys
import os
import asyncio
import aiosqlite

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
        # 新協議：第一則是 join_ack，第二則是 room_update
        ack = ws_a.receive_json()
        assert ack["type"] == "join_ack"
        assert ack["player_id"] == 0
        assert ack["is_host"] is True

        room_update = ws_a.receive_json()
        assert room_update["type"] == "room_update"
        assert len(room_update["players"]) == 1

        # 2. 玩家 B 加入同一個房間
        with client.websocket_connect("/ws/battle_123/PlayerB") as ws_b:
            # PlayerB 收到 join_ack + room_update，跳過
            ws_b.receive_json()
            ws_b.receive_json()

            # 3. 玩家 A 收到 PlayerB 加入的 room_update 廣播
            data = ws_a.receive_json()
            assert data["type"] == "room_update"
            assert len(data["players"]) == 2
            assert data["players"][1]["name"] == "PlayerB"


def test_leaderboard_counts_ranked_matches_only():
    """
    驗證排行榜與段位只統計牌位賽，不會把自訂房間結果算進去。
    """
    from src.python.lobby_server import main as lobby

    async def _run():
        old_db = lobby._db
        db = await aiosqlite.connect(":memory:")
        lobby._db = db
        try:
            await db.executescript("""
                CREATE TABLE matches (
                    match_id   TEXT PRIMARY KEY,
                    room_code  TEXT NOT NULL
                );

                CREATE TABLE match_results (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id  TEXT NOT NULL,
                    nickname  TEXT NOT NULL,
                    char_type INTEGER NOT NULL,
                    result    TEXT NOT NULL
                );
            """)
            await db.executemany(
                "INSERT INTO matches (match_id, room_code) VALUES (?, ?)",
                [
                    ("ranked-1", "__queue_gold__"),
                    ("custom-1", "ABC123"),
                ],
            )
            await db.executemany(
                """INSERT INTO match_results
                   (match_id, nickname, char_type, result)
                   VALUES (?, ?, ?, ?)""",
                [
                    ("ranked-1", "RankedPlayer", 0, "win"),
                    ("custom-1", "RankedPlayer", 0, "lose"),
                    ("custom-1", "CustomOnly", 1, "win"),
                ],
            )
            await db.commit()

            leaderboard = await lobby.get_leaderboard()
            assert leaderboard["entries"] == [{
                "nickname": "RankedPlayer",
                "games": 1,
                "wins": 1,
                "losses": 0,
                "draws": 0,
                "win_rate": 100.0,
                "tier": "placement",
            }]

            ranked_tier = await lobby.get_player_tier("RankedPlayer")
            assert ranked_tier["games"] == 1
            assert ranked_tier["win_rate"] == 100.0

            custom_tier = await lobby.get_player_tier("CustomOnly")
            assert custom_tier["games"] == 0
            assert custom_tier["win_rate"] == 0.0
        finally:
            await db.close()
            lobby._db = old_db

    asyncio.run(_run())
