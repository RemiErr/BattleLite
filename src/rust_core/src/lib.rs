use pyo3::prelude::*;
use pyo3::exceptions::{PyRuntimeError, PyIndexError};
use ggrs::{Config, GgrsError, P2PSession, PlayerType, SessionBuilder, InputStatus, GgrsRequest, UdpNonBlockingSocket, SessionState};
use std::net::SocketAddr;

// --- 1. 物理與戰鬥常數 (定點數，1000 = 1 像素) ---
const GRAVITY: i32 = 400;
const JUMP_IMPULSE: i32 = 9000;
const WALK_SPEED_X: i32 = 5000;
const WALK_SPEED_Y: i32 = 3000;

// 碰撞箱大小
const CHAR_WIDTH: i32 = 30000;  // 30px
const CHAR_DEPTH: i32 = 15000;  // 15px
const CHAR_HEIGHT: i32 = 4000;  // 4px (垂直高度判定)

// 戰鬥判定擴展
const ATK_DEPTH_REACH: i32 = 25000; // 25px (攻擊時的 Y 軸寬鬆度)

// 狀態定義
const STATE_IDLE: u8 = 0;
const STATE_WALK: u8 = 1;
const STATE_ATTACK: u8 = 2;
const STATE_HURT: u8 = 3;

// --- 2. 輸入遮罩定義 ---
const INPUT_RIGHT: u8 = 1 << 0;
const INPUT_LEFT: u8  = 1 << 1;
const INPUT_UP: u8    = 1 << 2;
const INPUT_DOWN: u8  = 1 << 3;
const INPUT_JUMP: u8  = 1 << 4;
const INPUT_ATTACK: u8 = 1 << 5;

// --- 3. 物理實體 ---

#[pyclass]
#[derive(Clone, Default, Debug)]
pub struct Player {
    #[pyo3(get, set)]
    pub x: i32,
    #[pyo3(get, set)]
    pub y: i32,
    #[pyo3(get, set)]
    pub z: i32,
    #[pyo3(get, set)]
    pub vx: i32,
    #[pyo3(get, set)]
    pub vy: i32,
    #[pyo3(get, set)]
    pub vz: i32,
    #[pyo3(get, set)]
    pub state: u8,
    #[pyo3(get, set)]
    pub timer: u32,
    #[pyo3(get, set)]
    pub facing_right: bool,
}

#[pymethods]
impl Player {
    #[new]
    fn new() -> Self {
        let mut p = Player::default();
        p.facing_right = true;
        p
    }

    /// 檢查此玩家的「攻擊框」是否打中對方的「身體框」
    fn check_attack_hit(&self, other: &Player) -> bool {
        let atk_offset_x = if self.facing_right { 30000 } else { -30000 };
        let atk_x = self.x + atk_offset_x;
        let atk_y = self.y;
        let atk_z = self.z;

        let atk_w = 20000; // 攻擊框半寬
        let body_w = CHAR_WIDTH / 2;
        let body_d = ATK_DEPTH_REACH; 
        let body_h = 20000; 

        let dx = (atk_x - other.x).abs();
        let dy = (atk_y - other.y).abs();
        let dz = (atk_z - other.z).abs();

        dx < (atk_w + body_w) && dy < body_d && dz < body_h
    }

    fn update(&mut self) {
        if self.timer > 0 {
            self.timer -= 1;
            if self.timer == 0 && (self.state == STATE_ATTACK || self.state == STATE_HURT) {
                self.state = STATE_IDLE;
            }
        }

        if self.z > 0 || self.vz > 0 {
            self.vz -= GRAVITY;
        }

        if self.state != STATE_ATTACK && self.state != STATE_HURT {
            self.x += self.vx;
            self.y += self.vy;
        }
        self.z += self.vz;

        if self.z <= 0 {
            self.z = 0;
            self.vz = 0;
        }
    }
}

// --- 4. 遊戲狀態與 GGRS 橋接器 ---

#[derive(Clone, Default, Debug)]
pub struct GameState {
    pub players: Vec<Player>,
}

pub struct BattleConfig;
impl Config for BattleConfig {
    type Input = u8;
    type State = GameState;
    type Address = SocketAddr;
}

#[pyclass(unsendable)]
pub struct GGRSSession {
    session_p2p: Option<P2PSession<BattleConfig>>,
    current_state: GameState,
}

