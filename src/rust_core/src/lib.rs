use pyo3::prelude::*;
use pyo3::exceptions::{PyRuntimeError, PyIndexError};
use ggrs::{Config, P2PSession, PlayerType, SessionBuilder, InputStatus, GgrsRequest, UdpNonBlockingSocket, SessionState};
use std::net::SocketAddr;

use chacha20poly1305::{ChaCha20Poly1305, Key, Nonce, KeyInit, aead::Aead};
use base64::{engine::general_purpose, Engine as _};

// --- 1. 全域常數 ---
const CHAR_WIDTH: i32 = 30000;
const ATK_DEPTH_REACH: i32 = 25000;
const MAX_HP: i32 = 100000;
const MAX_MP: i32 = 50000;
const MP_REGEN: i32 = 50;

const STATE_IDLE: u8 = 0;
const STATE_WALK: u8 = 1;
// Action state IDs (2, 4, …) are Python-defined via AbilityConfig.state_id
const STATE_HURT: u8 = 3;
const STATE_DEAD: u8 = 5;

const INPUT_RIGHT: u8  = 1 << 0;
const INPUT_LEFT: u8   = 1 << 1;
const INPUT_UP: u8     = 1 << 2;
const INPUT_DOWN: u8   = 1 << 3;
const INPUT_JUMP: u8   = 1 << 4;
const INPUT_ATTACK: u8 = 1 << 5;
const INPUT_SKILL: u8  = 1 << 6;

// --- 2. 角色設定（session 層持有，不進 GameState）---

#[derive(Clone, Debug)]
struct PhysicsConfig {
    gravity:       i32,
    jump_impulse:  i32,
    walk_speed_x:  i32,
    walk_speed_y:  i32,
    hitstop_frames: u32,
    max_hp:        i32,
    max_mp:        i32,
    hurt_front:    i32,
    hurt_half_w:   i32,
    hurt_half_h:   i32,
    hurt_z_offset: i32,
}

impl Default for PhysicsConfig {
    fn default() -> Self {
        PhysicsConfig {
            gravity:       400,
            jump_impulse:  9000,
            walk_speed_x:  5000,
            walk_speed_y:  3000,
            hitstop_frames: 4,
            max_hp:        MAX_HP,
            max_mp:        MAX_MP,
            hurt_front:    0,
            hurt_half_w:   CHAR_WIDTH / 2,
            hurt_half_h:   50000,
            hurt_z_offset: 0,
        }
    }
}

