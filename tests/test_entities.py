import pytest
from battlelite_core import OfflineSession, Player

STATE_IDLE   = 0
STATE_WALK   = 1
STATE_ATTACK = 2
STATE_HURT   = 3
STATE_SKILL  = 4

INPUT_ATTACK = 1 << 5
INPUT_SKILL  = 1 << 6

CHAR_TYPE_KNIGHT = 0
CHAR_TYPE_MAGE   = 1


def make_session_with_mage(mage_idx: int = 0, num_players: int = 2) -> OfflineSession:
    """建立 session 並把指定玩家設為法師（需設定 projectile_vx 才會生成投擲物）。"""
    session = OfflineSession(num_players)
    session.set_physics_config(
        CHAR_TYPE_MAGE,
        400, 9000, 5000, 3000, 4,   # gravity, jump_impulse, walk_speed_x, walk_speed_y, hitstop_frames
        70000, 80000,                # max_hp, max_mp
        0, 35000, 43500, 0,         # hurt_front, hurt_half_w, hurt_half_h, hurt_z_offset
    )
    session.set_ability(
        CHAR_TYPE_MAGE, 0,
        INPUT_ATTACK, 0, STATE_ATTACK,
        0, 20,                       # mp_cost, timer
        8000, 0, 0, 25000, 0, 0,    # dmg, front, half_w, depth, half_h, z_offset
        5000, 3000, 20,              # kb_vx, kb_vz, kb_timer
        True, 0, 9999,              # melee_enabled, hit_start, hit_end
        0,                           # damage_absorb
        0, 30, 10,                   # projectile_vx, projectile_lifetime, spawn_timer
        0, 0,                        # entity_spawn_offset, entity_spawn_z_offset
        False,                       # spawn_entity
        0, 0,                        # dash_vx, dash_tick
        False,                       # is_skill
    )
    session.set_ability(
        CHAR_TYPE_MAGE, 1,
        INPUT_SKILL, 0, STATE_SKILL,
        15000, 40,                   # mp_cost, timer
        20000, 0, 0, 40000, 0, 0,   # dmg, front, half_w, depth, half_h, z_offset
        7000, 5000, 30,              # kb_vx, kb_vz, kb_timer
        False, 0, 9999,             # melee_enabled, hit_start, hit_end
        0,                           # damage_absorb
        15000, 60, 35,              # projectile_vx, projectile_lifetime, spawn_timer
        0, 0,                        # entity_spawn_offset, entity_spawn_z_offset
        False,                       # spawn_entity
        0, 0,                        # dash_vx, dash_tick
        True,                        # is_skill
    )
    p = session.get_player(mage_idx)
    p.character_type = CHAR_TYPE_MAGE
    p.mp = 80000
    session.set_player(mage_idx, p)
    return session


# --- 1. 初始狀態 ---

def test_entity_count_starts_at_zero():
    session = OfflineSession(2)
    assert session.get_entity_count() == 0


# --- 2. 法師技能產生投擲物 ---

def test_mage_skill_spawns_entity():
    session = make_session_with_mage(mage_idx=0)
    for _ in range(10):
        session.advance([INPUT_SKILL, 0])
    assert session.get_entity_count() >= 1


def test_knight_skill_does_not_spawn_entity():
    """騎士的 SKILL 是格擋，不產生投擲物。"""
    session = OfflineSession(2)
    for _ in range(10):
        session.advance([INPUT_SKILL, 0])
    assert session.get_entity_count() == 0


# --- 3. 投擲物屬性 ---

def test_entity_has_correct_attributes():
    session = make_session_with_mage(mage_idx=0)
    for _ in range(10):
        session.advance([INPUT_SKILL, 0])
    assert session.get_entity_count() >= 1
    e = session.get_entity(0)
    assert hasattr(e, 'owner_id')
    assert hasattr(e, 'x')
    assert hasattr(e, 'y')
    assert hasattr(e, 'z')
    assert hasattr(e, 'lifetime')
    assert e.owner_id == 0


def test_entity_moves_horizontally():
    session = make_session_with_mage(mage_idx=0)
    p = session.get_player(0)
    p.facing_right = True
    session.set_player(0, p)

    for _ in range(10):
        session.advance([INPUT_SKILL, 0])

    e_before = session.get_entity(0)
    x_before = e_before.x

    session.advance([0, 0])

    e_after = session.get_entity(0)
    assert e_after.x > x_before


# --- 4. 生命週期 ---

def test_entity_expires_after_lifetime():
    session = make_session_with_mage(mage_idx=0)
    for _ in range(10):
        session.advance([INPUT_SKILL, 0])
    assert session.get_entity_count() >= 1

    for _ in range(70):
        session.advance([0, 0])

    assert session.get_entity_count() == 0


# --- 5. 碰撞傷害 ---

def test_entity_collision_causes_hurt():
    session = make_session_with_mage(mage_idx=0)

    mage = session.get_player(0)
    mage.x, mage.y, mage.z = 100000, 200000, 0
    mage.facing_right = True
    session.set_player(0, mage)

    target = session.get_player(1)
    target.x, target.y, target.z = 150000, 200000, 0
    target.state = STATE_IDLE
    session.set_player(1, target)

    for _ in range(60):
        session.advance([INPUT_SKILL, 0])

    victim = session.get_player(1)
    assert victim.state == STATE_HURT
