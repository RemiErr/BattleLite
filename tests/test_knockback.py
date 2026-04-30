from battlelite_core import OfflineSession

STATE_IDLE   = 0
STATE_WALK   = 1
STATE_ATTACK = 2
STATE_HURT   = 3
STATE_SKILL  = 4

INPUT_ATTACK = 1 << 5
INPUT_SKILL  = 1 << 6

CHAR_TYPE_KNIGHT = 0
CHAR_TYPE_MAGE   = 1


def _setup_mage_config(session) -> None:
    """設定 Mage（char_type=1）的物理與技能參數（對應舊版 set_char_config 值）。"""
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
        0, 0, 0,                     # damage_absorb, hp_regen_per_tick, on_hit_hp_restore
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
        True, 0, 9999,              # melee_enabled, hit_start, hit_end
        0, 0, 0,                     # damage_absorb, hp_regen_per_tick, on_hit_hp_restore
        15000, 60, 35,              # projectile_vx, projectile_lifetime, spawn_timer
        0, 0,                        # entity_spawn_offset, entity_spawn_z_offset
        False,                       # spawn_entity
        0, 0,                        # dash_vx, dash_tick
        True,                        # is_skill
    )


def _make_adjacent(session, attacker_idx=0, victim_idx=1, gap=25000):
    """將兩位玩家並排放置，attacker 面右。"""
    a = session.get_player(attacker_idx)
    a.x, a.y, a.z = 200000, 300000, 0
    a.facing_right = True
    session.set_player(attacker_idx, a)

    v = session.get_player(victim_idx)
    v.x, v.y, v.z = a.x + gap, 300000, 0
    v.state = STATE_IDLE
    session.set_player(victim_idx, v)


# --- 1. 擊飛方向 ---

def test_attack_knockback_pushes_victim_right():
    """攻擊者面右，受擊者應被推向右方（vx > 0）。"""
    session = OfflineSession(2)
    _make_adjacent(session)

    a = session.get_player(0)
    a.state = STATE_ATTACK
    a.timer = 16
    session.set_player(0, a)

    session.advance([0, 0])

    victim = session.get_player(1)
    assert victim.state == STATE_HURT
    assert victim.vx > 0


def test_attack_knockback_pushes_victim_left():
    """攻擊者面左，受擊者應被推向左方（vx < 0）。"""
    session = OfflineSession(2)

    a = session.get_player(0)
    a.x, a.y, a.z = 500000, 300000, 0
    a.facing_right = False
    a.state = STATE_ATTACK
    a.timer = 16
    session.set_player(0, a)

    v = session.get_player(1)
    v.x, v.y, v.z = a.x - 25000, 300000, 0
    v.state = STATE_IDLE
    session.set_player(1, v)

    session.advance([0, 0])

    victim = session.get_player(1)
    assert victim.state == STATE_HURT
    assert victim.vx < 0


# --- 2. 不同招式力道差異 ---

def test_skill_knockback_stronger_than_attack():
    """Knight 技能（格擋反擊）的擊飛高度應大於普通攻擊。"""
    s1 = OfflineSession(2)
    _make_adjacent(s1)
    a1 = s1.get_player(0)
    a1.state = STATE_ATTACK
    a1.timer = 16
    s1.set_player(0, a1)
    s1.advance([0, 0])
    atk_vz = s1.get_player(1).vz

    s2 = OfflineSession(2)
    _make_adjacent(s2)
    a2 = s2.get_player(0)
    a2.character_type = CHAR_TYPE_KNIGHT
    a2.state = STATE_SKILL
    a2.timer = 16
    a2.mp = 50000
    s2.set_player(0, a2)
    s2.advance([0, 0])
    skill_vz = s2.get_player(1).vz

    assert skill_vz > atk_vz


# --- 3. 受擊期間橫向移動 ---

def test_hurt_player_moves_horizontally():
    """HURT 狀態下玩家應因 vx 而移動，不應被鎖定原地。"""
    session = OfflineSession(2)
    v = session.get_player(0)
    v.state = STATE_HURT
    v.timer = 20
    v.x = 300000
    v.vx = 10000
    session.set_player(0, v)

    session.advance([0, 0])

    assert session.get_player(0).x > 300000


# --- 4. 空中減速 ---

def test_hurt_vx_decelerates_each_frame():
    """HURT 狀態的 vx 每幀應受阻力遞減。"""
    session = OfflineSession(2)
    v = session.get_player(0)
    v.state = STATE_HURT
    v.timer = 30
    v.x = 300000
    v.vx = 10000
    session.set_player(0, v)

    session.advance([0, 0])
    vx_after_1 = session.get_player(0).vx

    session.advance([0, 0])
    vx_after_2 = session.get_player(0).vx

    assert vx_after_1 < 10000
    assert vx_after_2 < vx_after_1


# --- 5. 落地摩擦 ---

def test_landing_reduces_vx():
    """落地瞬間 vx 應因摩擦力而減少。"""
    session = OfflineSession(2)
    v = session.get_player(0)
    v.state = STATE_HURT
    v.timer = 30
    v.z = 200
    v.vz = -500
    v.vx = 10000
    session.set_player(0, v)

    for _ in range(5):
        session.advance([0, 0])

    after = session.get_player(0)
    assert after.z == 0
    assert abs(after.vx) < 10000


# --- 6. 投擲物擊飛方向 ---

def test_entity_knockback_follows_projectile_direction():
    """向右飛行的投擲物擊中後，受擊者應向右被推（vx > 0）。"""
    session = OfflineSession(2)
    _setup_mage_config(session)

    mage = session.get_player(0)
    mage.x, mage.y, mage.z = 100000, 200000, 0
    mage.facing_right = True
    mage.character_type = CHAR_TYPE_MAGE
    mage.mp = 80000
    session.set_player(0, mage)

    target = session.get_player(1)
    target.x, target.y, target.z = 150000, 200000, 0
    target.state = STATE_IDLE
    session.set_player(1, target)

    for _ in range(15):
        session.advance([INPUT_SKILL, 0])

    victim = session.get_player(1)
    assert victim.state == STATE_HURT
    assert victim.vx > 0