// 每個技能槽的完整設定。trigger_button / state_id 由 Python 定義，Rust 通用執行。
#[derive(Clone, Debug)]
struct AbilityConfig {
    trigger_button:        u8,
    trigger_context:       u8,   // reserved; 0 = ANY
    state_id:              u8,
    mp_cost:               i32,
    timer:                 u32,
    dmg:                   i32,
    front:                 i32,
    half_w:                i32,
    depth:                 i32,
    half_h:                i32,
    z_offset:              i32,
    kb_vx:                 i32,
    kb_vz:                 i32,
    kb_timer:              u32,
    melee_enabled:         bool,
    hit_start:             u32,
    hit_end:               u32,
    damage_absorb:         i32,
    hp_regen_per_tick:     i32,
    on_hit_hp_restore:     i32,
    projectile_vx:         i32,
    projectile_lifetime:   u32,
    spawn_timer:           u32,
    entity_spawn_offset:   i32,
    entity_spawn_z_offset: i32,
    spawn_entity:          bool,
    dash_vx:               i32,
    dash_tick:             u32,
    is_skill:              bool,
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
struct CharConfig {
    physics:   PhysicsConfig,
    abilities: Vec<AbilityConfig>,
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

fn get_cfg(configs: &[CharConfig], char_type: u8) -> CharConfig {
    configs.get(char_type as usize).cloned().unwrap_or_default()
}

// 共用設定寫入邏輯（OfflineSession / GGRSSession 各持一份 configs）
fn do_set_physics_config(
    configs: &mut Vec<CharConfig>,
    players: &mut Vec<Player>,
    char_type: usize,
    gravity: i32, jump_impulse: i32, walk_speed_x: i32, walk_speed_y: i32, hitstop_frames: u32,
    max_hp: i32, max_mp: i32,
    hurt_front: i32, hurt_half_w: i32, hurt_half_h: i32, hurt_z_offset: i32,
) {
    while configs.len() <= char_type { configs.push(CharConfig::default()); }
    let phy = &mut configs[char_type].physics;
    phy.gravity       = gravity;
    phy.jump_impulse  = jump_impulse;
    phy.walk_speed_x  = walk_speed_x;
    phy.walk_speed_y  = walk_speed_y;
    phy.hitstop_frames = hitstop_frames;
    phy.max_hp        = max_hp;
    phy.max_mp        = max_mp;
    phy.hurt_front    = hurt_front;
    phy.hurt_half_w   = hurt_half_w;
    phy.hurt_half_h   = hurt_half_h;
    phy.hurt_z_offset = hurt_z_offset;
    for p in players.iter_mut() {
        if p.character_type as usize == char_type {
            p.hp = max_hp;
            p.mp = max_mp;
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn do_set_ability(
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

// --- 3. 物理實體 ---

#[pyclass]
#[derive(Clone, Default, Debug)]
pub struct Player {
    #[pyo3(get, set)] pub x: i32,
    #[pyo3(get, set)] pub y: i32,
    #[pyo3(get, set)] pub z: i32,
    #[pyo3(get, set)] pub vx: i32,
    #[pyo3(get, set)] pub vy: i32,
    #[pyo3(get, set)] pub vz: i32,
    #[pyo3(get, set)] pub state: u8,
    #[pyo3(get, set)] pub timer: u32,
    #[pyo3(get, set)] pub facing_right: bool,
    #[pyo3(get, set)] pub hp: i32,
    #[pyo3(get, set)] pub mp: i32,
    #[pyo3(get, set)] pub character_type: u8,
    #[pyo3(get, set)] pub hitstop: u32,
}

#[pymethods]
impl Player {
    #[new]
    fn new() -> Self {
        let mut p = Player::default();
        p.facing_right = true;
        p.hp = MAX_HP;
        p.mp = MAX_MP;
        p
    }

    // Python 測試相容：使用預設 AbilityConfig（ATK slot）
    fn check_attack_hit(&self, other: &Player) -> bool {
        check_attack_hit_cfg(self, other, &AbilityConfig::default(), &PhysicsConfig::default())
    }

    // Python 測試相容：使用預設物理常數，不鎖定移動
    fn update(&mut self) {
        self.update_internal(PhysicsConfig::default().gravity, false);
    }
}

impl Player {
    // in_ability: 若為 true，本幀不套用 vx/vy 位移（技能鎖定狀態）
    fn update_internal(&mut self, gravity: i32, in_ability: bool) {
        if self.state == STATE_DEAD {
            if self.z > 0 || self.vz > 0 { self.vz -= gravity; }
            self.z += self.vz;
            if self.z <= 0 { self.z = 0; self.vz = 0; self.vx = 0; self.vy = 0; }
            return;
        }
        if self.hitstop > 0 {
            self.hitstop -= 1;
            return;
        }
        if self.timer > 0 {
            self.timer -= 1;
            if self.timer == 0 { self.state = STATE_IDLE; }
        }
        if self.z > 0 || self.vz > 0 { self.vz -= gravity; }
        if !in_ability {
            self.x += self.vx;
            self.y += self.vy;
        }
        if self.state == STATE_HURT {
            self.vx = self.vx * 9 / 10;
            self.vy = self.vy * 9 / 10;
        }
        self.z += self.vz;
        if self.z <= 0 {
            self.z = 0;
            self.vz = 0;
            if self.state == STATE_HURT {
                self.vx /= 2;
                self.vy /= 2;
            }
        }
    }
}

fn check_attack_hit_cfg(attacker: &Player, victim: &Player, ab: &AbilityConfig, vic_phy: &PhysicsConfig) -> bool {
    let atk_offset_x = if attacker.facing_right { ab.front } else { -ab.front };
    let atk_center_x = attacker.x + atk_offset_x;
    let atk_center_z = attacker.z + ab.z_offset;
    let vic_offset_x = if victim.facing_right { vic_phy.hurt_front } else { -vic_phy.hurt_front };
    let vic_center_x = victim.x + vic_offset_x;
    let vic_center_z = victim.z + vic_phy.hurt_z_offset;
    let dx = (atk_center_x - vic_center_x).abs();
    let dy = (attacker.y - victim.y).abs();
    let dz = (atk_center_z - vic_center_z).abs();
    dx < (ab.half_w + vic_phy.hurt_half_w) && dy < ab.depth && dz < (ab.half_h + vic_phy.hurt_half_h)
}

// --- 4. 實體系統 ---

#[derive(Clone, Default, Debug)]
pub struct Entity {
    pub owner_id:         usize,
    pub character_type:   u8,
    pub ability_state_id: u8,   // 生成此 entity 的 ability 的 state_id
    pub x: i32,
    pub y: i32,
    pub z: i32,
    pub vx: i32,
    pub vy: i32,
    pub lifetime: u32,
    pub is_skill: bool,
}

#[pyclass]
#[derive(Clone, Debug)]
pub struct EntityView {
    #[pyo3(get)] pub owner_id:         usize,
    #[pyo3(get)] pub character_type:   u8,
    #[pyo3(get)] pub ability_state_id: u8,
    #[pyo3(get)] pub x: i32,
    #[pyo3(get)] pub y: i32,
    #[pyo3(get)] pub z: i32,
    #[pyo3(get)] pub vx: i32,
    #[pyo3(get)] pub lifetime: u32,
    #[pyo3(get)] pub is_skill: bool,
}

// --- 5. 遊戲狀態與共用邏輯 ---

#[derive(Clone, Default, Debug)]
pub struct GameState {
    pub players:  Vec<Player>,
    pub frame:    i32,
    pub entities: Vec<Entity>,
}

pub struct BattleConfig;
impl Config for BattleConfig {
    type Input   = u8;
    type State   = GameState;
    type Address = SocketAddr;
}

fn apply_hit(
    victim: &mut Player,
    damage: i32, kb_vx: i32, kb_vz: i32, kb_timer: u32,
    absorb: i32, hitstop: u32,
) -> bool {
    if absorb > 0 {
        victim.hp = (victim.hp - (damage - absorb).max(0)).max(0);
    } else {
        victim.state   = STATE_HURT;
        victim.timer   = kb_timer;
        victim.vx      = kb_vx;
        victim.vz      = kb_vz;
        victim.hp      = (victim.hp - damage).max(0);
        victim.hitstop = hitstop;
    }
    if victim.hp == 0 { victim.state = STATE_DEAD; victim.timer = 0; }
    absorb == 0
}

fn apply_per_tick_buffs(p: &mut Player, phy: &PhysicsConfig, active_ab: Option<&AbilityConfig>) {
    if p.mp < phy.max_mp { p.mp = (p.mp + MP_REGEN).min(phy.max_mp); }
    if p.hp > phy.max_hp { p.hp = phy.max_hp; }
    if let Some(ab) = active_ab {
        if ab.hp_regen_per_tick > 0 && p.hp > 0 && p.state != STATE_DEAD {
            p.hp = (p.hp + ab.hp_regen_per_tick).min(phy.max_hp);
        }
    }
}

fn perform_tick(state: &mut GameState, inputs: &[(u8, InputStatus)], configs: &[CharConfig]) {
    state.frame += 1;

    let mut spawn_queue: Vec<Entity> = Vec::new();

    for (i, (input, status)) in inputs.iter().enumerate() {
        if i >= state.players.len() || *status == InputStatus::Disconnected { continue; }
        let p = &mut state.players[i];
        let pcfg = get_cfg(configs, p.character_type);
        let phy  = &pcfg.physics;

        if p.state == STATE_DEAD {
            p.update_internal(phy.gravity, false);
            continue;
        }

        // 移動輸入 + 觸發技能
        if p.state == STATE_IDLE || p.state == STATE_WALK {
            p.vx = 0; p.vy = 0;
            if input & INPUT_RIGHT != 0 { p.vx += phy.walk_speed_x; p.state = STATE_WALK; p.facing_right = true; }
            if input & INPUT_LEFT  != 0 { p.vx -= phy.walk_speed_x; p.state = STATE_WALK; p.facing_right = false; }
            if input & INPUT_DOWN  != 0 { p.vy += phy.walk_speed_y; p.state = STATE_WALK; }
            if input & INPUT_UP    != 0 { p.vy -= phy.walk_speed_y; p.state = STATE_WALK; }
            if p.vx == 0 && p.vy == 0  { p.state = STATE_IDLE; }
            if input & INPUT_JUMP != 0 && p.z == 0 { p.vz = phy.jump_impulse; }
            for ab in &pcfg.abilities {
                if *input & ab.trigger_button != 0 && p.mp >= ab.mp_cost {
                    p.state = ab.state_id;
                    p.timer = ab.timer;
                    p.mp   -= ab.mp_cost;
                    p.vx    = 0; p.vy = 0;
                    break;
                }
            }
        }

        // Entity 生成（以 timer 倒數值比對，在 update_internal 遞減前判斷）
        if let Some(ab) = pcfg.abilities.iter().find(|ab| {
            ab.state_id == p.state
                && p.timer == ab.spawn_timer
                && (ab.projectile_vx != 0 || ab.spawn_entity)
        }) {
            let vx = if p.facing_right { ab.projectile_vx } else { -ab.projectile_vx };
            let spawn_x = if p.facing_right { p.x + ab.entity_spawn_offset } else { p.x - ab.entity_spawn_offset };
            spawn_queue.push(Entity {
                owner_id:         i,
                character_type:   p.character_type,
                ability_state_id: ab.state_id,
                x: spawn_x, y: p.y, z: p.z + ab.entity_spawn_z_offset,
                vx, vy: 0,
                lifetime: ab.projectile_lifetime,
                is_skill: ab.is_skill,
            });
        }

        // 衝刺（elapsed = timer_max – timer，在 update_internal 遞減前計算）
        if let Some(ab) = pcfg.abilities.iter().find(|ab| ab.state_id == p.state && ab.dash_vx != 0) {
            let elapsed = ab.timer.saturating_sub(p.timer);
            if elapsed == ab.dash_tick {
                let dash = if p.facing_right { ab.dash_vx } else { -ab.dash_vx };
                p.x += dash;
            }
        }

        let active_ab = pcfg.abilities.iter().find(|ab| ab.state_id == p.state);
        p.update_internal(phy.gravity, active_ab.is_some());
        apply_per_tick_buffs(p, phy, active_ab);
    }

    // 實體移動 + 壽命遞減
    state.entities.retain_mut(|e| {
        e.x += e.vx;
        e.y += e.vy;
        e.lifetime = e.lifetime.saturating_sub(1);
        e.lifetime > 0
    });
    state.entities.extend(spawn_queue);

    // 投擲物碰撞判定
    struct EntityHit { victim: usize, owner_id: usize, vx: i32, vz: i32, timer: u32, damage: i32, on_hit_hp_restore: i32 }
    let mut entity_hits: Vec<EntityHit> = Vec::new();
    for e in &state.entities {
        let atk_cfg = get_cfg(configs, e.character_type);
        let Some(ab) = atk_cfg.abilities.iter().find(|ab| ab.state_id == e.ability_state_id) else { continue };
        for j in 0..state.players.len() {
            if e.owner_id == j { continue; }
            let victim = &state.players[j];
            if victim.state == STATE_HURT || victim.state == STATE_DEAD { continue; }
            let vic_cfg = get_cfg(configs, victim.character_type);
            let vic_phy = &vic_cfg.physics;
            let vic_off_x = if victim.facing_right { vic_phy.hurt_front } else { -vic_phy.hurt_front };
            let dx = (e.x - (victim.x + vic_off_x)).abs();
            let dy = (e.y - victim.y).abs();
            let dz = (e.z + ab.z_offset - (victim.z + vic_phy.hurt_z_offset)).abs();
            if dx < ab.half_w + vic_phy.hurt_half_w
                && dy < ab.depth
                && dz < ab.half_h + vic_phy.hurt_half_h
            {
                let kb_vx = if e.vx >= 0 { ab.kb_vx } else { -ab.kb_vx };
                let ratio = if ab.projectile_lifetime > 0 {
                    e.lifetime as i32 * 1000 / ab.projectile_lifetime as i32
                } else { 1000 };
                let damage = ab.dmg * ratio / 1000;
                entity_hits.push(EntityHit { victim: j, owner_id: e.owner_id, vx: kb_vx, vz: ab.kb_vz, timer: ab.kb_timer, damage, on_hit_hp_restore: ab.on_hit_hp_restore });
            }
        }
    }
    let mut entity_hp_restores: Vec<(usize, i32)> = Vec::new();
    for hit in entity_hits {
        if state.players[hit.victim].state == STATE_DEAD { continue; }
        let (victim_state, victim_char) = {
            let v = &state.players[hit.victim];
            (v.state, v.character_type)
        };
        let vic_cfg = get_cfg(configs, victim_char);
        let absorb = vic_cfg.abilities.iter()
            .find(|ab| ab.state_id == victim_state && ab.damage_absorb > 0)
            .map(|ab| ab.damage_absorb).unwrap_or(0);
        let hit_landed = apply_hit(&mut state.players[hit.victim], hit.damage, hit.vx, hit.vz, hit.timer, absorb, vic_cfg.physics.hitstop_frames);
        if hit_landed && hit.on_hit_hp_restore > 0 {
            entity_hp_restores.push((hit.owner_id, hit.on_hit_hp_restore));
        }
    }
    for (pid, amount) in entity_hp_restores {
        if let Some(owner) = state.players.get_mut(pid) {
            if owner.state != STATE_DEAD {
                let max_hp = get_cfg(configs, owner.character_type).physics.max_hp;
                owner.hp = (owner.hp + amount).min(max_hp);
            }
        }
    }

    // 近戰判定
    let num_players = state.players.len();
    for i in 0..num_players {
        let atk_info = state.players[i].clone();
        let atk_cfg  = get_cfg(configs, atk_info.character_type);
        let Some(ab) = atk_cfg.abilities.iter().find(|ab| {
            if ab.state_id != atk_info.state || !ab.melee_enabled { return false; }
            let elapsed = ab.timer.saturating_sub(atk_info.timer);
            elapsed >= ab.hit_start && elapsed <= ab.hit_end
        }) else { continue };

        let kb_vx = if atk_info.facing_right { ab.kb_vx } else { -ab.kb_vx };
        let mut hit_landed = false;

        for j in 0..num_players {
            if i == j { continue; }
            if state.players[j].state == STATE_HURT || state.players[j].state == STATE_DEAD { continue; }
            let vic_cfg = get_cfg(configs, state.players[j].character_type);
            if check_attack_hit_cfg(&atk_info, &state.players[j], ab, &vic_cfg.physics) {
                let victim_state = state.players[j].state;
                let absorb = vic_cfg.abilities.iter()
                    .find(|a| a.state_id == victim_state && a.damage_absorb > 0)
                    .map(|a| a.damage_absorb).unwrap_or(0);
                if apply_hit(&mut state.players[j], ab.dmg, kb_vx, ab.kb_vz, ab.kb_timer, absorb, atk_cfg.physics.hitstop_frames) {
                    hit_landed = true;
                }
            }
        }
        if hit_landed {
            state.players[i].hitstop = atk_cfg.physics.hitstop_frames;
            if ab.on_hit_hp_restore > 0 {
                let max_hp = atk_cfg.physics.max_hp;
                state.players[i].hp = (state.players[i].hp + ab.on_hit_hp_restore).min(max_hp);
            }
        }
    }
}

// --- 6. 離線 Session ---

#[pyclass]
pub struct OfflineSession {
    state:        GameState,
    char_configs: Vec<CharConfig>,
}

#[pymethods]
impl OfflineSession {
    #[new]
    fn new(num_players: usize) -> Self {
        let spawn_points = [(200000, 300000), (824000, 300000), (200000, 450000), (824000, 450000)];
        let players = (0..num_players).map(|i| {
            let mut p = Player::new();
            if i < spawn_points.len() { p.x = spawn_points[i].0; p.y = spawn_points[i].1; }
            p
        }).collect();
        let configs = (0..5).map(|_| CharConfig::default()).collect();
        OfflineSession { state: GameState { players, frame: 0, entities: Vec::new() }, char_configs: configs }
    }

    fn set_physics_config(
        &mut self, char_type: usize,
        gravity: i32, jump_impulse: i32, walk_speed_x: i32, walk_speed_y: i32, hitstop_frames: u32,
        max_hp: i32, max_mp: i32,
        hurt_front: i32, hurt_half_w: i32, hurt_half_h: i32, hurt_z_offset: i32,
    ) {
        do_set_physics_config(
            &mut self.char_configs, &mut self.state.players, char_type,
            gravity, jump_impulse, walk_speed_x, walk_speed_y, hitstop_frames,
            max_hp, max_mp, hurt_front, hurt_half_w, hurt_half_h, hurt_z_offset,
        );
    }

    #[allow(clippy::too_many_arguments)]
    fn set_ability(
        &mut self, char_type: usize, slot_idx: usize,
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
        do_set_ability(
            &mut self.char_configs, char_type, slot_idx,
            trigger_button, trigger_context, state_id,
            mp_cost, timer, dmg, front, half_w, depth, half_h, z_offset,
            kb_vx, kb_vz, kb_timer,
            melee_enabled, hit_start, hit_end,
            damage_absorb, hp_regen_per_tick, on_hit_hp_restore,
            projectile_vx, projectile_lifetime, spawn_timer,
            entity_spawn_offset, entity_spawn_z_offset,
            spawn_entity, dash_vx, dash_tick, is_skill,
        );
    }

    fn advance(&mut self, inputs: Vec<u8>) {
        let ggrs_style: Vec<(u8, InputStatus)> = inputs.into_iter()
            .map(|i| (i, InputStatus::Confirmed)).collect();
        perform_tick(&mut self.state, &ggrs_style, &self.char_configs);
    }

    fn get_player(&self, id: usize) -> PyResult<Player> {
        self.state.players.get(id).cloned().ok_or_else(|| PyIndexError::new_err("OOR"))
    }

    fn set_player(&mut self, id: usize, player: Player) -> PyResult<()> {
        self.state.players.get_mut(id).map(|p| *p = player)
            .ok_or_else(|| PyIndexError::new_err("OOR"))
    }

    fn get_entity_count(&self) -> usize { self.state.entities.len() }

    fn get_entity(&self, id: usize) -> PyResult<EntityView> {
        self.state.entities.get(id).map(|e| EntityView {
            owner_id: e.owner_id, character_type: e.character_type,
            ability_state_id: e.ability_state_id,
            x: e.x, y: e.y, z: e.z, vx: e.vx, lifetime: e.lifetime, is_skill: e.is_skill,
        }).ok_or_else(|| PyIndexError::new_err("Entity OOR"))
    }

    fn current_frame(&self) -> i32 { self.state.frame }
    fn is_synchronized(&self) -> bool { true }
}

// --- 7. GGRS 連線 Session ---

#[pyclass(unsendable)]
pub struct GGRSSession {
    session:       P2PSession<BattleConfig>,
    current_state: GameState,
    local_player_id: usize,
    char_configs:  Vec<CharConfig>,
}

#[pymethods]
impl GGRSSession {
    #[new]
    fn new(local_player_id: usize, num_players: usize, port: u16, remotes: Vec<(usize, String, u16)>) -> PyResult<Self> {
        let socket = UdpNonBlockingSocket::bind_to_port(port)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        let mut builder = SessionBuilder::<BattleConfig>::new()
            .with_num_players(num_players).with_fps(60).unwrap();
        builder = builder.add_player(PlayerType::Local, local_player_id).unwrap();
        for (id, ip, p) in remotes {
            if id != local_player_id {
                let addr: SocketAddr = format!("{}:{}", ip, p).parse()
                    .map_err(|e: std::net::AddrParseError| PyRuntimeError::new_err(e.to_string()))?;
                builder = builder.add_player(PlayerType::Remote(addr), id).unwrap();
            }
        }
        let session = builder.start_p2p_session(socket)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        let spawn_points = [(200000, 300000), (824000, 300000), (200000, 450000), (824000, 450000)];
        let players = (0..num_players).map(|i| {
            let mut p = Player::new();
            if i < spawn_points.len() { p.x = spawn_points[i].0; p.y = spawn_points[i].1; }
            p
        }).collect();
        let configs = (0..5).map(|_| CharConfig::default()).collect();
        Ok(GGRSSession {
            session,
            current_state: GameState { players, frame: 0, entities: Vec::new() },
            local_player_id,
            char_configs: configs,
        })
    }

    fn set_physics_config(
        &mut self, char_type: usize,
        gravity: i32, jump_impulse: i32, walk_speed_x: i32, walk_speed_y: i32, hitstop_frames: u32,
        max_hp: i32, max_mp: i32,
        hurt_front: i32, hurt_half_w: i32, hurt_half_h: i32, hurt_z_offset: i32,
    ) {
        do_set_physics_config(
            &mut self.char_configs, &mut self.current_state.players, char_type,
            gravity, jump_impulse, walk_speed_x, walk_speed_y, hitstop_frames,
            max_hp, max_mp, hurt_front, hurt_half_w, hurt_half_h, hurt_z_offset,
        );
    }

    #[allow(clippy::too_many_arguments)]
    fn set_ability(
        &mut self, char_type: usize, slot_idx: usize,
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
        do_set_ability(
            &mut self.char_configs, char_type, slot_idx,
            trigger_button, trigger_context, state_id,
            mp_cost, timer, dmg, front, half_w, depth, half_h, z_offset,
            kb_vx, kb_vz, kb_timer,
            melee_enabled, hit_start, hit_end,
            damage_absorb, hp_regen_per_tick, on_hit_hp_restore,
            projectile_vx, projectile_lifetime, spawn_timer,
            entity_spawn_offset, entity_spawn_z_offset,
            spawn_entity, dash_vx, dash_tick, is_skill,
        );
    }

    fn advance(&mut self, local_input: u8) -> PyResult<()> {
        self.session.poll_remote_clients();
        if self.session.current_state() == SessionState::Running {
            self.session.add_local_input(self.local_player_id, local_input).ok();
            match self.session.advance_frame() {
                Ok(requests) => self.handle_requests(requests),
                _ => {}
            }
        }
        Ok(())
    }

    fn get_player(&self, id: usize) -> PyResult<Player> {
        self.current_state.players.get(id).cloned().ok_or_else(|| PyIndexError::new_err("OOR"))
    }

    fn set_player(&mut self, id: usize, player: Player) -> PyResult<()> {
        self.current_state.players.get_mut(id).map(|p| *p = player)
            .ok_or_else(|| PyIndexError::new_err("OOR"))
    }

    fn get_entity_count(&self) -> usize { self.current_state.entities.len() }

    fn get_entity(&self, id: usize) -> PyResult<EntityView> {
        self.current_state.entities.get(id).map(|e| EntityView {
            owner_id: e.owner_id, character_type: e.character_type,
            ability_state_id: e.ability_state_id,
            x: e.x, y: e.y, z: e.z, vx: e.vx, lifetime: e.lifetime, is_skill: e.is_skill,
        }).ok_or_else(|| PyIndexError::new_err("Entity OOR"))
    }

    fn is_synchronized(&self) -> bool { self.session.current_state() == SessionState::Running }
    fn current_frame(&self) -> i32 { self.session.current_frame() }
}

impl GGRSSession {
    fn handle_requests(&mut self, requests: Vec<GgrsRequest<BattleConfig>>) {
        let configs = self.char_configs.clone();
        for req in requests {
            match req {
                GgrsRequest::AdvanceFrame { inputs } => {
                    perform_tick(&mut self.current_state, &inputs, &configs);
                }
                GgrsRequest::SaveGameState { cell, frame } => {
                    cell.save(frame, Some(self.current_state.clone()), None);
                }
                GgrsRequest::LoadGameState { cell, .. } => {
                    self.current_state = cell.load().unwrap_or_default();
                }
            }
        }
    }
}

// --- 8. 模組註冊 ---

#[pyfunction]
fn decrypt_payload(payload: String, key: &[u8]) -> PyResult<String> {
    let data = general_purpose::STANDARD.decode(payload)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    let (nonce_bytes, ciphertext) = data.split_at(12);
    let cipher = ChaCha20Poly1305::new(Key::from_slice(key));
    let plaintext = cipher.decrypt(Nonce::from_slice(nonce_bytes), ciphertext)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    String::from_utf8(plaintext).map_err(|e| PyRuntimeError::new_err(e.to_string()))
}

#[pyfunction]
fn hello_from_rust() -> PyResult<String> { Ok("Hello from BattleLite Rust Core!".to_string()) }

#[pymodule]
fn battlelite_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(hello_from_rust, m)?)?;
    m.add_function(wrap_pyfunction!(decrypt_payload, m)?)?;
    m.add_class::<Player>()?;
    m.add_class::<EntityView>()?;
    m.add_class::<OfflineSession>()?;
    m.add_class::<GGRSSession>()?;
    m.add("STATE_IDLE",  STATE_IDLE)?;
    m.add("STATE_WALK",  STATE_WALK)?;
    m.add("STATE_HURT",  STATE_HURT)?;
    m.add("STATE_DEAD",  STATE_DEAD)?;
    Ok(())
}
