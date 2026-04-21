use pyo3::prelude::*;
use pyo3::exceptions::{PyRuntimeError, PyIndexError};
use ggrs::{Config, P2PSession, PlayerType, SessionBuilder, InputStatus, GgrsRequest, UdpNonBlockingSocket, SessionState};
use std::net::SocketAddr;

// 加密庫
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
}

#[pymethods]
impl Player {
    #[new] fn new() -> Self {
        let mut p = Player::default();
        p.facing_right = true; p.hp = MAX_HP; p.mp = MAX_MP;
        p
    }

    fn check_attack_hit(&self, other: &Player) -> bool {
        let is_skill = self.state == STATE_SKILL;
        let atk_offset_x = if self.facing_right { if is_skill { 45000 } else { 30000 } } else { if is_skill { -45000 } else { -30000 } };
        let atk_w = if is_skill { 35000 } else { 20000 };
        let atk_d = if is_skill { 40000 } else { ATK_DEPTH_REACH };
        let atk_h = if is_skill { 40000 } else { 5000 };

        let dx = (self.x + atk_offset_x - other.x).abs();
        let dy = (self.y - other.y).abs();
        let dz = (self.z - other.z).abs();
        dx < (atk_w + (CHAR_WIDTH / 2)) && dy < atk_d && dz < atk_h
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
        if self.state != STATE_ATTACK && self.state != STATE_HURT && self.state != STATE_SKILL {
            self.x += self.vx; self.y += self.vy;
        }
        self.z += self.vz;
        if self.z <= 0 { self.z = 0; self.vz = 0; }
    }
}

// --- 3. 遊戲狀態與共用邏輯 ---

#[derive(Clone, Default, Debug)]
pub struct GameState { pub players: Vec<Player>, pub frame: i32 }

pub struct BattleConfig;
impl Config for BattleConfig {
    type Input = u8;
    type State = GameState;
    type Address = SocketAddr;
}

/// 核心物理模擬邏輯 (全模式共享)
fn perform_tick(state: &mut GameState, inputs: &[(u8, InputStatus)]) {
    state.frame += 1;
    // 1. 處理輸入與狀態更新
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
            if input & INPUT_JUMP != 0 && p.z == 0 { p.vz = JUMP_IMPULSE; }
            if input & INPUT_ATTACK != 0 { p.state = STATE_ATTACK; p.timer = 20; p.vx = 0; p.vy = 0; }
            if input & INPUT_SKILL != 0 && p.mp >= SKILL_COST { p.state = STATE_SKILL; p.timer = 40; p.mp -= SKILL_COST; p.vx = 0; p.vy = 0; }
        }
        p.update();
    }
    // 2. 戰鬥判定
    let num_players = state.players.len();
    for i in 0..num_players {
        let atk_info = state.players[i].clone();
        let is_attacking = (atk_info.state == STATE_ATTACK && atk_info.timer == 15) || (atk_info.state == STATE_SKILL && atk_info.timer > 10);
        if is_attacking {
            for j in 0..num_players {
                if i == j { continue; }
                let victim = &mut state.players[j];
                if atk_info.check_attack_hit(victim) {
                    victim.state = STATE_HURT; victim.timer = 30; victim.vz = 4000; victim.hp -= 10000;
                }
            }
        }
    }
}

// --- 4. 離線 Session (組合模式 A) ---

#[pyclass]
pub struct OfflineSession {
    state: GameState,
}

#[pymethods]
impl OfflineSession {
    #[new]
    fn new(num_players: usize) -> Self {
        let mut players = Vec::new();
        let spawn_points = [(200000, 300000), (600000, 300000), (200000, 450000), (600000, 450000)];
        for i in 0..num_players {
            let mut p = Player::new();
            if i < spawn_points.len() { p.x = spawn_points[i].0; p.y = spawn_points[i].1; }
            players.push(p);
        }
        OfflineSession { state: GameState { players, frame: 0 } }
    }

