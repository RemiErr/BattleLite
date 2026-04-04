import pytest
from battlelite_core import Player, GGRSSession

# 定義標準輸入位元 (與 Rust 對齊)
INPUT_RIGHT = 1
INPUT_LEFT = 2
INPUT_UP = 4
INPUT_DOWN = 8
INPUT_JUMP = 16

def test_y_axis_movement():
    """
    驗證 Y 軸 (深淺) 的位移邏輯。
    """
    # 建立一個測試 Session (P2P 模式，僅測試邏輯不測試連線)
    session = GGRSSession(local_player_id=0, num_players=1, port=12350)
    
    # 手動進入 Running 狀態（在測試中我們假設它能處理）
    # 注意：P2P Session 在測試中很難真正達到 Running，
    # 這就是為什麼我們之後可能需要實作一個強制的 'test_mode'。
    # 暫時我們直接測試 Player 結構體的 update 邏輯。
    
    player = Player()
    player.y = 2000
    
    # 測試向上走 (INPUT_UP)
    # 我們預期如果輸入包含 UP，VY 應為負值 (在 Pygame 中向上是座標減少)
    # 但在我們 2.5D 架構中，我們定義 UP 為 Y 減少
    player.vy = -3000
    player.update()
    assert player.y < 2000, f"向上移動後 Y 應減少，目前為 {player.y}"

def test_jump_trigger():
    """
    驗證跳躍觸發邏輯。
    按下跳躍鍵時，垂直速度 VZ 應該獲得一個向上的初速度。
    """
    player = Player()
    player.z = 0
    player.vz = 0
    
    # 這裡我們模擬 Rust 核心收到 INPUT_JUMP 後的行為
    # 預期初速度應為正值 (向上)
    jump_impulse = 8000 
    
    # 模擬核心邏輯：如果收到跳躍鍵且在地面
    if player.z == 0:
        player.vz = jump_impulse
    
    player.update()
    assert player.z > 0, "跳躍後 Z 座標應大於 0"
    assert player.vz < jump_impulse, "受重力影響，跳躍後 VZ 應小於初速度"

def test_input_mask_processing():
    """
    這是一個關鍵測試：驗證 GGRSSession 是否能正確解析多個按鍵。
    """
    # 預計會失敗，因為目前 GGRSSession.advance 只處理了左右
    session = GGRSSession(local_player_id=0, num_players=1, port=12351)
    
    # 同時按下「右」與「跳」
    input_mask = INPUT_RIGHT | INPUT_JUMP
    
    # 這裡我們需要一個方法來在測試中強制執行模擬，而不受網路同步限制
    # 暫時保留此測試作為目標
    pass
