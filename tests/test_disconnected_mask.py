from battlelite_core import OfflineSession, GGRSSession  # type: ignore[import]
from src.python.session.adapter import OfflineAdapter, GGRSAdapter


def test_offline_adapter_returns_zero_mask():
    adapter = OfflineAdapter(OfflineSession(2))
    assert adapter.get_disconnected_mask() == 0


def test_ggrs_session_has_get_disconnected_mask():
    assert hasattr(GGRSSession, "get_disconnected_mask")


def test_ggrs_session_initial_mask_is_zero():
    s = GGRSSession(0, 1, 7777, [], None)
    adapter = GGRSAdapter(s, 0, [])
    assert adapter.get_disconnected_mask() == 0