    fn advance(&mut self, inputs: Vec<u8>) {
        let ggrs_style: Vec<(u8, InputStatus)> = inputs.into_iter().map(|i| (i, InputStatus::Confirmed)).collect();
        perform_tick(&mut self.state, &ggrs_style);
    }

    fn get_player(&self, id: usize) -> PyResult<Player> {
        self.state.players.get(id).cloned().ok_or_else(|| PyIndexError::new_err("OOR"))
    }

    fn set_player(&mut self, id: usize, player: Player) -> PyResult<()> {
        if let Some(p) = self.state.players.get_mut(id) { *p = player; Ok(()) } else { Err(PyIndexError::new_err("OOR")) }
    }

    fn current_frame(&self) -> i32 { self.state.frame }
    fn is_synchronized(&self) -> bool { true }
}

// --- 5. GGRS 連線 Session (組合模式 B) ---

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
        let socket = UdpNonBlockingSocket::bind_to_port(port).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        let mut builder = SessionBuilder::<BattleConfig>::new().with_num_players(num_players).with_fps(60).unwrap();
        builder = builder.add_player(PlayerType::Local, local_player_id).unwrap();
        for (id, ip, p) in remotes {
            if id != local_player_id {
                let addr: SocketAddr = format!("{}:{}", ip, p).parse().map_err(|e: std::net::AddrParseError| PyRuntimeError::new_err(e.to_string()))?;
                builder = builder.add_player(PlayerType::Remote(addr), id).unwrap();
            }
        }
        let session = builder.start_p2p_session(socket).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        let mut players = Vec::new();
        let spawn_points = [(200000, 300000), (600000, 300000), (200000, 450000), (600000, 450000)];
        for i in 0..num_players {
            let mut p = Player::new();
            if i < spawn_points.len() { p.x = spawn_points[i].0; p.y = spawn_points[i].1; }
            players.push(p);
        }
        Ok(GGRSSession { session, current_state: GameState { players, frame: 0 }, local_player_id })
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
        if let Some(p) = self.current_state.players.get_mut(id) { *p = player; Ok(()) } else { Err(PyIndexError::new_err("OOR")) }
    }

    fn is_synchronized(&self) -> bool { self.session.current_state() == SessionState::Running }
    fn current_frame(&self) -> i32 { self.session.current_frame() }
}

impl GGRSSession {
    fn handle_requests(&mut self, requests: Vec<GgrsRequest<BattleConfig>>) {
        for req in requests {
            match req {
                GgrsRequest::AdvanceFrame { inputs } => { perform_tick(&mut self.current_state, &inputs); }
                GgrsRequest::SaveGameState { cell, frame } => { cell.save(frame, Some(self.current_state.clone()), None); }
                GgrsRequest::LoadGameState { cell, .. } => { self.current_state = cell.load().unwrap_or_default(); }
            }
        }
    }
}

// --- 6. 模組註冊 ---

#[pyfunction]
fn decrypt_payload(payload: String, key: &[u8]) -> PyResult<String> {
    let data = general_purpose::STANDARD.decode(payload).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    let (nonce_bytes, ciphertext) = data.split_at(12);
    let cipher = ChaCha20Poly1305::new(Key::from_slice(key));
    let plaintext = cipher.decrypt(Nonce::from_slice(nonce_bytes), ciphertext).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    String::from_utf8(plaintext).map_err(|e| PyRuntimeError::new_err(e.to_string()))
}

#[pyfunction]
fn hello_from_rust() -> PyResult<String> { Ok("Hello from BattleLite Rust Core!".to_string()) }

#[pymodule]
fn battlelite_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(hello_from_rust, m)?)?;
    m.add_function(wrap_pyfunction!(decrypt_payload, m)?)?;
    m.add_class::<Player>()?;
    m.add_class::<OfflineSession>()?;
    m.add_class::<GGRSSession>()?;
    Ok(())
}
