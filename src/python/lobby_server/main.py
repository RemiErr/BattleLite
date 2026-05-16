from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel, Field
from typing import Dict
import re
import random
import asyncio
import uuid
import os
import json
import base64
import datetime
import time
import aiosqlite
import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

DB_PATH = os.path.join(os.path.dirname(__file__), "leaderboard.db")
SHEETS_WEBHOOK_URL = os.environ.get("SHEETS_WEBHOOK_URL", "")
QUEUE_MIN = 2  # TODO: for testing, default is 4
PUNCH_DURATION = 2.0

# Ed25519 簽章金鑰（私鑰 seed，32 bytes hex，64 chars）。不設定則 sig 為空字串。
_signing_key: Ed25519PrivateKey | None = None
_signing_key_hex = os.environ.get("LOBBY_SIGNING_KEY", "")
if _signing_key_hex:
    try:
        _signing_key = Ed25519PrivateKey.from_private_bytes(
            bytes.fromhex(_signing_key_hex))
    except Exception as e:
        print(f"[WARN] LOBBY_SIGNING_KEY 格式錯誤，簽章停用: {e}")


def _sign_session(match_id: str, seed: int, host_id: int) -> str:
    """以伺服器私鑰簽署核心 session 欄位，回傳 base64url（無 padding）。"""
    if _signing_key is None:
        return ""
    canonical = json.dumps(
        {"host_id": host_id, "match_id": match_id, "seed": seed},
        sort_keys=True, separators=(',', ':'),
    )
    sig = _signing_key.sign(canonical.encode())
    return base64.urlsafe_b64encode(sig).rstrip(b'=').decode()


TIER_THRESHOLDS = {"games": 5, "silver_min": 40.0, "gold_min": 60.0}
RANKED_ROOM_PATTERN = r"\_\_queue\_%\_\_"


def _is_queue_room(room_id: str) -> bool:
    return room_id.startswith("__queue_") and room_id.endswith("__")


def _calc_tier(games: int, win_rate: float) -> str:
    if games < TIER_THRESHOLDS["games"]:
        return "placement"
    if win_rate < TIER_THRESHOLDS["silver_min"]:
        return "bronze"
    if win_rate <= TIER_THRESHOLDS["gold_min"]:
        return "silver"
    return "gold"


rooms: Dict[str, dict] = {}
_db: aiosqlite.Connection | None = None


# ── DB 初始化 ──────────────────────────────────────────────────────────────

async def _init_db():
    global _db
    _db = await aiosqlite.connect(DB_PATH)
    await _db.executescript("""
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS matches (
            match_id      TEXT    PRIMARY KEY,
            room_code     TEXT    NOT NULL,
            num_players   INTEGER NOT NULL DEFAULT 2,
            sheets_posted INTEGER NOT NULL DEFAULT 0,
            started_at    TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS match_results (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id     TEXT    NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
            player_id    INTEGER NOT NULL DEFAULT 0,
            nickname     TEXT    NOT NULL,
            char_type    INTEGER NOT NULL,
            result       TEXT    NOT NULL CHECK(result IN ('win', 'lose', 'draw')),
            submitted_at TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE(match_id, player_id)
        );
    """)
    await _db.commit()


# ── DB 欄位升級（舊 DB 補欄位，CREATE IF NOT EXISTS 不會自動加）─────────────

async def _migrate_db():
    for stmt in [
        "ALTER TABLE matches ADD COLUMN num_players   INTEGER NOT NULL DEFAULT 2",
        "ALTER TABLE matches ADD COLUMN sheets_posted INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE match_results ADD COLUMN player_id INTEGER NOT NULL DEFAULT 0",
    ]:
        try:
            await _db.execute(stmt)
        except aiosqlite.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise
    await _db.commit()


# ── 週清 ───────────────────────────────────────────────────────────────────

def _secs_until_next_taiwan_sunday_4am() -> float:
    """計算距下一個台灣時間週日 04:00 的秒數。"""
    now_tw = datetime.datetime.now(
        datetime.timezone.utc) + datetime.timedelta(hours=8)
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
    await _migrate_db()
    asyncio.create_task(_weekly_purge_loop())
    asyncio.create_task(_idle_room_sweep())
    yield
    if _db:
        await _db.close()


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="BattleLite Signaling Lobby", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


_ws_connections: dict[str, int] = {}
_MAX_WS_PER_IP = 4   # 同一 IP 最多 4 條；localhost 豁免


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
@limiter.limit("60/minute")
async def online_count(request: Request):
    return {"count": sum(len(r["players"]) for r in rooms.values())}


