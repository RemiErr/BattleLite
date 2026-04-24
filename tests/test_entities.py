import pytest
from battlelite_core import OfflineSession, Player

# 常數對齊 Rust
STATE_IDLE   = 0
STATE_WALK   = 1
STATE_ATTACK = 2
STATE_HURT   = 3
STATE_SKILL  = 4

INPUT_SKILL = 1 << 6

CHAR_TYPE_KNIGHT = 0
CHAR_TYPE_MAGE   = 1


def make_session_with_mage(mage_idx: int = 0, num_players: int = 2) -> OfflineSession:
    """建立 session 並把指定玩家設為法師（需設定 projectile_vx 才會生成投擲物）。"""
    session = OfflineSession(num_players)
    session.set_char_config(
        CHAR_TYPE_MAGE,
        70000, 80000, 15000, 8000, 20000,
        0, 0, 25000, 0, 0,
        0, 0, 40000, 0, 0,
        5000, 3000, 20, 7000, 5000, 30,
        0, 35000, 43500, 0,
        15000, 60, 35,
        20000,
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
    # 法師施放技能
    for _ in range(10):
        session.advance([INPUT_SKILL, 0])
    assert session.get_entity_count() >= 1


def test_knight_skill_does_not_spawn_entity():
    """騎士的 SKILL 是格擋，不產生投擲物。"""
    session = OfflineSession(2)  # 預設 character_type=0 (Knight)
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
    # 讓法師面朝右施法
    p = session.get_player(0)
    p.facing_right = True
    session.set_player(0, p)

    for _ in range(10):
        session.advance([INPUT_SKILL, 0])

    e_before = session.get_entity(0)
    x_before = e_before.x

    session.advance([0, 0])

    e_after = session.get_entity(0)
    assert e_after.x > x_before  # 向右移動


# --- 4. 生命週期 ---

def test_entity_expires_after_lifetime():
    session = make_session_with_mage(mage_idx=0)
    for _ in range(10):
        session.advance([INPUT_SKILL, 0])
    assert session.get_entity_count() >= 1

    # 推進足夠幀數讓投擲物消失（lifetime=60 幀）
    for _ in range(70):
        session.advance([0, 0])

    assert session.get_entity_count() == 0


# --- 5. 碰撞傷害 ---

def test_entity_collision_causes_hurt():
    session = make_session_with_mage(mage_idx=0)

    # 把法師和目標擺在同一水平線，目標在右方 50px
    mage = session.get_player(0)
    mage.x, mage.y, mage.z = 100000, 200000, 0
    mage.facing_right = True
    session.set_player(0, mage)

    target = session.get_player(1)
    target.x, target.y, target.z = 150000, 200000, 0
    target.state = STATE_IDLE
    session.set_player(1, target)

    # 施放技能後推進到投擲物飛抵目標位置
    for _ in range(60):
        session.advance([INPUT_SKILL, 0])

    victim = session.get_player(1)
    assert victim.state == STATE_HURT
