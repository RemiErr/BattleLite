from battlelite_core import OfflineSession

WORLD_X_MIN = 0
WORLD_X_MAX = 3_072_000
WORLD_Y_MIN = 250_000
WORLD_Y_MAX = 520_000


def _player_at(session, x, y):
    p = session.get_player(0)
    p.x, p.y = x, y
    p.vx, p.vy = 0, 0
    session.set_player(0, p)


def test_clamp_x_below_min():
    s = OfflineSession(1)
    _player_at(s, -100_000, 385_000)
    s.advance([0])
    p = s.get_player(0)
    assert p.x == WORLD_X_MIN
    assert p.vx == 0


def test_clamp_x_above_max():
    s = OfflineSession(1)
    _player_at(s, WORLD_X_MAX + 100_000, 385_000)
    s.advance([0])
    p = s.get_player(0)
    assert p.x == WORLD_X_MAX
    assert p.vx == 0


def test_clamp_y_below_min():
    s = OfflineSession(1)
    _player_at(s, 500_000, WORLD_Y_MIN - 50_000)
    s.advance([0])
    p = s.get_player(0)
    assert p.y == WORLD_Y_MIN
    assert p.vy == 0


def test_clamp_y_above_max():
    s = OfflineSession(1)
    _player_at(s, 500_000, WORLD_Y_MAX + 50_000)
    s.advance([0])
    p = s.get_player(0)
    assert p.y == WORLD_Y_MAX
    assert p.vy == 0


def test_in_bounds_player_unchanged():
    s = OfflineSession(1)
    _player_at(s, 500_000, 385_000)
    s.advance([0])
    p = s.get_player(0)
    assert p.x == 500_000
    assert p.y == 385_000
