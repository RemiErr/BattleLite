from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, List
import json
import random

app = FastAPI(title="BattleLite Signaling Lobby")

# 資料結構：{ room_id: [ {name, ip, port, id, websocket}, ... ] }
rooms: Dict[str, List[dict]] = {}

@app.get("/")
async def root():
    return {"status": "BattleLite Lobby is Running"}

@app.websocket("/ws/{room_id}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_name: str):
    await websocket.accept()
    
    # 建立玩家物件 (初始資料)
    new_player = {
        "name": player_name,
        "ip": websocket.client.host,
        "port": 0, # 等待客戶端透過第一個訊息回報 STUN 埠號
        "id": 0,
        "websocket": websocket
    }
    
    if room_id not in rooms:
        rooms[room_id] = []
    
    # 分配 ID (根據目前房內人數)
    new_player["id"] = len(rooms[room_id])
    rooms[room_id].append(new_player)
    
    print(f"➕ Player {player_name} (ID:{new_player['id']}) joined room {room_id}")
    
    try:
        # 當有人加入，先發送一次房間更新 (通知有人來了)
        await broadcast_room_update(room_id)
        
        # 進入訊息監聽迴圈
        while True:
            data = await websocket.receive_json()
            
            # 處理客戶端回報的公網 Endpoint (STUN 結果)
            if data.get("type") == "report_endpoint":
                for p in rooms[room_id]:
                    if p["websocket"] == websocket:
                        p["ip"] = data["ip"]
                        p["port"] = data["port"]
                        print(f"📍 Player {player_name} reported endpoint: {p['ip']}:{p['port']}")

                # 必須等所有玩家都回報了有效 port 才觸發，避免帶 port=0 的錯誤地址出發
                all_reported = len(rooms[room_id]) >= 2 and all(p["port"] != 0 for p in rooms[room_id])
                already_started = rooms[room_id][0].get("match_started", False)
                if all_reported and not already_started:
                    for p in rooms[room_id]:
                        p["match_started"] = True
                    await trigger_match_start(room_id)
            
    except WebSocketDisconnect:
        rooms[room_id] = [p for p in rooms[room_id] if p["websocket"] != websocket]
        if not rooms[room_id]:
            del rooms[room_id]
        print(f"➖ Player {player_name} left room {room_id}")
        await broadcast_room_update(room_id)

async def broadcast_room_update(room_id: str):
    if room_id not in rooms: return
    players_data = [{"name": p["name"], "id": p["id"]} for p in rooms[room_id]]
    message = {"type": "room_update", "players": players_data}
    for p in rooms[room_id]:
        await p["websocket"].send_json(message)

async def trigger_match_start(room_id: str):
    """當房間滿 2 人，發送開始對戰訊號。"""
    players = rooms[room_id]
    seed = random.randint(1, 1000000)
    
    # 構造對戰資料 (包含所有人的公網地址)
    match_info = {
        "type": "start_match",
        "seed": seed,
        "players": [
            {"id": p["id"], "name": p["name"], "ip": p["ip"], "port": p["port"]} 
            for p in players
        ]
    }
    
    print(f"🎮 Starting match in room {room_id} with seed {seed}")
    for p in players:
        await p["websocket"].send_json(match_info)

if __name__ == "__main__":
    import uvicorn
    import os
    # 支援 Render/Railway 等雲端平台的 PORT 環境變數
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
