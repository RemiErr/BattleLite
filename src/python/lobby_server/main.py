from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, List
import json
import random
import asyncio

app = FastAPI(title="BattleLite Signaling Lobby")

# { room_id: [ {name, ip, port, id, websocket, match_started}, ... ] }
rooms: Dict[str, List[dict]] = {}

PUNCH_DURATION = 2.0  # 秒，Lobby 等雙方打洞的時間


@app.get("/")
async def root():
    return {"status": "BattleLite Lobby is Running"}


@app.websocket("/ws/{room_id}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_name: str):
    await websocket.accept()

    new_player = {
        "name": player_name,
        "pub_ip": websocket.client.host if websocket.client else "unknown",
        "pub_port": 0,
        "local_ip": "unknown",
        "local_port": 0,
        "id": 0,
        "match_started": False,
        "websocket": websocket
    }

    if room_id not in rooms:
        rooms[room_id] = []

    new_player["id"] = len(rooms[room_id])
    rooms[room_id].append(new_player)
    print(f"➕ Player {player_name} (ID:{new_player['id']}) joined room {room_id}")

    try:
        await broadcast_room_update(room_id)

        while True:
            data = await websocket.receive_json()

            if data.get("type") == "report_endpoint":
                for p in rooms[room_id]:
                    if p["websocket"] == websocket:
                        p["pub_ip"]    = data["pub_ip"]
                        p["pub_port"]  = data["pub_port"]
                        p["local_ip"]  = data["local_ip"]
                        p["local_port"]= data["local_port"]
                        print(f"📍 {player_name}  pub={p['pub_ip']}:{p['pub_port']}  lan={p['local_ip']}:{p['local_port']}")

                # 所有玩家都回報有效 port 且尚未啟動 → 進入打洞流程
                all_reported = (
                    len(rooms[room_id]) >= 2 and
                    all(p["pub_port"] != 0 for p in rooms[room_id])
                )
                already_started = rooms[room_id][0].get("match_started", False)
                if all_reported and not already_started:
                    for p in rooms[room_id]:
                        p["match_started"] = True
                    await trigger_punch_start(room_id)

    except WebSocketDisconnect:
        rooms[room_id] = [p for p in rooms[room_id] if p["websocket"] != websocket]
        if not rooms[room_id]:
            del rooms[room_id]
        print(f"➖ Player {player_name} left room {room_id}")
        await broadcast_room_update(room_id)


async def broadcast_room_update(room_id: str):
    if room_id not in rooms:
        return
    players_data = [{"name": p["name"], "id": p["id"]} for p in rooms[room_id]]
    message = {"type": "room_update", "players": players_data}
    for p in rooms[room_id]:
        await p["websocket"].send_json(message)


async def trigger_punch_start(room_id: str):
    """同時通知所有玩家開始打洞，2 秒後發送 game_start。"""
    players = rooms[room_id]
    seed = random.randint(1, 1_000_000)

    players_info = [
        {
            "id": p["id"], "name": p["name"],
            "pub_ip": p["pub_ip"], "pub_port": p["pub_port"],
            "local_ip": p["local_ip"], "local_port": p["local_port"],
        }
        for p in players
    ]

    punch_msg = {"type": "punch_start", "seed": seed, "players": players_info}
    print(f"👊 punch_start  room={room_id}  seed={seed}")
    for p in players:
        await p["websocket"].send_json(punch_msg)

    # 方案三：固定等待 PUNCH_DURATION 秒後發 game_start
    asyncio.create_task(_delayed_game_start(room_id, seed, players_info))


async def _delayed_game_start(room_id: str, seed: int, players_info: list):
    await asyncio.sleep(PUNCH_DURATION)

    if room_id not in rooms:
        return

    game_msg = {"type": "game_start", "seed": seed, "players": players_info}
    print(f"🎮 game_start  room={room_id}")
    for p in rooms.get(room_id, []):
        try:
            await p["websocket"].send_json(game_msg)
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    port = int(__import__("os").environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
