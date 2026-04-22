use pyo3::prelude::*;
use pyo3::exceptions::{PyRuntimeError, PyIndexError};
use ggrs::{Config, P2PSession, PlayerType, SessionBuilder, InputStatus, GgrsRequest, UdpNonBlockingSocket, SessionState};
use std::net::SocketAddr;

use chacha20poly1305::{ChaCha20Poly1305, Key, Nonce, KeyInit, aead::Aead};
use base64::{engine::general_purpose, Engine as _};

// --- 1. 常數定義 ---
const GRAVITY: i32 = 400;
const JUMP_IMPULSE: i32 = 9000;
const WALK_SPEED_X: i32 = 5000;
const WALK_SPEED_Y: i32 = 3000;

const CHAR_WIDTH: i32 = 30000;
const CHAR_DEPTH: i32 = 15000;
const ATK_DEPTH_REACH: i32 = 25000;

const STATE_IDLE: u8 = 0;
const STATE_WALK: u8 = 1;
const STATE_ATTACK: u8 = 2;
const STATE_HURT: u8 = 3;
const STATE_SKILL: u8 = 4;

const MAX_HP: i32 = 100000;
const MAX_MP: i32 = 50000;
const MP_REGEN: i32 = 50;
const SKILL_COST: i32 = 20000;

const INPUT_RIGHT: u8  = 1 << 0;
const INPUT_LEFT: u8   = 1 << 1;
const INPUT_UP: u8     = 1 << 2;
const INPUT_DOWN: u8   = 1 << 3;
const INPUT_JUMP: u8   = 1 << 4;
const INPUT_ATTACK: u8 = 1 << 5;
const INPUT_SKILL: u8  = 1 << 6;

// 角色種類
const CHAR_TYPE_KNIGHT: u8 = 0;
const CHAR_TYPE_MAGE: u8   = 1;

// 投擲物參數
const PROJECTILE_VX: i32      = 15000; // 每幀橫向移動量
const PROJECTILE_LIFETIME: u32 = 60;   // 存活幀數（1 秒）
const ENTITY_HIT_RADIUS: i32  = 20000; // 碰撞半徑
// 法師技能在 timer==35 時（5 幀預備動作後）生成投擲物
const MAGE_SPAWN_TIMER: u32 = 35;

// --- 2. 物理實體 ---

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
    #[pyo3(get, set)] pub character_type: u8,  // 0=Knight  1=Mage
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

    fn check_attack_hit(&self, other: &Player) -> bool {
        let is_skill = self.state == STATE_SKILL;
        let atk_offset_x = if self.facing_right {
            if is_skill { 45000 } else { 30000 }
        } else {
            if is_skill { -45000 } else { -30000 }
        };
        let atk_w = if is_skill { 35000 } else { 20000 };
        let atk_d = if is_skill { 40000 } else { ATK_DEPTH_REACH };
        let atk_h = if is_skill { 40000 } else { 5000 };

        let dx = (self.x + atk_offset_x - other.x).abs();
        let dy = (self.y - other.y).abs();
        let dz = (self.z - other.z).abs();
        dx < (atk_w + CHAR_WIDTH / 2) && dy < atk_d && dz < atk_h
    }

    fn update(&mut self) {
        if self.timer > 0 {
            self.timer -= 1;
            if self.timer == 0 { self.state = STATE_IDLE; }
        }
        if self.mp < MAX_MP {
            self.mp += MP_REGEN;
            if self.mp > MAX_MP { self.mp = MAX_MP; }
        }
        if self.z > 0 || self.vz > 0 { self.vz -= GRAVITY; }
        // ATTACK/SKILL 鎖住位移；HURT 允許擊飛移動
        if self.state != STATE_ATTACK && self.state != STATE_SKILL {
            self.x += self.vx;
            self.y += self.vy;
        }
        // HURT 狀態空氣阻力，每幀衰減 10%
        if self.state == STATE_HURT {
            self.vx = self.vx * 9 / 10;
            self.vy = self.vy * 9 / 10;
        }
        self.z += self.vz;
        if self.z <= 0 {
            self.z = 0;
            self.vz = 0;
            // 落地加強摩擦
            if self.state == STATE_HURT {
                self.vx /= 2;
                self.vy /= 2;
            }
        }
    }
}

