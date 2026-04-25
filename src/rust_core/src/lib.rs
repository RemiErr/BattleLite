use pyo3::prelude::*;
use pyo3::exceptions::{PyRuntimeError, PyIndexError};
use ggrs::{Config, P2PSession, PlayerType, SessionBuilder, InputStatus, GgrsRequest, UdpNonBlockingSocket, SessionState};
use std::net::SocketAddr;

use chacha20poly1305::{ChaCha20Poly1305, Key, Nonce, KeyInit, aead::Aead};
use base64::{engine::general_purpose, Engine as _};

// --- 1. 全域常數（狀態機、輸入遮罩，不受角色影響）---
const CHAR_WIDTH: i32 = 30000;
const ATK_DEPTH_REACH: i32 = 25000;

const MAX_HP: i32 = 100000;
const MAX_MP: i32 = 50000;
const MP_REGEN: i32 = 50;
const SKILL_COST: i32 = 20000;

const STATE_IDLE: u8 = 0;
const STATE_WALK: u8 = 1;
const STATE_ATTACK: u8 = 2;
const STATE_HURT: u8 = 3;
const STATE_SKILL: u8 = 4;

const INPUT_RIGHT: u8  = 1 << 0;
const INPUT_LEFT: u8   = 1 << 1;
const INPUT_UP: u8     = 1 << 2;
const INPUT_DOWN: u8   = 1 << 3;
const INPUT_JUMP: u8   = 1 << 4;
const INPUT_ATTACK: u8 = 1 << 5;
const INPUT_SKILL: u8  = 1 << 6;

// --- 2. 角色設定（session 層持有，不進 GameState）---
//
// 所有距離單位皆為遊戲單位（px × 1000）。
// atk_front / skl_front：攻擊框中心距角色中心的距離（朝面向方向為正）。
// atk_half_w / skl_half_w：攻擊框半寬。
// atk_half_h / skl_half_h：攻擊框半高（z 軸容許誤差）。
// atk_depth / skl_depth：攻擊框深度（y 軸容許誤差）。
#[derive(Clone, Debug)]
struct CharConfig {
    // 物理常數（per-character，透過 set_char_config 傳入）
    gravity:        i32,
    jump_impulse:   i32,
    walk_speed_x:   i32,
    walk_speed_y:   i32,
    hitstop_frames: u32,
    max_hp:       i32,
    max_mp:       i32,
    skill_cost:   i32,
    atk_dmg:      i32,
    skill_dmg:    i32,
    atk_front:    i32,
    atk_half_w:   i32,
    atk_depth:    i32,
    atk_half_h:   i32,
    atk_z_offset: i32,
    skl_front:    i32,
    skl_half_w:   i32,
    skl_depth:    i32,
    skl_half_h:   i32,
    skl_z_offset: i32,
    atk_kb_vx:    i32,
    atk_kb_vz:    i32,
    atk_kb_timer: u32,
    skl_kb_vx:    i32,
    skl_kb_vz:    i32,
    skl_kb_timer: u32,
    hurt_front:   i32,
    hurt_half_w:  i32,
    hurt_half_h:  i32,
    hurt_z_offset: i32,
    // SKILL 投射物（skl_projectile_vx == 0 表示此角色技能無投射物）
    skl_projectile_vx:       i32,
    skl_projectile_lifetime: u32,
    skl_spawn_timer:         u32,
    skl_entity_spawn_offset:   i32, // SKILL entity X 發射偏移
    skl_entity_spawn_z_offset: i32, // SKILL entity Z 高度偏移
    atk_entity_spawn_offset:   i32, // ATTACK entity X 發射偏移
    atk_entity_spawn_z_offset: i32, // ATTACK entity Z 高度偏移
    atk_timer:           u32,
    skl_timer:           u32,
    // ATTACK 投射物（atk_projectile_vx == 0 表示此角色的 ATTACK 是近戰）
    atk_projectile_vx:       i32,
    atk_projectile_lifetime: u32,
    atk_spawn_timer:         u32,
    // 近戰啟用旗標（可與投射物獨立設定）
    atk_melee_enabled: bool,
    skl_melee_enabled: bool,
    // 護盾：每次命中吸收的傷害量（0 = 無護盾）
    skl_damage_absorb: i32,
    // 近戰判定視窗（ticks，elapsed = timer_max - timer）
    atk_hit_start: u32,
    atk_hit_end:   u32,
    skl_hit_start: u32,
    skl_hit_end:   u32,
    // ATTACK 衝刺（0 = 無衝刺）
    atk_dash_vx:   i32,  // 衝刺距離（game unit，正值 = 朝面向方向）
    atk_dash_tick: u32,  // elapsed ticks 到此值時觸發
    // 強制生成 SKILL entity（即使 skl_projectile_vx == 0，用於 AOE 技能）
    skl_spawn_entity: bool,
}