@app.get("/leaderboard")
@limiter.limit("60/minute")
async def get_leaderboard(request: Request, limit: int = 30):
    if not _db:
        raise HTTPException(503, "DB not ready")
    t = TIER_THRESHOLDS
    async with _db.execute(
        f"""SELECT nickname, games, wins, losses, draws, win_rate,
                  CASE
                      WHEN games < {t['games']}             THEN 'placement'
                      WHEN win_rate < {t['silver_min']}     THEN 'bronze'
                      WHEN win_rate <= {t['gold_min']}      THEN 'silver'
                      ELSE                                       'gold'
                  END AS tier
           FROM (
               SELECT nickname,
                      COUNT(*) AS games,
                      SUM(CASE WHEN result='win'  THEN 1 ELSE 0 END) AS wins,
                      SUM(CASE WHEN result='lose' THEN 1 ELSE 0 END) AS losses,
                      SUM(CASE WHEN result='draw' THEN 1 ELSE 0 END) AS draws,
                      ROUND(100.0 * SUM(CASE WHEN result='win' THEN 1 ELSE 0 END) / COUNT(*), 1) AS win_rate
               FROM match_results AS mr
               JOIN matches AS m ON m.match_id = mr.match_id
               WHERE m.room_code LIKE ? ESCAPE '\\'
               GROUP BY nickname
               ORDER BY win_rate DESC, wins DESC
           ) LIMIT ?""",
        (RANKED_ROOM_PATTERN, limit)
    ) as cur:
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in await cur.fetchall()]
    return {"entries": rows}


@app.get("/player_tier/{nickname}")
@limiter.limit("60/minute")
async def get_player_tier(request: Request, nickname: str):
    if not _db:
        raise HTTPException(503, "DB not ready")
    async with _db.execute(
        """SELECT COUNT(*) AS games,
                  ROUND(100.0 * SUM(CASE WHEN result='win' THEN 1 ELSE 0 END)
                        / NULLIF(COUNT(*), 0), 1) AS win_rate
           FROM match_results AS mr
           JOIN matches AS m ON m.match_id = mr.match_id
           WHERE mr.nickname = ?
             AND m.room_code LIKE ? ESCAPE '\\'""",
        (nickname, RANKED_ROOM_PATTERN)
    ) as cur:
        row = await cur.fetchone()
    games = row[0] or 0
    win_rate = row[1] or 0.0
    return {"tier": _calc_tier(games, win_rate), "games": games, "win_rate": win_rate}


class ResultItem(BaseModel):
    match_id:    str = Field(..., min_length=1, max_length=36)
    room_code:   str = Field(..., min_length=1, max_length=32)
    nickname:    str = Field(..., min_length=1, max_length=20)
    char_type:   int = Field(..., ge=0, le=4)
    result:      str
    player_id:   int = Field(0, ge=0, le=3)
    num_players: int = Field(2, ge=2, le=4)


@app.post("/submit_result")
@limiter.limit("20/hour")
async def submit_result(request: Request, item: ResultItem):
    if item.result not in ("win", "lose", "draw"):
        raise HTTPException(400, "result must be win / lose / draw")
    if not _db:
        raise HTTPException(503, "DB not ready")
    is_ranked = _is_queue_room(item.room_code)
    await _db.execute(
        "INSERT OR IGNORE INTO matches (match_id, room_code, num_players) VALUES (?, ?, ?)",
        (item.match_id, item.room_code, item.num_players),
    )
    await _db.execute(
        """INSERT OR IGNORE INTO match_results (match_id, player_id, nickname, char_type, result)
           VALUES (?, ?, ?, ?, ?)""",
        (item.match_id, item.player_id, item.nickname, item.char_type, item.result),
    )
    await _db.commit()
    asyncio.create_task(_maybe_push_to_sheets(item.match_id))
    return {"ok": True, "ranked": is_ranked}


# ── Google Sheets 推送 ────────────────────────────────────────────────────