// --- 3. 實體系統 ---

#[derive(Clone, Default, Debug)]
pub struct Entity {
    pub owner_id: usize,
    pub x: i32,
    pub y: i32,
    pub z: i32,
    pub vx: i32,
    pub vy: i32,
    pub lifetime: u32,
}

/// Python 可讀的投擲物快照（唯讀）
#[pyclass]
#[derive(Clone, Debug)]
pub struct EntityView {
    #[pyo3(get)] pub owner_id: usize,
    #[pyo3(get)] pub x: i32,
    #[pyo3(get)] pub y: i32,
    #[pyo3(get)] pub z: i32,
    #[pyo3(get)] pub lifetime: u32,
}

// --- 4. 遊戲狀態與共用邏輯 ---

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

fn perform_tick(state: &mut GameState, inputs: &[(u8, InputStatus)]) {
    state.frame += 1;

    // 1. 玩家輸入與狀態推進，同時收集新增實體指令
    let mut spawn_queue: Vec<Entity> = Vec::new();

    for (i, (input, status)) in inputs.iter().enumerate() {
        if i >= state.players.len() || *status == InputStatus::Disconnected { continue; }
        let p = &mut state.players[i];

        if p.state == STATE_IDLE || p.state == STATE_WALK {
            p.vx = 0; p.vy = 0;
            if input & INPUT_RIGHT != 0 { p.vx += WALK_SPEED_X; p.state = STATE_WALK; p.facing_right = true; }
            if input & INPUT_LEFT  != 0 { p.vx -= WALK_SPEED_X; p.state = STATE_WALK; p.facing_right = false; }
            if input & INPUT_DOWN  != 0 { p.vy += WALK_SPEED_Y; p.state = STATE_WALK; }
            if input & INPUT_UP    != 0 { p.vy -= WALK_SPEED_Y; p.state = STATE_WALK; }
            if p.vx == 0 && p.vy == 0 { p.state = STATE_IDLE; }
            if input & INPUT_JUMP   != 0 && p.z == 0 { p.vz = JUMP_IMPULSE; }
            if input & INPUT_ATTACK != 0 { p.state = STATE_ATTACK; p.timer = 20; p.vx = 0; p.vy = 0; }
            if input & INPUT_SKILL  != 0 && p.mp >= SKILL_COST {
                p.state = STATE_SKILL; p.timer = 40; p.mp -= SKILL_COST; p.vx = 0; p.vy = 0;
            }
        }

        // 法師在技能第 5 幀（timer==35）生成投擲物
        if p.state == STATE_SKILL && p.timer == MAGE_SPAWN_TIMER && p.character_type == CHAR_TYPE_MAGE {
            let vx = if p.facing_right { PROJECTILE_VX } else { -PROJECTILE_VX };
            spawn_queue.push(Entity {
                owner_id: i,
                x: p.x, y: p.y, z: p.z,
                vx, vy: 0,
                lifetime: PROJECTILE_LIFETIME,
            });
        }

        p.update();
    }

    // 2. 現有實體移動並倒數生命週期，移除過期實體
    state.entities.retain_mut(|e| {
        e.x += e.vx;
        e.y += e.vy;
        e.lifetime = e.lifetime.saturating_sub(1);
        e.lifetime > 0
    });

    // 3. 加入本幀新生成的實體
    state.entities.extend(spawn_queue);

    // 4. 實體與玩家碰撞判定
    struct EntityHit { victim: usize, vx: i32 }
    let mut entity_hits: Vec<EntityHit> = Vec::new();
    for e in &state.entities {
        for j in 0..state.players.len() {
            if e.owner_id == j { continue; }
            let victim = &state.players[j];
            if victim.state == STATE_HURT { continue; }
            let dx = (e.x - victim.x).abs();
            let dy = (e.y - victim.y).abs();
            if dx < ENTITY_HIT_RADIUS + CHAR_WIDTH / 2
                && dy < ENTITY_HIT_RADIUS + CHAR_DEPTH / 2 {
                // 擊飛方向與投擲物行進方向一致
                let kb_vx = if e.vx >= 0 { 6000i32 } else { -6000i32 };
                entity_hits.push(EntityHit { victim: j, vx: kb_vx });
            }
        }
    }
    for hit in entity_hits {
        let victim = &mut state.players[hit.victim];
        victim.state = STATE_HURT;
        victim.timer = 25;
        victim.vx = hit.vx;
        victim.vz = 3000;
        victim.hp -= 8000;
    }

    // 5. 玩家近戰判定，帶方向性 knockback
    let num_players = state.players.len();
    for i in 0..num_players {
        let atk_info = state.players[i].clone();
        let is_attack = atk_info.state == STATE_ATTACK && atk_info.timer == 15;
        let is_skill  = atk_info.state == STATE_SKILL
            && atk_info.character_type == CHAR_TYPE_KNIGHT
            && atk_info.timer > 10;
        if !is_attack && !is_skill { continue; }

        // 不同招式的擊飛參數
        let (kb_vz, kb_timer, kb_dmg) = if is_skill {
            (6000i32, 40u32, 15000i32)  // 技能：高飛、長硬直、高傷
        } else {
            (4000i32, 30u32, 10000i32)  // 普攻
        };
        let kb_vx = if atk_info.facing_right { 8000i32 } else { -8000i32 };

        for j in 0..num_players {
            if i == j { continue; }
            let victim = &mut state.players[j];
            if victim.state == STATE_HURT { continue; }
            if atk_info.check_attack_hit(victim) {
                victim.state = STATE_HURT;
                victim.timer = kb_timer;
                victim.vx = kb_vx;
                victim.vz = kb_vz;
                victim.hp -= kb_dmg;
            }
        }
    }
}