impl Default for CharConfig {
    fn default() -> Self {
        CharConfig {
            gravity:        400,
            jump_impulse:   9000,
            walk_speed_x:   5000,
            walk_speed_y:   3000,
            hitstop_frames: 4,
            max_hp:       MAX_HP,
            max_mp:       MAX_MP,
            skill_cost:   SKILL_COST,
            atk_dmg:      10000,
            skill_dmg:    15000,
            atk_front:    30000,
            atk_half_w:   20000,
            atk_depth:    ATK_DEPTH_REACH,
            atk_half_h:   5000,
            atk_z_offset: 0,
            skl_front:    45000,
            skl_half_w:   35000,
            skl_depth:    40000,
            skl_half_h:   40000,
            skl_z_offset: 0,
            atk_kb_vx:    8000,
            atk_kb_vz:    4000,
            atk_kb_timer: 30,
            skl_kb_vx:    8000,
            skl_kb_vz:    6000,
            skl_kb_timer: 40,
            hurt_front:   0,
            hurt_half_w:  CHAR_WIDTH / 2,
            hurt_half_h:  50000,
            hurt_z_offset: 0,
            skl_projectile_vx:       0,
            skl_projectile_lifetime: 60,
            skl_spawn_timer:         35,
            skl_entity_spawn_offset:   0,
            skl_entity_spawn_z_offset: 0,
            atk_entity_spawn_offset:   0,
            atk_entity_spawn_z_offset: 0,
            atk_timer:               20,
            skl_timer:           40,
            atk_projectile_vx:       0,
            atk_projectile_lifetime: 30,
            atk_spawn_timer:         10,
            atk_melee_enabled: true,
            skl_melee_enabled: true,
            skl_damage_absorb: 0,
            atk_hit_start: 0,
            atk_hit_end:   9999,
            skl_hit_start: 0,
            skl_hit_end:   9999,
            atk_dash_vx:   0,
            atk_dash_tick: 0,
            skl_spawn_entity: false,
        }
    }
}

fn get_cfg(configs: &[CharConfig], char_type: u8) -> CharConfig {
    configs.get(char_type as usize).cloned().unwrap_or_default()
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

    // 保留 Python 可呼叫版本，使用預設 config（測試相容用）
    fn check_attack_hit(&self, other: &Player) -> bool {
        check_attack_hit_cfg(self, other, &CharConfig::default(), &CharConfig::default())
    }

    // Python 相容用（測試直接呼叫），使用 CharConfig 預設值
    fn update(&mut self) {
        self.update_internal(CharConfig::default().gravity);
    }
}

