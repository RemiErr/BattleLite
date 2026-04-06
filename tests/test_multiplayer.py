import pytest
from battlelite_core import GGRSSession, Player

def test_four_player_initialization():
    """
    驗證 GGRS Session 是否能正確初始化 4 位玩家。
    """
    num_players = 4
    session = GGRSSession(local_player_id=0, num_players=num_players, port=12360)
    
    # 驗證是否能成功取得 4 位玩家的初始狀態
    for i in range(num_players):
        player = session.get_player(i)
        assert player is not None
        assert player.x == 0
        assert player.y == 0

def test_player_out_of_range():
    """
    驗證當讀取超出範圍的玩家 ID 時，是否會拋出 IndexError。
    """
    session = GGRSSession(local_player_id=0, num_players=2, port=12361)
    
    with pytest.raises(IndexError):
        session.get_player(99) # 超出範圍