// --- 5. 離線 Session ---

#[pyclass]
pub struct OfflineSession {
    state: GameState,
}

#[pymethods]
impl OfflineSession {
    #[new]
    fn new(num_players: usize) -> Self {
        let spawn_points = [(200000, 300000), (600000, 300000), (200000, 450000), (600000, 450000)];
        let players = (0..num_players).map(|i| {
            let mut p = Player::new();
            if i < spawn_points.len() { p.x = spawn_points[i].0; p.y = spawn_points[i].1; }
            p
        }).collect();
        OfflineSession { state: GameState { players, frame: 0, entities: Vec::new() } }
    }

    fn advance(&mut self, inputs: Vec<u8>) {
        let ggrs_style: Vec<(u8, InputStatus)> = inputs.into_iter()
            .map(|i| (i, InputStatus::Confirmed)).collect();
        perform_tick(&mut self.state, &ggrs_style);
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
            owner_id: e.owner_id, x: e.x, y: e.y, z: e.z, lifetime: e.lifetime,
        }).ok_or_else(|| PyIndexError::new_err("Entity OOR"))
    }

    fn current_frame(&self) -> i32 { self.state.frame }
    fn is_synchronized(&self) -> bool { true }
}

// --- 6. GGRS 連線 Session ---

#[pyclass(unsendable)]
pub struct GGRSSession {
    session: P2PSession<BattleConfig>,
    current_state: GameState,
    local_player_id: usize,
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
        let spawn_points = [(200000, 300000), (600000, 300000), (200000, 450000), (600000, 450000)];
        let players = (0..num_players).map(|i| {
            let mut p = Player::new();
            if i < spawn_points.len() { p.x = spawn_points[i].0; p.y = spawn_points[i].1; }
            p
        }).collect();
        Ok(GGRSSession {
            session,
            current_state: GameState { players, frame: 0, entities: Vec::new() },
            local_player_id,
        })
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
            owner_id: e.owner_id, x: e.x, y: e.y, z: e.z, lifetime: e.lifetime,
        }).ok_or_else(|| PyIndexError::new_err("Entity OOR"))
    }

    fn is_synchronized(&self) -> bool { self.session.current_state() == SessionState::Running }
    fn current_frame(&self) -> i32 { self.session.current_frame() }
}

impl GGRSSession {
    fn handle_requests(&mut self, requests: Vec<GgrsRequest<BattleConfig>>) {
        for req in requests {
            match req {
                GgrsRequest::AdvanceFrame { inputs } => {
                    perform_tick(&mut self.current_state, &inputs);
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

// --- 7. 模組註冊 ---

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
