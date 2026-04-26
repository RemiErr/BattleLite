from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict
import random
import asyncio

app = FastAPI(title="BattleLite Signaling Lobby")

QUEUE_ROOM_ID   = "__queue__"
QUEUE_MIN       = 2       # 排隊最少人數
PUNCH_DURATION  = 2.0     # 打洞等待秒數

# rooms[room_id] = { "players": [...], "started": bool, "is_queue": bool }
rooms: Dict[str, dict] = {}


# ── 玩家資料工廠 ──────────────────────────────────────────────────────────

def _make_player(name: str, ws: WebSocket, pid: int, pub_ip: str) -> dict:
    return {
        "id": pid, "name": name,
        "pub_ip": pub_ip, "pub_port": 0,
        "local_ip": "unknown", "local_port": 0,
        "char_type": 0, "ready": False,
        "websocket": ws,
    }

def _pub(p: dict) -> dict:
    """給 room_update 廣播用（不含 websocket）。"""
    return {"id": p["id"], "name": p["name"],
            "char_type": p["char_type"], "ready": p["ready"]}

def _net(p: dict) -> dict:
    """給 punch_start / game_start 用（含網路位址）。"""
    return {"id": p["id"], "name": p["name"], "char_type": p["char_type"],
            "pub_ip": p["pub_ip"], "pub_port": p["pub_port"],
            "local_ip": p["local_ip"], "local_port": p["local_port"]}


# ── REST ──────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "BattleLite Lobby is Running"}

@app.get("/online")
async def online_count():
    return {"count": sum(len(r["players"]) for r in rooms.values())}


# ── WebSocket ─────────────────────────────────────────────────────────────

@app.websocket("/ws/{room_id}/{player_name}")
async def ws_endpoint(websocket: WebSocket, room_id: str, player_name: str):
    await websocket.accept()
    is_queue = (room_id == QUEUE_ROOM_ID)

    if room_id not in rooms:
        rooms[room_id] = {"players": [], "started": False, "is_queue": is_queue}
    room = rooms[room_id]

    pid    = len(room["players"])
    pub_ip = websocket.client.host if websocket.client else "unknown"
    player = _make_player(player_name, websocket, pid, pub_ip)
    room["players"].append(player)
    print(f"➕ {player_name}(id={pid}) → {'queue' if is_queue else room_id}")

    # 通知新玩家自己的 id 與是否為房主
    is_host = (pid == 0 and not is_queue)
    await websocket.send_json({
        "type": "join_ack",
        "player_id": pid,
        "is_host": is_host,
        "room_id": room_id,
    })
    await _broadcast_room_update(room_id)

    try:
        while True:
            data = await websocket.receive_json()
            t = data.get("type")

            if t == "report_endpoint":
                player["pub_ip"]    = data["pub_ip"]
                player["pub_port"]  = data["pub_port"]
                player["local_ip"]  = data["local_ip"]
                player["local_port"]= data["local_port"]
                print(f"📍 {player_name} pub={player['pub_ip']}:{player['pub_port']}")

            elif t == "char_select":
                player["char_type"] = int(data.get("char_type", 0))
                await _broadcast_room_update(room_id)

            elif t == "player_ready":
                player["ready"] = True
                await _broadcast_room_update(room_id)
                if is_queue:
                    await _try_queue_start(room_id)

            elif t == "start_game":
                # 只有一般房間的房主（pid=0）可以觸發
                if not is_queue and pid == 0:
                    ps = room["players"]
                    if (len(ps) >= 2
                            and all(p["ready"]    for p in ps)
                            and all(p["pub_port"] != 0 for p in ps)):
                        await _initiate_match(room_id, host_id=0)

    except WebSocketDisconnect:
        room["players"] = [p for p in room["players"] if p["websocket"] != websocket]
        print(f"➖ {player_name} left {room_id}")
        if not room["players"]:
            del rooms[room_id]
        elif room_id in rooms:
            await _broadcast_room_update(room_id)


# ── 廣播 & 媒合 ───────────────────────────────────────────────────────────

async def _broadcast_room_update(room_id: str):
    if room_id not in rooms:
        return
    room = rooms[room_id]
    host_id = 0 if not room["is_queue"] else -1
    msg = {"type": "room_update", "host_id": host_id,
           "players": [_pub(p) for p in room["players"]]}
    for p in room["players"]:
        try:
            await p["websocket"].send_json(msg)
        except Exception:
            pass


async def _try_queue_start(room_id: str):
    """排隊房：所有人 ready 且都有 endpoint → 隨機選房主並開始。"""
    room = rooms.get(room_id)
    if not room or room.get("started"):
        return
    ps = room["players"]
    if (len(ps) >= QUEUE_MIN
            and all(p["ready"]    for p in ps)
            and all(p["pub_port"] != 0 for p in ps)):
        host_id = random.choice([p["id"] for p in ps])
        await _initiate_match(room_id, host_id=host_id)


async def _initiate_match(room_id: str, host_id: int):
    room = rooms[room_id]
    if room.get("started"):
        return
    room["started"] = True
    seed = random.randint(1, 1_000_000)
    players_info = [_net(p) for p in room["players"]]

    punch_msg = {"type": "punch_start", "seed": seed,
                 "host_id": host_id, "players": players_info}
    print(f"👊 punch_start room={room_id} seed={seed} host={host_id}")
    for p in room["players"]:
        try:
            await p["websocket"].send_json(punch_msg)
        except Exception:
            pass

    asyncio.create_task(_delayed_game_start(room_id, seed, players_info, host_id))


async def _delayed_game_start(room_id: str, seed: int, players_info: list, host_id: int):
    await asyncio.sleep(PUNCH_DURATION)
    if room_id not in rooms:
        return
    game_msg = {"type": "game_start", "seed": seed,
                "host_id": host_id, "players": players_info}
    print(f"🎮 game_start room={room_id}")
    for p in rooms.get(room_id, {}).get("players", []):
        try:
            await p["websocket"].send_json(game_msg)
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
