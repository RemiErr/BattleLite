import websockets
import json


class LobbyClient:
    """Launcher 的大廳 WebSocket 客戶端。"""

    def __init__(self, server_url: str):
        self.server_url = server_url
        self.websocket = None

    async def join_room(self, room_id: str, player_name: str) -> bool:
        uri = f"{self.server_url}/ws/{room_id}/{player_name}"
        try:
            self.websocket = await websockets.connect(uri)
            print(f"[Lobby] Connected: room={room_id}")
            return True
        except Exception as e:
            print(f"[ERR] Connection failed: {e}")
            return False

    async def send_data(self, data: dict):
        if self.websocket:
            await self.websocket.send(json.dumps(data))

    async def send_char_select(self, char_type: int):
        await self.send_data({"type": "char_select", "char_type": char_type})

    async def send_ready(self):
        await self.send_data({"type": "player_ready"})

    async def send_start_game(self, ai_count: int = 0):
        await self.send_data({"type": "start_game", "ai_count": ai_count})

    async def listen(self):
        if not self.websocket:
            return
        try:
            async for message in self.websocket:
                yield json.loads(message)
        except websockets.exceptions.ConnectionClosed:
            print("[Lobby] Connection closed.")
        except Exception as e:
            print(f"[WARN] Lobby error: {e}")

    async def close(self):
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
