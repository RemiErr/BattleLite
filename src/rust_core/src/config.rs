// --- 全域常數 ---

pub(crate) const CHAR_WIDTH: i32 = 30000;
pub(crate) const ATK_DEPTH_REACH: i32 = 25000;
pub(crate) const MAX_HP: i32 = 100000;
pub(crate) const MAX_MP: i32 = 50000;
pub(crate) const MP_REGEN: i32 = 50;

pub(crate) const STATE_IDLE:   u8 = 0;
pub(crate) const STATE_WALK:   u8 = 1;
pub(crate) const STATE_ATTACK: u8 = 2;
pub(crate) const STATE_HURT:   u8 = 3;
pub(crate) const STATE_SKILL:  u8 = 4;
pub(crate) const STATE_DEAD:   u8 = 5;

pub(crate) const INPUT_RIGHT:  u8 = 1 << 0;
pub(crate) const INPUT_LEFT:   u8 = 1 << 1;
pub(crate) const INPUT_UP:     u8 = 1 << 2;
pub(crate) const INPUT_DOWN:   u8 = 1 << 3;
pub(crate) const INPUT_JUMP:   u8 = 1 << 4;
pub(crate) const INPUT_ATTACK: u8 = 1 << 5;
pub(crate) const INPUT_SKILL:  u8 = 1 << 6;

// --- 角色設定（session 層持有，不進 GameState）---

#[derive(Clone, Debug)]
pub(crate) struct PhysicsConfig {
    pub(crate) gravity:        i32,
    pub(crate) jump_impulse:   i32,
    pub(crate) walk_speed_x:   i32,
    pub(crate) walk_speed_y:   i32,
    pub(crate) hitstop_frames: u32,
    pub(crate) max_hp:         i32,
    pub(crate) max_mp:         i32,
    pub(crate) hurt_front:     i32,
    pub(crate) hurt_half_w:    i32,
    pub(crate) hurt_half_h:    i32,
    pub(crate) hurt_z_offset:  i32,
}

impl Default for PhysicsConfig {
    fn default() -> Self {
        PhysicsConfig {
            gravity:        400,
            jump_impulse:   9000,
            walk_speed_x:   5000,
            walk_speed_y:   3000,
            hitstop_frames: 4,
            max_hp:         MAX_HP,
            max_mp:         MAX_MP,
            hurt_front:     0,
            hurt_half_w:    CHAR_WIDTH / 2,
            hurt_half_h:    50000,
            hurt_z_offset:  0,
        }
    }
}

// 每個技能槽的完整設定。trigger_button / state_id 由 Python 定義，Rust 通用執行。
#[derive(Clone, Debug)]
pub(crate) struct AbilityConfig {
    pub(crate) trigger_button:        u8,
    #[allow(dead_code)]
    pub(crate) trigger_context:       u8,   // reserved; 0 = ANY
    pub(crate) state_id:              u8,
    pub(crate) mp_cost:               i32,
    pub(crate) timer:                 u32,
    pub(crate) dmg:                   i32,
    pub(crate) front:                 i32,
    pub(crate) half_w:                i32,
    pub(crate) depth:                 i32,
    pub(crate) half_h:                i32,
    pub(crate) z_offset:              i32,
    pub(crate) kb_vx:                 i32,
    pub(crate) kb_vz:                 i32,
    pub(crate) kb_timer:              u32,
    pub(crate) melee_enabled:         bool,
    pub(crate) hit_start:             u32,
    pub(crate) hit_end:               u32,
    pub(crate) damage_absorb:         i32,
    pub(crate) hp_regen_per_tick:     i32,
    pub(crate) on_hit_hp_restore:     i32,
    pub(crate) projectile_vx:         i32,
    pub(crate) projectile_lifetime:   u32,
    pub(crate) spawn_timer:           u32,
    pub(crate) entity_spawn_offset:   i32,
    pub(crate) entity_spawn_z_offset: i32,
    pub(crate) spawn_entity:          bool,
    pub(crate) dash_vx:               i32,
    pub(crate) dash_tick:             u32,
    pub(crate) is_skill:              bool,
}

impl Default for AbilityConfig {
    fn default() -> Self {
        AbilityConfig {
            trigger_button:        INPUT_ATTACK,
            trigger_context:       0,
            state_id:              2,   // STATE_ATTACK
            mp_cost:               0,
            timer:                 20,
            dmg:                   10000,
            front:                 30000,
            half_w:                20000,
            depth:                 ATK_DEPTH_REACH,
            half_h:                5000,
            z_offset:              0,
            kb_vx:                 8000,
            kb_vz:                 4000,
            kb_timer:              30,
            melee_enabled:         true,
            hit_start:             0,
            hit_end:               9999,
            damage_absorb:         0,
            hp_regen_per_tick:     0,
            on_hit_hp_restore:     0,
            projectile_vx:         0,
            projectile_lifetime:   30,
            spawn_timer:           10,
            entity_spawn_offset:   0,
            entity_spawn_z_offset: 0,
            spawn_entity:          false,
            dash_vx:               0,
            dash_tick:             0,
            is_skill:              false,
        }
    }
}

