from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from typing import Dict
import random
import asyncio
import uuid
import os
import datetime
import aiosqlite

DB_PATH         = os.path.join(os.path.dirname(__file__), "leaderboard.db")
QUEUE_ROOM_ID   = "__queue__"
QUEUE_MIN       = 2
PUNCH_DURATION  = 2.0

rooms: Dict[str, dict] = {}
_db: aiosqlite.Connection | None = None


# ── DB 初始化 ──────────────────────────────────────────────────────────────

async def _init_db():
    global _db
    _db = await aiosqlite.connect(DB_PATH)
    await _db.executescript("""
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS matches (
            match_id   TEXT PRIMARY KEY,
            room_code  TEXT NOT NULL,
            started_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS match_results (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id     TEXT    NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
            nickname     TEXT    NOT NULL,
            char_type    INTEGER NOT NULL,
            result       TEXT    NOT NULL CHECK(result IN ('win', 'lose', 'draw')),
            submitted_at TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE(match_id, nickname)
        );
    """)
    await _db.commit()


# ── 週清 ───────────────────────────────────────────────────────────────────

def _secs_until_next_taiwan_sunday_4am() -> float:
    """計算距下一個台灣時間週日 04:00 的秒數。"""
    now_tw = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)
    days_ahead = (6 - now_tw.weekday()) % 7   # weekday() Sunday=6
    if days_ahead == 0 and now_tw.hour < 4:
        target = now_tw.replace(hour=4, minute=0, second=0, microsecond=0)
    else:
        if days_ahead == 0:
            days_ahead = 7
        target = (now_tw + datetime.timedelta(days=days_ahead)).replace(
            hour=4, minute=0, second=0, microsecond=0)
    return (target - now_tw).total_seconds()


async def _weekly_purge_loop():
    while True:
        await asyncio.sleep(_secs_until_next_taiwan_sunday_4am())
        if _db:
            await _db.execute("DELETE FROM matches")
            await _db.commit()
            print("🗑 Weekly leaderboard purge completed.")


# ── Lifespan ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await _init_db()
    asyncio.create_task(_weekly_purge_loop())
    yield
    if _db:
        await _db.close()


app = FastAPI(title="BattleLite Signaling Lobby", lifespan=lifespan)


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
    return {"id": p["id"], "name": p["name"],
            "char_type": p["char_type"], "ready": p["ready"]}

def _net(p: dict) -> dict:
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

@app.get("/leaderboard")
async def get_leaderboard(limit: int = 30):
    if not _db:
        raise HTTPException(503, "DB not ready")
    async with _db.execute(
        """SELECT nickname, games, wins, losses, draws, win_rate
           FROM (
               SELECT nickname,
                      COUNT(*) AS games,
                      SUM(CASE WHEN result='win'  THEN 1 ELSE 0 END) AS wins,
                      SUM(CASE WHEN result='lose' THEN 1 ELSE 0 END) AS losses,
                      SUM(CASE WHEN result='draw' THEN 1 ELSE 0 END) AS draws,
                      ROUND(100.0 * SUM(CASE WHEN result='win' THEN 1 ELSE 0 END) / COUNT(*), 1) AS win_rate
               FROM match_results
               GROUP BY nickname
               ORDER BY win_rate DESC, wins DESC
           ) LIMIT ?""",
        (limit,)
    ) as cur:
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in await cur.fetchall()]
    return {"entries": rows}


class ResultItem(BaseModel):
    match_id:  str
    room_code: str
    nickname:  str
    char_type: int
    result:    str

@app.post("/submit_result")
async def submit_result(item: ResultItem):
    if item.result not in ("win", "lose", "draw"):
        raise HTTPException(400, "result must be win / lose / draw")
    if not _db:
        raise HTTPException(503, "DB not ready")
    await _db.execute(
        "INSERT OR IGNORE INTO matches (match_id, room_code) VALUES (?, ?)",
        (item.match_id, item.room_code),
    )
    await _db.execute(
        """INSERT OR IGNORE INTO match_results (match_id, nickname, char_type, result)
           VALUES (?, ?, ?, ?)""",
        (item.match_id, item.nickname, item.char_type, item.result),
    )
    await _db.commit()
    return {"ok": True}


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
    room["started"]  = True
    match_id = str(uuid.uuid4())
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

    asyncio.create_task(
        _delayed_game_start(room_id, seed, players_info, host_id, match_id))


async def _delayed_game_start(
        room_id: str, seed: int, players_info: list, host_id: int, match_id: str):
    await asyncio.sleep(PUNCH_DURATION)
    if room_id not in rooms:
        return
    game_msg = {
        "type":     "game_start",
        "seed":     seed,
        "host_id":  host_id,
        "players":  players_info,
        "match_id": match_id,
    }
    print(f"🎮 game_start room={room_id} match={match_id}")
    for p in rooms.get(room_id, {}).get("players", []):
        try:
            await p["websocket"].send_json(game_msg)
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