async def _maybe_push_to_sheets(match_id: str) -> None:
    if not SHEETS_WEBHOOK_URL or not _db:
        return

    async with _db.execute(
        "SELECT num_players, sheets_posted, room_code FROM matches WHERE match_id = ?",
        (match_id,),
    ) as cur:
        row = await cur.fetchone()
    if not row or row[1]:  # 不存在或已推送
        return
    num_players, _, room_code = row

    async with _db.execute(
        "SELECT COUNT(*) FROM match_results WHERE match_id = ?",
        (match_id,),
    ) as cur:
        count = (await cur.fetchone())[0]
    if count < num_players:
        return  # 尚有玩家未提交

    async with _db.execute(
        """SELECT player_id, nickname, char_type, result
           FROM match_results WHERE match_id = ? ORDER BY player_id""",
        (match_id,),
    ) as cur:
        players = [
            {"player_id": r[0], "nickname": r[1],
                "char_type": r[2], "result": r[3]}
            for r in await cur.fetchall()
        ]

    winners = [p["nickname"] for p in players if p["result"] == "win"]
    winner_str = winners[0] if winners else "平手: " + \
        " / ".join(p["nickname"] for p in players)

    now_tw = datetime.datetime.now(
        datetime.timezone.utc) + datetime.timedelta(hours=8)
    payload = {
        "match_id":  match_id,
        "room_code": room_code,
        "room_type": "ranked" if _is_queue_room(room_code) else "custom",
        "timestamp": now_tw.strftime("%Y-%m-%d %H:%M:%S"),
        "players":   players,
        "winner":    winner_str,
    }

    # 先標記避免重複推送
    await _db.execute(
        "UPDATE matches SET sheets_posted = 1 WHERE match_id = ?", (match_id,))
    await _db.commit()

    asyncio.create_task(_post_to_sheets(payload))


async def _post_to_sheets(payload: dict) -> None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(SHEETS_WEBHOOK_URL, json=payload)
        print(
            f"[OK] Sheets pushed: {payload['match_id']} ({payload['room_type']})")
    except Exception as e:
        print(f"[WARN] Sheets push failed: {e}")


# ── WebSocket ─────────────────────────────────────────────────────────────

@app.websocket("/ws/{room_id}/{player_name}")
async def ws_endpoint(websocket: WebSocket, room_id: str, player_name: str):
    ip = websocket.client.host if websocket.client else "unknown"

    if ip not in ("127.0.0.1", "::1") and _ws_connections.get(ip, 0) >= _MAX_WS_PER_IP:
        await websocket.close(code=1008, reason="Too many connections")
        return
    if not player_name or len(player_name) > 20:
        await websocket.close(code=1008, reason="Invalid player name")
        return
    if not room_id or len(room_id) > 32 or not re.match(r'^[\w\-]+$', room_id):
        await websocket.close(code=1008, reason="Invalid room ID")
        return
    if room_id in rooms:
        _r = rooms[room_id]
        if _r.get("started"):
            await websocket.close(code=1008, reason="Game already started")
            return
        if len(_r["players"]) >= _r["target_size"]:
            await websocket.close(code=1008, reason="Room full")
            return

    _ws_connections[ip] = _ws_connections.get(ip, 0) + 1
    await websocket.accept()
    is_queue = _is_queue_room(room_id)

    if room_id not in rooms:
        target_size = QUEUE_MIN if is_queue else 2
        rooms[room_id] = {
            "players": [], "started": False,
            "is_queue": is_queue, "target_size": target_size,
            "last_activity": time.monotonic(),
            "ai_players": {},
        }
    room = rooms[room_id]

    if any(p["name"] == player_name for p in room["players"]):
        await websocket.send_json({"type": "error", "code": "name_taken"})
        _ws_connections[ip] = max(0, _ws_connections.get(ip, 0) - 1)
        if _ws_connections.get(ip) == 0:
            _ws_connections.pop(ip, None)
        return

    pid = len(room["players"])
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
            room["last_activity"] = time.monotonic()
            t = data.get("type")

            if t == "report_endpoint":
                player["pub_ip"] = data["pub_ip"]
                player["pub_port"] = data["pub_port"]
                player["local_ip"] = data["local_ip"]
                player["local_port"] = data["local_port"]
                print(
                    f"📍 {player_name} pub={player['pub_ip']}:{player['pub_port']}")

            elif t == "char_select":
                char_type = int(data.get("char_type", 0))
                if 0 <= char_type <= 4:
                    player["char_type"] = char_type
                await _broadcast_room_update(room_id)

            elif t == "set_room_size":
                if not is_queue and pid == 0:
                    room["target_size"] = max(
                        2, min(4, int(data.get("size", 2))))
                    await _broadcast_room_update(room_id)

            elif t == "player_ready":
                player["ready"] = True
                await _broadcast_room_update(room_id)
                if is_queue:
                    await _try_queue_start(room_id)

            elif t == "cancel_ready":
                if not is_queue and not room.get("started"):
                    player["ready"] = False
                    await _broadcast_room_update(room_id)

            elif t == "update_ai_players":
                if not is_queue and pid == 0:
                    raw_ai = data.get("ai_players", {})
                    ai_players: dict = {}
                    for k, v in raw_ai.items():
                        try:
                            ai_pid = int(k)
                            ct = int(v.get("char_type", 0))
                            lv = int(v.get("level", 1))
                            if 0 <= ai_pid <= 3 and 0 <= ct <= 4 and 1 <= lv <= 3:
                                ai_players[str(ai_pid)] = {
                                    "char_type": ct, "level": lv}
                        except (ValueError, AttributeError):
                            pass
                    room["ai_players"] = ai_players
                    await _broadcast_room_update(room_id)

            elif t == "start_game":
                if not is_queue and pid == 0:
                    ai_count = max(0, min(3, int(data.get("ai_count", 0))))
                    raw_ai = data.get("ai_players", {})
                    ai_players: dict = {}
                    for k, v in raw_ai.items():
                        try:
                            ai_pid = int(k)
                            ct = int(v.get("char_type", 0))
                            lv = int(v.get("level", 1))
                            if 0 <= ai_pid <= 3 and 0 <= ct <= 4 and 1 <= lv <= 3:
                                ai_players[str(ai_pid)] = {
                                    "char_type": ct, "level": lv}
                        except (ValueError, AttributeError):
                            pass
                    room["ai_players"] = ai_players
                    ps = room["players"]
                    if (len(ps) + ai_count >= room["target_size"]
                            and all(p["ready"] for p in ps)
                            and all(p["pub_port"] != 0 for p in ps)):
                        await _initiate_match(room_id, host_id=0)

    except WebSocketDisconnect:
        room["players"] = [p for p in room["players"]
                           if p["websocket"] != websocket]
        print(f"➖ {player_name} left {room_id}")
        if not room["players"]:
            del rooms[room_id]
        elif room_id in rooms:
            await _broadcast_room_update(room_id)
    finally:
        _ws_connections[ip] = max(0, _ws_connections.get(ip, 0) - 1)
        if _ws_connections.get(ip) == 0:
            _ws_connections.pop(ip, None)