#[derive(Clone, Debug)]
pub(crate) struct CharConfig {
    pub(crate) physics:   PhysicsConfig,
    pub(crate) abilities: Vec<AbilityConfig>,
}

impl Default for CharConfig {
    fn default() -> Self {
        CharConfig {
            physics: PhysicsConfig::default(),
            abilities: vec![
                AbilityConfig::default(),
                AbilityConfig {
                    trigger_button:        INPUT_SKILL,
                    trigger_context:       0,
                    state_id:              4,   // STATE_SKILL
                    mp_cost:               20000,
                    timer:                 40,
                    dmg:                   15000,
                    front:                 45000,
                    half_w:                35000,
                    depth:                 40000,
                    half_h:                40000,
                    z_offset:              0,
                    kb_vx:                 8000,
                    kb_vz:                 6000,
                    kb_timer:              40,
                    melee_enabled:         true,
                    hit_start:             0,
                    hit_end:               9999,
                    damage_absorb:         0,
                    hp_regen_per_tick:     0,
                    on_hit_hp_restore:     0,
                    projectile_vx:         0,
                    projectile_lifetime:   60,
                    spawn_timer:           35,
                    entity_spawn_offset:   0,
                    entity_spawn_z_offset: 0,
                    spawn_entity:          false,
                    dash_vx:               0,
                    dash_tick:             0,
                    is_skill:              true,
                },
            ],
        }
    }
}

pub(crate) fn get_cfg(configs: &[CharConfig], char_type: u8) -> CharConfig {
    configs.get(char_type as usize).cloned().unwrap_or_default()
}

// 共用設定寫入邏輯（OfflineSession / GGRSSession 各持一份 configs）
pub(crate) fn do_set_physics_config(
    configs: &mut Vec<CharConfig>,
    players: &mut Vec<crate::player::Player>,
    char_type: usize,
    gravity: i32, jump_impulse: i32, walk_speed_x: i32, walk_speed_y: i32, hitstop_frames: u32,
    max_hp: i32, max_mp: i32,
    hurt_front: i32, hurt_half_w: i32, hurt_half_h: i32, hurt_z_offset: i32,
) {
    while configs.len() <= char_type { configs.push(CharConfig::default()); }
    let phy = &mut configs[char_type].physics;
    phy.gravity        = gravity;
    phy.jump_impulse   = jump_impulse;
    phy.walk_speed_x   = walk_speed_x;
    phy.walk_speed_y   = walk_speed_y;
    phy.hitstop_frames = hitstop_frames;
    phy.max_hp         = max_hp;
    phy.max_mp         = max_mp;
    phy.hurt_front     = hurt_front;
    phy.hurt_half_w    = hurt_half_w;
    phy.hurt_half_h    = hurt_half_h;
    phy.hurt_z_offset  = hurt_z_offset;
    for p in players.iter_mut() {
        if p.character_type as usize == char_type {
            p.hp = max_hp;
            p.mp = max_mp;
        }
    }
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn do_set_ability(
    configs: &mut Vec<CharConfig>,
    char_type: usize, slot_idx: usize,
    trigger_button: u8, trigger_context: u8, state_id: u8,
    mp_cost: i32, timer: u32,
    dmg: i32, front: i32, half_w: i32, depth: i32, half_h: i32, z_offset: i32,
    kb_vx: i32, kb_vz: i32, kb_timer: u32,
    melee_enabled: bool, hit_start: u32, hit_end: u32,
    damage_absorb: i32, hp_regen_per_tick: i32, on_hit_hp_restore: i32,
    projectile_vx: i32, projectile_lifetime: u32, spawn_timer: u32,
    entity_spawn_offset: i32, entity_spawn_z_offset: i32,
    spawn_entity: bool,
    dash_vx: i32, dash_tick: u32,
    is_skill: bool,
) {
    while configs.len() <= char_type { configs.push(CharConfig::default()); }
    let abilities = &mut configs[char_type].abilities;
    let ab = AbilityConfig {
        trigger_button, trigger_context, state_id,
        mp_cost, timer, dmg,
        front, half_w, depth, half_h, z_offset,
        kb_vx, kb_vz, kb_timer,
        melee_enabled, hit_start, hit_end,
        damage_absorb, hp_regen_per_tick, on_hit_hp_restore,
        projectile_vx, projectile_lifetime, spawn_timer,
        entity_spawn_offset, entity_spawn_z_offset,
        spawn_entity,
        dash_vx, dash_tick,
        is_skill,
    };
    if slot_idx < abilities.len() {
        abilities[slot_idx] = ab;
    } else {
        abilities.push(ab);
    }
}
