import asyncio
import websockets
import json

class LobbyClient:
    """
    Launcher 的大廳通訊客戶端。
    負責連線至信令伺服器並處理配對訊息。
    """
    def __init__(self, server_url):
        self.server_url = server_url
        self.websocket = None

    async def join_room(self, room_id, player_name):
        """建立連線並加入指定房間。"""
        # 格式符合 FastAPI 端定義的 /ws/{room_id}/{player_name}
        uri = f"{self.server_url}/ws/{room_id}/{player_name}"
        try:
            self.websocket = await websockets.connect(uri)
            print(f"📡 Connected to lobby: {room_id}")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    async def send_data(self, data: dict):
        """發送 JSON 資料至大廳。"""
        if self.websocket:
            await self.websocket.send(json.dumps(data))

    async def listen(self):
        """
        非同步監聽伺服器訊息。
        這是一個生成器，可以用 async for 調用。
        """
        if not self.websocket:
            return

        try:
            async for message in self.websocket:
                yield json.loads(message)
        except websockets.exceptions.ConnectionClosed:
            print("🔌 Connection closed by server.")
        except Exception as e:
            print(f"⚠️ Lobby listener error: {e}")

    async def close(self):
        """關閉連線。"""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
