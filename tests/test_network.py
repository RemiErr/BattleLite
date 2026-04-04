import pytest

def test_ggrs_session_initialization():
    """
    驗證是否能建立 GGRS P2P Session。
    """
    try:
        from battlelite_core import GGRSSession
    except ImportError:
        pytest.fail("battlelite_core 模組中找不到 'GGRSSession' 類別。")

    # 建立一個測試用的 P2P Session
    session = GGRSSession(local_player_id=0, num_players=2, port=12345)
    
    assert session is not None
    assert hasattr(session, 'advance'), "Session 應具備 advance 函式"

def test_ggrs_advance_not_crashing():
    """
    驗證即便在尚未同步的情況下，呼叫 advance 也不會導致程式崩潰。
    這是為了模擬真實網路環境下的等待狀態。
    """
    from battlelite_core import GGRSSession
    
    session = GGRSSession(local_player_id=0, num_players=2, port=12347)
    
    # 執行一幀推進 (此時尚未同步，應靜默跳過)
    try:
        session.advance(local_input=1)
    except Exception as e:
        pytest.fail(f"在尚未同步時呼叫 advance 發生錯誤: {e}")
    
    # 驗證同步狀態
    assert session.is_synchronized() is False