impl Player {
    fn update_internal(&mut self, gravity: i32) {
        if self.hitstop > 0 {
            self.hitstop -= 1;
            return;
        }
        if self.timer > 0 {
            self.timer -= 1;
            if self.timer == 0 { self.state = STATE_IDLE; }
        }
        if self.z > 0 || self.vz > 0 { self.vz -= gravity; }
        if self.state != STATE_ATTACK && self.state != STATE_SKILL {
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

// 使用 CharConfig 的碰撞判定（perform_tick 內部使用）
// atk_cfg：攻擊者設定（決定攻擊框大小與位置）
// vic_cfg：受害者設定（決定 hurt_box 大小）
fn check_attack_hit_cfg(attacker: &Player, victim: &Player, atk_cfg: &CharConfig, vic_cfg: &CharConfig) -> bool {
    let is_skill = attacker.state == STATE_SKILL;
    let (front, half_w, depth, half_h, atk_zo) = if is_skill {
        (atk_cfg.skl_front, atk_cfg.skl_half_w, atk_cfg.skl_depth, atk_cfg.skl_half_h, atk_cfg.skl_z_offset)
    } else {
        (atk_cfg.atk_front, atk_cfg.atk_half_w, atk_cfg.atk_depth, atk_cfg.atk_half_h, atk_cfg.atk_z_offset)
    };
    // 攻擊框中心：攻擊者位置 + 面向偏移（ox 決定）
    let atk_offset_x = if attacker.facing_right { front } else { -front };
    let atk_center_x = attacker.x + atk_offset_x;
    let atk_center_z = attacker.z + atk_zo;
    // 受害者身體框中心：受害者位置 + hurt_front 偏移（hurt ox 決定）
    let vic_offset_x = if victim.facing_right { vic_cfg.hurt_front } else { -vic_cfg.hurt_front };
    let vic_center_x = victim.x + vic_offset_x;
    let vic_center_z = victim.z + vic_cfg.hurt_z_offset;

    let dx = (atk_center_x - vic_center_x).abs();
    let dy = (attacker.y - victim.y).abs();
    let dz = (atk_center_z - vic_center_z).abs();
    dx < (half_w + vic_cfg.hurt_half_w) && dy < depth && dz < (half_h + vic_cfg.hurt_half_h)
}

// --- 4. 實體系統 ---

#[derive(Clone, Default, Debug)]
pub struct Entity {
    pub owner_id: usize,
    pub character_type: u8,
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
    #[pyo3(get)] pub owner_id: usize,
    #[pyo3(get)] pub character_type: u8,
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
    pub players: Vec<Player>,
    pub frame: i32,
    pub entities: Vec<Entity>,
}

pub struct BattleConfig;
impl Config for BattleConfig {
    type Input = u8;
    type State = GameState;
    type Address = SocketAddr;
}

fn perform_tick(state: &mut GameState, inputs: &[(u8, InputStatus)], configs: &[CharConfig]) {
    state.frame += 1;

    let mut spawn_queue: Vec<Entity> = Vec::new();

    for (i, (input, status)) in inputs.iter().enumerate() {
        if i >= state.players.len() || *status == InputStatus::Disconnected { continue; }
        let p = &mut state.players[i];
        let pcfg = get_cfg(configs, p.character_type);

        if p.state == STATE_IDLE || p.state == STATE_WALK {
            p.vx = 0; p.vy = 0;
            if input & INPUT_RIGHT != 0 { p.vx += pcfg.walk_speed_x; p.state = STATE_WALK; p.facing_right = true; }
            if input & INPUT_LEFT  != 0 { p.vx -= pcfg.walk_speed_x; p.state = STATE_WALK; p.facing_right = false; }
            if input & INPUT_DOWN  != 0 { p.vy += pcfg.walk_speed_y; p.state = STATE_WALK; }
            if input & INPUT_UP    != 0 { p.vy -= pcfg.walk_speed_y; p.state = STATE_WALK; }
            if p.vx == 0 && p.vy == 0 { p.state = STATE_IDLE; }
            if input & INPUT_JUMP   != 0 && p.z == 0 { p.vz = pcfg.jump_impulse; }
            if input & INPUT_ATTACK != 0 { p.state = STATE_ATTACK; p.timer = pcfg.atk_timer; p.vx = 0; p.vy = 0; }
            if input & INPUT_SKILL  != 0 && p.mp >= pcfg.skill_cost {
                p.state = STATE_SKILL; p.timer = pcfg.skl_timer; p.mp -= pcfg.skill_cost; p.vx = 0; p.vy = 0;
            }
        }

        if p.state == STATE_SKILL && p.timer == pcfg.skl_spawn_timer && (pcfg.skl_projectile_vx != 0 || pcfg.skl_spawn_entity) {
            let vx = if p.facing_right { pcfg.skl_projectile_vx } else { -pcfg.skl_projectile_vx };
            let spawn_x = if p.facing_right { p.x + pcfg.skl_entity_spawn_offset } else { p.x - pcfg.skl_entity_spawn_offset };
            spawn_queue.push(Entity {
                owner_id: i,
                character_type: p.character_type,
                x: spawn_x, y: p.y, z: p.z + pcfg.skl_entity_spawn_z_offset,
                vx, vy: 0,
                lifetime: pcfg.skl_projectile_lifetime,
                is_skill: true,
            });
        }
        if p.state == STATE_ATTACK && p.timer == pcfg.atk_spawn_timer && pcfg.atk_projectile_vx != 0 {
            let vx = if p.facing_right { pcfg.atk_projectile_vx } else { -pcfg.atk_projectile_vx };
            let spawn_x = if p.facing_right { p.x + pcfg.atk_entity_spawn_offset } else { p.x - pcfg.atk_entity_spawn_offset };
            spawn_queue.push(Entity {
                owner_id: i,
                character_type: p.character_type,
                x: spawn_x, y: p.y, z: p.z + pcfg.atk_entity_spawn_z_offset,
                vx, vy: 0,
                lifetime: pcfg.atk_projectile_lifetime,
                is_skill: false,
            });
        }

        if p.state == STATE_ATTACK && pcfg.atk_dash_vx != 0 {
            let elapsed = pcfg.atk_timer.saturating_sub(p.timer);
            if elapsed == pcfg.atk_dash_tick {
                let dash = if p.facing_right { pcfg.atk_dash_vx } else { -pcfg.atk_dash_vx };
                p.x += dash;
            }
        }

        p.update_internal(pcfg.gravity);
        if p.mp < pcfg.max_mp {
            p.mp += MP_REGEN;
            if p.mp > pcfg.max_mp { p.mp = pcfg.max_mp; }
        }
        if p.hp > pcfg.max_hp { p.hp = pcfg.max_hp; }
    }

    state.entities.retain_mut(|e| {
        e.x += e.vx;
        e.y += e.vy;
        e.lifetime = e.lifetime.saturating_sub(1);
        e.lifetime > 0
    });

    state.entities.extend(spawn_queue);

    // 投擲物與玩家碰撞
    struct EntityHit { victim: usize, vx: i32, vz: i32, timer: u32, damage: i32 }
    let mut entity_hits: Vec<EntityHit> = Vec::new();
    for e in &state.entities {
        let atk_cfg = get_cfg(configs, e.character_type);
        for j in 0..state.players.len() {
            if e.owner_id == j { continue; }
            let victim = &state.players[j];
            if victim.state == STATE_HURT { continue; }
            let vic_cfg = get_cfg(configs, victim.character_type);
            let (entity_half_w, entity_depth, entity_half_h, entity_z_off) = if e.is_skill {
                (atk_cfg.skl_half_w, atk_cfg.skl_depth, atk_cfg.skl_half_h, atk_cfg.skl_z_offset)
            } else {
                (atk_cfg.atk_half_w, atk_cfg.atk_depth, atk_cfg.atk_half_h, atk_cfg.atk_z_offset)
            };
            let vic_off_x = if victim.facing_right { vic_cfg.hurt_front } else { -vic_cfg.hurt_front };
            let dx = (e.x - (victim.x + vic_off_x)).abs();
            let dy = (e.y - victim.y).abs();
            let dz = (e.z + entity_z_off - (victim.z + vic_cfg.hurt_z_offset)).abs();
            if dx < entity_half_w + vic_cfg.hurt_half_w
                && dy < entity_depth
                && dz < entity_half_h + vic_cfg.hurt_half_h {
                let (kb_vx_mag, kb_vz, kb_timer, dmg_base, total_lifetime) = if e.is_skill {
                    (atk_cfg.skl_kb_vx, atk_cfg.skl_kb_vz, atk_cfg.skl_kb_timer,
                     atk_cfg.skill_dmg, atk_cfg.skl_projectile_lifetime)
                } else {
                    (atk_cfg.atk_kb_vx, atk_cfg.atk_kb_vz, atk_cfg.atk_kb_timer,
                     atk_cfg.atk_dmg, atk_cfg.atk_projectile_lifetime)
                };
                let kb_vx = if e.vx >= 0 { kb_vx_mag } else { -kb_vx_mag };
                // 距離衰減：lifetime 愈少 = 飛愈遠 = 傷害愈低
                let ratio = e.lifetime as i32 * 1000 / total_lifetime as i32;
                let damage = dmg_base * ratio / 1000;
                entity_hits.push(EntityHit {
                    victim: j,
                    vx: kb_vx,
                    vz: kb_vz,
                    timer: kb_timer,
                    damage,
                });
            }
        }
    }
    for hit in entity_hits {
        let victim = &mut state.players[hit.victim];
        let vic_cfg = get_cfg(configs, victim.character_type);
        if victim.state == STATE_SKILL && vic_cfg.skl_damage_absorb > 0 {
            let dmg = (hit.damage - vic_cfg.skl_damage_absorb).max(0);
            victim.hp = (victim.hp - dmg).max(0);
        } else {
            victim.state = STATE_HURT;
            victim.timer = hit.timer;
            victim.vx = hit.vx;
            victim.vz = hit.vz;
            victim.hp -= hit.damage;
            if victim.hp < 0 { victim.hp = 0; }
        }
    }

    // 玩家近戰判定（使用 CharConfig）
    let num_players = state.players.len();
    for i in 0..num_players {
        let atk_info = state.players[i].clone();
        let atk_cfg = get_cfg(configs, atk_info.character_type);
        let elapsed_atk = atk_cfg.atk_timer.saturating_sub(atk_info.timer);
        let elapsed_skl = atk_cfg.skl_timer.saturating_sub(atk_info.timer);
        let is_attack = atk_info.state == STATE_ATTACK
            && atk_cfg.atk_melee_enabled
            && elapsed_atk >= atk_cfg.atk_hit_start
            && elapsed_atk <= atk_cfg.atk_hit_end;
        let is_skill  = atk_info.state == STATE_SKILL
            && atk_cfg.skl_melee_enabled
            && elapsed_skl >= atk_cfg.skl_hit_start
            && elapsed_skl <= atk_cfg.skl_hit_end;
        if !is_attack && !is_skill { continue; }

        let cfg = atk_cfg;
        let (kb_vz, kb_timer, kb_dmg, kb_vx_mag) = if is_skill {
            (cfg.skl_kb_vz, cfg.skl_kb_timer, cfg.skill_dmg, cfg.skl_kb_vx)
        } else {
            (cfg.atk_kb_vz, cfg.atk_kb_timer, cfg.atk_dmg, cfg.atk_kb_vx)
        };
        let kb_vx = if atk_info.facing_right { kb_vx_mag } else { -kb_vx_mag };

        let mut hit_landed = false;
        for j in 0..num_players {
            if i == j { continue; }
            if state.players[j].state == STATE_HURT { continue; }
            let vic_cfg = get_cfg(configs, state.players[j].character_type);
            if check_attack_hit_cfg(&atk_info, &state.players[j], &cfg, &vic_cfg) {
                let victim = &mut state.players[j];
                if victim.state == STATE_SKILL && vic_cfg.skl_damage_absorb > 0 {
                    let dmg = (kb_dmg - vic_cfg.skl_damage_absorb).max(0);
                    victim.hp = (victim.hp - dmg).max(0);
                } else {
                    victim.state = STATE_HURT;
                    victim.timer = kb_timer;
                    victim.vx = kb_vx;
                    victim.vz = kb_vz;
                    victim.hp -= kb_dmg;
                    victim.hitstop = cfg.hitstop_frames;
                    hit_landed = true;
                }
            }
        }
        if hit_landed {
            state.players[i].hitstop = cfg.hitstop_frames;
        }
    }
}

// --- 6. 離線 Session ---

#[pyclass]
pub struct OfflineSession {
    state: GameState,
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
        let mut configs = Vec::new();
        configs.push(CharConfig::default()); // Knight (0)
        configs.push(CharConfig::default()); // Mage   (1)
        configs.push(CharConfig::default()); // Archer (2)
        configs.push(CharConfig::default()); // Paladin (3)
        configs.push(CharConfig::default()); // Wizard  (4)
        OfflineSession { state: GameState { players, frame: 0, entities: Vec::new() }, char_configs: configs }
    }

    /// 設定指定角色種類的所有碰撞與數值參數。
    /// 所有距離單位為遊戲單位（像素 × 1000）。
    /// 呼叫時機：session 建立後、第一次 advance 前。
    fn set_char_config(
        &mut self, char_type: usize,
        gravity: i32, jump_impulse: i32, walk_speed_x: i32, walk_speed_y: i32, hitstop_frames: u32,
        max_hp: i32, max_mp: i32, skill_cost: i32,
        atk_dmg: i32, skill_dmg: i32,
        atk_front: i32, atk_half_w: i32, atk_depth: i32, atk_half_h: i32, atk_z_offset: i32,
        skl_front: i32, skl_half_w: i32, skl_depth: i32, skl_half_h: i32, skl_z_offset: i32,
        atk_kb_vx: i32, atk_kb_vz: i32, atk_kb_timer: u32,
        skl_kb_vx: i32, skl_kb_vz: i32, skl_kb_timer: u32,
        hurt_front: i32, hurt_half_w: i32, hurt_half_h: i32, hurt_z_offset: i32,
        skl_projectile_vx: i32, skl_projectile_lifetime: u32, skl_spawn_timer: u32,
        skl_entity_spawn_offset: i32, skl_entity_spawn_z_offset: i32,
        atk_entity_spawn_offset: i32, atk_entity_spawn_z_offset: i32,
        atk_timer: u32, skl_timer: u32,
        atk_projectile_vx: i32, atk_projectile_lifetime: u32, atk_spawn_timer: u32,
        atk_melee_enabled: bool, skl_melee_enabled: bool,
        skl_damage_absorb: i32,
        atk_hit_start: u32, atk_hit_end: u32,
        skl_hit_start: u32, skl_hit_end: u32,
        atk_dash_vx: i32, atk_dash_tick: u32,
        skl_spawn_entity: bool,
    ) {
        while self.char_configs.len() <= char_type {
            self.char_configs.push(CharConfig::default());
        }
        self.char_configs[char_type] = CharConfig {
            gravity, jump_impulse, walk_speed_x, walk_speed_y, hitstop_frames,
            max_hp, max_mp, skill_cost, atk_dmg, skill_dmg,
            atk_front, atk_half_w, atk_depth, atk_half_h, atk_z_offset,
            skl_front, skl_half_w, skl_depth, skl_half_h, skl_z_offset,
            atk_kb_vx, atk_kb_vz, atk_kb_timer,
            skl_kb_vx, skl_kb_vz, skl_kb_timer,
            hurt_front, hurt_half_w, hurt_half_h, hurt_z_offset,
            skl_projectile_vx, skl_projectile_lifetime, skl_spawn_timer,
            skl_entity_spawn_offset, skl_entity_spawn_z_offset,
            atk_entity_spawn_offset, atk_entity_spawn_z_offset,
            atk_timer, skl_timer,
            atk_projectile_vx, atk_projectile_lifetime, atk_spawn_timer,
            atk_melee_enabled, skl_melee_enabled,
            skl_damage_absorb,
            atk_hit_start, atk_hit_end,
            skl_hit_start, skl_hit_end,
            atk_dash_vx, atk_dash_tick,
            skl_spawn_entity,
        };
        for p in &mut self.state.players {
            if p.character_type as usize == char_type {
                p.hp = max_hp;
                p.mp = max_mp;
            }
        }
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
            x: e.x, y: e.y, z: e.z, vx: e.vx, lifetime: e.lifetime, is_skill: e.is_skill,
        }).ok_or_else(|| PyIndexError::new_err("Entity OOR"))
    }

