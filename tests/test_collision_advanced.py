from battlelite_core import OfflineSession

STATE_IDLE   = 0
STATE_ATTACK = 2
STATE_HURT   = 3
STATE_DEAD   = 5

INPUT_ATTACK = 1 << 5
INPUT_SKILL  = 1 << 6

CHAR_TYPE_MAGE = 1


def _make_session(num_players: int = 2) -> OfflineSession:
    s = OfflineSession(num_players)
    s.set_physics_config(
        CHAR_TYPE_MAGE,
        400, 9000, 5000, 3000, 4,
        100000, 80000,
        0, 35000, 43500, 0,
    )
    return s


def test_self_hit_immunity():
    """entity 不能對 owner 造成傷害。"""
    s = _make_session(1)
    s.set_ability(
        CHAR_TYPE_MAGE, 0,
        INPUT_SKILL, 0, 4,
        0, 50,
        5000, 0, 100000, 50000, 100000, 0,
        0, 0, 0,
        False, 0, 0,
        0, 0, 0,
        10000, 50, 5,
        0, 0,
        False,
        0, 0,
        True,
    )
    p = s.get_player(0)
    p.character_type = CHAR_TYPE_MAGE
    p.mp = 80000
    s.set_player(0, p)
    initial_hp = s.get_player(0).hp
    for _ in range(60):
        s.advance([INPUT_SKILL])
    assert s.get_player(0).hp == initial_hp


def test_on_hit_hp_restore():
    """攻擊命中後，攻擊者回復 HP（on_hit_hp_restore > 0）。"""
    s = _make_session(2)
    ON_HIT_RESTORE = 5000
    s.set_ability(
        CHAR_TYPE_MAGE, 0,
        INPUT_ATTACK, 0, STATE_ATTACK,
        0, 20,
        8000, 0, 0, 25000, 0, 0,
        5000, 3000, 20,
        True, 0, 9999,
        0, 0, ON_HIT_RESTORE,
        0, 30, 10,
        0, 0,
        False,
        0, 0,
        False,
    )
    mage = s.get_player(0)
    mage.character_type = CHAR_TYPE_MAGE
    mage.mp  = 80000
    mage.hp  = 50000
    mage.x   = 100000
    mage.y   = 350000
    mage.facing_right = True
    s.set_player(0, mage)

    target = s.get_player(1)
    target.character_type = CHAR_TYPE_MAGE  # hurt_half_w=35000, 命中閾值 0+35000=35000 > dx=30000
    target.x = 130000
    target.y = 350000
    s.set_player(1, target)

    for _ in range(30):
        s.advance([INPUT_ATTACK, 0])

    assert s.get_player(0).hp > 50000


def test_entity_does_not_hit_already_hurt_player():
    """已處於 HURT 狀態的玩家不會再次被投擲物命中（免疫期）。"""
    s = _make_session(2)
    s.set_ability(
        CHAR_TYPE_MAGE, 0,
        INPUT_SKILL, 0, 4,
        0, 50,
        8000, 0, 0, 40000, 0, 0,
        5000, 3000, 30,
        False, 0, 0,
        0, 0, 0,
        15000, 60, 10,
        0, 0,
        False,
        0, 0,
        True,
    )
    mage = s.get_player(0)
    mage.character_type = CHAR_TYPE_MAGE
    mage.mp = 80000
    mage.x  = 100000
    mage.y  = 350000
    mage.facing_right = True
    s.set_player(0, mage)

    victim = s.get_player(1)
    victim.state = STATE_HURT
    victim.x = 150000
    victim.y = 350000
    s.set_player(1, victim)

    hp_before = victim.hp
    for _ in range(20):
        s.advance([INPUT_SKILL, 0])

    assert s.get_player(1).hp == hp_before
