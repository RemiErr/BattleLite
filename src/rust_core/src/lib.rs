use pyo3::prelude::*;
use pyo3::exceptions::{PyRuntimeError, PyIndexError};
use ggrs::{Config, GgrsError, P2PSession, PlayerType, SessionBuilder, InputStatus, GgrsRequest, UdpNonBlockingSocket, SessionState};
use std::net::SocketAddr;

// --- 1. 物理常數 (定點數，1000 = 1 單位) ---
const GRAVITY: i32 = 400;      // 每幀重力加速度
const JUMP_IMPULSE: i32 = 9000; // 跳躍初速度
const WALK_SPEED_X: i32 = 5000; // 左右移動速度
const WALK_SPEED_Y: i32 = 3000; // 深淺移動速度 (較慢，符合 2.5D 透視)

// --- 2. 輸入遮罩定義 (Input Mask) ---
const INPUT_RIGHT: u8 = 1 << 0;
const INPUT_LEFT: u8  = 1 << 1;
const INPUT_UP: u8    = 1 << 2;
const INPUT_DOWN: u8  = 1 << 3;
const INPUT_JUMP: u8  = 1 << 4;

// --- 3. 遊戲狀態與配置 ---

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

// --- 4. 物理實體 ---

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
}

#[pymethods]
impl Player {
    #[new]
    fn new() -> Self {
        Player::default()
    }

    fn update(&mut self) {
        // 應用重力
        if self.z > 0 || self.vz > 0 {
            self.vz -= GRAVITY;
        }

        // 更新座標
        self.x += self.vx;
        self.y += self.vy;
        self.z += self.vz;

        // 落地判定
        if self.z <= 0 {
            self.z = 0;
            self.vz = 0;
        }
    }
}

// --- 5. GGRS Session 橋接器 ---

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
// 初始化狀態與出生點
let mut players = Vec::new();
let spawn_points = [
    (200000, 300000), (600000, 300000), 
    (200000, 450000), (600000, 450000)
];

for i in 0..num_players {
    let mut p = Player::default();
    if i < spawn_points.len() {
        p.x = spawn_points[i].0;
        p.y = spawn_points[i].1;
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

    /// 獲取目前 GGRS 模擬的總幀數
    fn current_frame(&self) -> i32 {
        if let Some(ref s) = self.session_p2p {
            s.current_frame()
        } else {
            0
        }
    }

    fn get_player(&self, player_id: usize) -> PyResult<Player> {
        if player_id < self.current_state.players.len() {
            Ok(self.current_state.players[player_id].clone())
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
                            
                            // --- 完善的輸入映射 ---
                            p.vx = 0;
                            p.vy = 0;
                            
                            if input & INPUT_RIGHT != 0 { p.vx += WALK_SPEED_X; }
                            if input & INPUT_LEFT != 0  { p.vx -= WALK_SPEED_X; }
                            if input & INPUT_DOWN != 0  { p.vy += WALK_SPEED_Y; }
                            if input & INPUT_UP != 0    { p.vy -= WALK_SPEED_Y; }
                            
                            // 跳躍邏輯：僅當在地面且按下跳躍鍵時觸發
                            if input & INPUT_JUMP != 0 && p.z == 0 {
                                p.vz = JUMP_IMPULSE;
                            }
                            
                            p.update();
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