    fn current_frame(&self) -> i32 { self.state.frame }
    fn is_synchronized(&self) -> bool { true }
}

// --- 7. GGRS 連線 Session ---

#[pyclass(unsendable)]
pub struct GGRSSession {
    session: P2PSession<BattleConfig>,
    current_state: GameState,
    local_player_id: usize,
    char_configs: Vec<CharConfig>,
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
        let mut configs = Vec::new();
        configs.push(CharConfig::default()); // Knight (0)
        configs.push(CharConfig::default()); // Mage   (1)
        configs.push(CharConfig::default()); // Archer (2)
        configs.push(CharConfig::default()); // Paladin (3)
        configs.push(CharConfig::default()); // Wizard  (4)
        Ok(GGRSSession {
            session,
            current_state: GameState { players, frame: 0, entities: Vec::new() },
            local_player_id,
            char_configs: configs,
        })
    }

    fn set_char_config(
        &mut self, char_type: usize,
        gravity: i32, jump_impulse: i32, walk_speed_x: i32, walk_speed_y: i32, hitstop_frames: u32,
        max_hp: i32, max_mp: i32, skill_cost: i32,
        atk_dmg: i32, skill_dmg: i32,
        atk_front: i32, atk_half_w: i32, atk_depth: i32, atk_half_h: i32, atk_z_offset: i32,
        skl_front: i32, skl_half_w: i32, skl_depth: i32, skl_half_h: i32, skl_z_offset: i32,
        atk_kb_vx: i32, atk_kb_vz: i32, atk_kb_timer: u32,
        skl_kb_vx: i32, skl_kb_vz: i32, skl_kb_timer: u32,
        hurt_front: i32, hurt_half_w: i32, hurt_half_h: i32, hurt_z_offset: i32,
        skl_projectile_vx: i32, skl_projectile_lifetime: u32, skl_spawn_timer: u32,
        skl_entity_spawn_offset: i32, skl_entity_spawn_z_offset: i32,
        atk_entity_spawn_offset: i32, atk_entity_spawn_z_offset: i32,
        atk_timer: u32, skl_timer: u32,
        atk_projectile_vx: i32, atk_projectile_lifetime: u32, atk_spawn_timer: u32,
        atk_melee_enabled: bool, skl_melee_enabled: bool,
        skl_damage_absorb: i32,
        atk_hit_start: u32, atk_hit_end: u32,
        skl_hit_start: u32, skl_hit_end: u32,
        atk_dash_vx: i32, atk_dash_tick: u32,
        skl_spawn_entity: bool,
    ) {
        while self.char_configs.len() <= char_type {
            self.char_configs.push(CharConfig::default());
        }
        self.char_configs[char_type] = CharConfig {
            gravity, jump_impulse, walk_speed_x, walk_speed_y, hitstop_frames,
            max_hp, max_mp, skill_cost, atk_dmg, skill_dmg,
            atk_front, atk_half_w, atk_depth, atk_half_h, atk_z_offset,
            skl_front, skl_half_w, skl_depth, skl_half_h, skl_z_offset,
            atk_kb_vx, atk_kb_vz, atk_kb_timer,
            skl_kb_vx, skl_kb_vz, skl_kb_timer,
            hurt_front, hurt_half_w, hurt_half_h, hurt_z_offset,
            skl_projectile_vx, skl_projectile_lifetime, skl_spawn_timer,
            skl_entity_spawn_offset, skl_entity_spawn_z_offset,
            atk_entity_spawn_offset, atk_entity_spawn_z_offset,
            atk_timer, skl_timer,
            atk_projectile_vx, atk_projectile_lifetime, atk_spawn_timer,
            atk_melee_enabled, skl_melee_enabled,
            skl_damage_absorb,
            atk_hit_start, atk_hit_end,
            skl_hit_start, skl_hit_end,
            atk_dash_vx, atk_dash_tick,
            skl_spawn_entity,
        };
        for p in &mut self.current_state.players {
            if p.character_type as usize == char_type {
                p.hp = max_hp;
                p.mp = max_mp;
            }
        }
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
    Ok(())
}