#[pymethods]
impl GGRSSession {
    #[new]
    fn new(local_player_id: usize, num_players: usize, port: u16) -> PyResult<Self> {
        let socket = UdpNonBlockingSocket::bind_to_port(port)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

        let mut builder = SessionBuilder::<BattleConfig>::new()
            .with_num_players(num_players)
            .with_fps(60)
            .unwrap();

        for i in 0..num_players {
            if i == local_player_id {
                builder = builder.add_player(PlayerType::Local, i).unwrap();
            } else {
                let placeholder_addr: SocketAddr = format!("127.0.0.1:{}", 7000 + i).parse().unwrap();
                builder = builder.add_player(PlayerType::Remote(placeholder_addr), i).unwrap();
            }
        }

        let session = builder.start_p2p_session(socket)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

        let mut players = Vec::new();
        let spawn_points = [(200000, 300000), (600000, 300000), (200000, 450000), (600000, 450000)];
        for i in 0..num_players {
            let mut p = Player::default();
            if i < spawn_points.len() {
                p.x = spawn_points[i].0; p.y = spawn_points[i].1;
            }
            players.push(p);
        }

        Ok(GGRSSession {
            session_p2p: Some(session),
            current_state: GameState { players },
        })
    }

    fn advance(&mut self, local_input: u8) -> PyResult<()> {
        if let Some(ref mut s) = self.session_p2p {
            s.poll_remote_clients();
            if s.current_state() == SessionState::Running {
                s.add_local_input(0, local_input).ok();
                let requests = s.advance_frame().unwrap_or_default();
                self.handle_requests(requests);
            }
        }
        Ok(())
    }

    fn is_synchronized(&self) -> bool {
        self.session_p2p.as_ref().map_or(false, |s| s.current_state() == SessionState::Running)
    }

    fn current_frame(&self) -> i32 {
        self.session_p2p.as_ref().map_or(0, |s| s.current_frame())
    }

    fn get_player(&self, player_id: usize) -> PyResult<Player> {
        if player_id < self.current_state.players.len() {
            Ok(self.current_state.players[player_id].clone())
        } else {
            Err(PyIndexError::new_err("Player ID out of range"))
        }
    }

    fn set_player(&mut self, player_id: usize, player: Player) -> PyResult<()> {
        if player_id < self.current_state.players.len() {
            self.current_state.players[player_id] = player;
            Ok(())
        } else {
            Err(PyIndexError::new_err("Player ID out of range"))
        }
    }

    fn add_player(&mut self, _player_type: String, _id: usize) -> PyResult<()> { Ok(()) }
}

impl GGRSSession {
    fn handle_requests(&mut self, requests: Vec<GgrsRequest<BattleConfig>>) {
        for req in requests {
            match req {
                GgrsRequest::AdvanceFrame { inputs } => {
                    for (i, (input, status)) in inputs.iter().enumerate() {
                        if *status != InputStatus::Disconnected {
                            let p = &mut self.current_state.players[i];
                            if p.state == STATE_IDLE || p.state == STATE_WALK {
                                p.vx = 0; p.vy = 0;
                                if input & INPUT_RIGHT != 0 { p.vx += WALK_SPEED_X; p.state = STATE_WALK; p.facing_right = true; }
                                if input & INPUT_LEFT  != 0 { p.vx -= WALK_SPEED_X; p.state = STATE_WALK; p.facing_right = false; }
                                if input & INPUT_DOWN  != 0 { p.vy += WALK_SPEED_Y; p.state = STATE_WALK; }
                                if input & INPUT_UP    != 0 { p.vy -= WALK_SPEED_Y; p.state = STATE_WALK; }
                                if p.vx == 0 && p.vy == 0 { p.state = STATE_IDLE; }
                                if input & INPUT_JUMP != 0 && p.z == 0 { p.vz = JUMP_IMPULSE; }
                                if input & INPUT_ATTACK != 0 {
                                    p.state = STATE_ATTACK; p.timer = 20; p.vx = 0; p.vy = 0;
                                }
                            }
                            p.update();
                        }
                    }
                    let num_players = self.current_state.players.len();
                    for i in 0..num_players {
                        if self.current_state.players[i].state == STATE_ATTACK && self.current_state.players[i].timer == 15 {
                            for j in 0..num_players {
                                if i == j { continue; }
                                let attacker_pos = self.current_state.players[i].clone();
                                let victim = &mut self.current_state.players[j];
                                if attacker_pos.check_attack_hit(victim) {
                                    victim.state = STATE_HURT; victim.timer = 30; victim.vz = 3000;
                                }
                            }
                        }
                    }
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

#[pyfunction]
fn hello_from_rust() -> PyResult<String> {
    Ok("Hello from BattleLite Rust Core!".to_string())
}

#[pymodule]
fn battlelite_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(hello_from_rust, m)?)?;
    m.add_class::<Player>()?;
    m.add_class::<GGRSSession>()?;
    Ok(())
}
