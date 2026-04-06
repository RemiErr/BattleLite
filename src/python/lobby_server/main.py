from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, List
import json

app = FastAPI(title="BattleLite Signaling Lobby")

# 資料結構：{ room_id: [ {name, ip, websocket}, ... ] }
rooms: Dict[str, List[dict]] = {}

@app.get("/")
async def root():
    return {"status": "BattleLite Lobby is Running"}

@app.websocket("/ws/{room_id}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_name: str):
    await websocket.accept()
    
    # 獲取玩家 IP (在 Production 環境中，需考慮 X-Forwarded-For)
    client_ip = websocket.client.host
    
    # 建立玩家物件
    new_player = {
        "name": player_name,
        "ip": client_ip,
        "websocket": websocket
    }
    
    # 加入房間
    if room_id not in rooms:
        rooms[room_id] = []
    rooms[room_id].append(new_player)
    
    print(f"➕ Player {player_name} joined room {room_id} ({client_ip})")
    
    try:
        # 當有人加入，通知房內所有人
        await broadcast_room_update(room_id)
        
        # 維持連線
        while True:
            # 這裡可以處理聊天或準備狀態，目前僅維持心跳
            data = await websocket.receive_text()
            
    except WebSocketDisconnect:
        # 移除玩家
        rooms[room_id] = [p for p in rooms[room_id] if p["websocket"] != websocket]
        if not rooms[room_id]:
            del rooms[room_id]
        
        print(f"➖ Player {player_name} left room {room_id}")
        await broadcast_room_update(room_id)

async def broadcast_room_update(room_id: str):
    """將目前的房間清單廣播給該房間內的所有人"""
    if room_id not in rooms:
        return
        
    players_data = [
        {"name": p["name"], "ip": p["ip"]} 
        for p in rooms[room_id]
    ]
    
    message = {
        "type": "room_update",
        "players": players_data
    }
    
    # 執行廣播
    for p in rooms[room_id]:
        try:
            await p["websocket"].send_json(message)
        except:
            # 忽略發送失敗的客戶端
            pass
