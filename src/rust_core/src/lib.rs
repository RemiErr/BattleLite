use pyo3::prelude::*;
use pyo3::exceptions::{PyRuntimeError, PyIndexError};
use ggrs::{Config, GgrsError, P2PSession, PlayerType, SessionBuilder, InputStatus, GgrsRequest, UdpNonBlockingSocket, SessionState};
use std::net::SocketAddr;

// --- 1. 物理常數 (定點數，1000 = 1 單位) ---
const GRAVITY: i32 = 150; // 每幀重力加速度

// --- 2. 遊戲狀態與配置 ---

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

// --- 3. 物理實體 ---

#[pyclass]
#[derive(Clone, Default, Debug)]
pub struct Player {
    // 座標
    #[pyo3(get, set)]
    pub x: i32,
    #[pyo3(get, set)]
    pub y: i32,
    #[pyo3(get, set)]
    pub z: i32,
    // 速度
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

    /// 執行一幀的物理模擬
    fn update(&mut self) {
        // A. 應用重力 (僅當在空中或有向上速度時)
        if self.z > 0 || self.vz > 0 {
            self.vz -= GRAVITY;
        }

        // B. 更新座標
        self.x += self.vx;
        self.y += self.vy;
        self.z += self.vz;

        // C. 落地判定
        if self.z <= 0 {
            self.z = 0;
            self.vz = 0;
        }
    }
}

// --- 4. GGRS Session 橋接器 ---

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
        for _ in 0..num_players {
            players.push(Player::default());
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
        if let Some(ref s) = self.session_p2p {
            s.current_state() == SessionState::Running
        } else {
            false
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
                            
                            // 根據輸入設定速度 (暫時簡化版)
                            p.vx = 0;
                            p.vy = 0;
                            if input & 1 != 0 { p.vx = 5000; } // 右
                            if input & 2 != 0 { p.vx = -5000; } // 左
                            
                            // 呼叫物理更新
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