# ── 廣播 & 媒合 ───────────────────────────────────────────────────────────

async def _broadcast_room_update(room_id: str):
    if room_id not in rooms:
        return
    room = rooms[room_id]
    host_id = 0 if not room.get("is_queue") else -1
    msg = {"type": "room_update", "host_id": host_id,
           "target_size": room.get("target_size", 2),
           "players": [_pub(p) for p in room["players"]],
           "ai_players": room.get("ai_players", {})}
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
    if (len(ps) >= room["target_size"]
            and all(p["ready"] for p in ps)
            and all(p["pub_port"] != 0 for p in ps)):
        host_id = random.choice([p["id"] for p in ps])
        await _initiate_match(room_id, host_id=host_id)


async def _initiate_match(room_id: str, host_id: int):
    room = rooms[room_id]
    if room.get("started"):
        return
    room["started"] = True
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
        "type":      "game_start",
        "seed":      seed,
        "host_id":   host_id,
        "players":   players_info,
        "match_id":  match_id,
        "ai_players": rooms.get(room_id, {}).get("ai_players", {}),
        "sig":        _sign_session(match_id, seed, host_id),
    }
    print(f"🎮 game_start room={room_id} match={match_id}")
    for p in rooms.get(room_id, {}).get("players", []):
        try:
            await p["websocket"].send_json(game_msg)
        except Exception:
            pass

    asyncio.create_task(_room_ttl_cleanup(room_id))


_ROOM_TTL_SECS = 3600  # 遊戲開始後最長保留 1 小時
_IDLE_TIMEOUT_SECS = 300   # 等待房間閒置超過 5 分鐘即關閉連線
_SWEEP_INTERVAL_SECS = 60    # 每 60 秒掃描一次閒置房間


async def _room_ttl_cleanup(room_id: str) -> None:
    """遊戲開始後若房間殘留超過 TTL，自動清除以防記憶體洩漏。"""
    await asyncio.sleep(_ROOM_TTL_SECS)
    if room_id in rooms and rooms[room_id].get("started"):
        del rooms[room_id]
        print(f"🧹 TTL 清理房間 {room_id}")


async def _idle_room_sweep() -> None:
    """定期掃描閒置等待房間，關閉其 WebSocket 連線以觸發正常斷線清理。"""
    while True:
        await asyncio.sleep(_SWEEP_INTERVAL_SECS)
        now = time.monotonic()
        stale = [
            rid for rid, room in list(rooms.items())
            if not room.get("started")
            and now - room.get("last_activity", now) > _IDLE_TIMEOUT_SECS
        ]
        for rid in stale:
            room = rooms.get(rid)
            if not room:
                continue
            print(f"閒置清理房間 {rid} ({len(room['players'])} 玩家)")
            for p in list(room["players"]):
                try:
                    await asyncio.wait_for(
                        p["websocket"].close(code=1001, reason="Idle timeout"),
                        timeout=5.0,
                    )
                except Exception:
                    pass


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
