use pyo3::prelude::*;
use pyo3::exceptions::{PyRuntimeError, PyIndexError};
use ggrs::{Config, GgrsError, P2PSession, PlayerType, SessionBuilder, InputStatus, GgrsRequest, UdpNonBlockingSocket, SessionState};
use std::net::SocketAddr;

// --- 1. 遊戲狀態與配置 ---

#[derive(Clone, Default, Debug)]
pub struct GameState {
    pub players: Vec<Player>,
}

pub struct BattleConfig;
impl Config for BattleConfig {
    type Input = u8; // 8-bit input mask
    type State = GameState;
    type Address = SocketAddr;
}

// --- 2. 物理實體 ---

#[pyclass]
#[derive(Clone, Default, Debug)]
pub struct Player {
    #[pyo3(get, set)]
    pub x: i32,
    #[pyo3(get, set)]
    pub y: i32,
    #[pyo3(get, set)]
    pub z: i32,
}

#[pymethods]
impl Player {
    #[new]
    fn new() -> Self {
        Player::default()
    }
}

// --- 3. GGRS Session 橋接器 ---

#[pyclass(unsendable)]
pub struct GGRSSession {
    session: P2PSession<BattleConfig>,
    current_state: GameState,
}

#[pymethods]
impl GGRSSession {
    #[new]
    fn new(local_player_id: usize, num_players: usize, port: u16) -> PyResult<Self> {
        // 建立 GGRS 專用的非阻塞 UDP Socket
        let socket = UdpNonBlockingSocket::bind_to_port(port)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

        // 建立 GGRS Session
        let mut builder = SessionBuilder::<BattleConfig>::new()
            .with_num_players(num_players)
            .with_fps(60)
            .unwrap();

        // 註冊玩家
        for i in 0..num_players {
            if i == local_player_id {
                builder = builder.add_player(PlayerType::Local, i).unwrap();
            } else {
                let placeholder_addr: SocketAddr = format!("127.0.0.1:{}", 7000 + i).parse().unwrap();
                builder = builder.add_player(PlayerType::Remote(placeholder_addr), i).unwrap();
            }
        }

        // GGRS 0.11 使用 start_p2p_session
        let session = builder.start_p2p_session(socket)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

        // 初始化狀態
        let mut players = Vec::new();
        for _ in 0..num_players {
            players.push(Player::default());
        }

        Ok(GGRSSession {
            session,
            current_state: GameState { players },
        })
    }

    /// 推進一幀
    fn advance(&mut self, local_input: u8) -> PyResult<()> {
        // 每一幀先處理網路封包
        self.session.poll_remote_clients();

        // 只有在 Running 狀態下才執行邏輯 (避免 NotSynchronized 錯誤)
        if self.session.current_state() == SessionState::Running {
            match self.session.add_local_input(0, local_input) {
                Ok(()) => {},
                Err(GgrsError::PredictionThreshold) => return Ok(()),
                Err(e) => return Err(PyRuntimeError::new_err(e.to_string())),
            }

            match self.session.advance_frame() {
                Ok(requests) => {
                    for req in requests {
                        match req {
                            GgrsRequest::AdvanceFrame { inputs } => {
                                for (i, (input, status)) in inputs.iter().enumerate() {
                                    if *status != InputStatus::Disconnected {
                                        let p = &mut self.current_state.players[i];
                                        if input & 1 != 0 {
                                            p.x += 1000;
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
                Err(GgrsError::NotSynchronized) => {}, // 靜默處理尚未同步的情況
                Err(e) => return Err(PyRuntimeError::new_err(e.to_string())),
            }
        }

        Ok(())
    }

    /// 檢查是否已完成網路同步
    fn is_synchronized(&self) -> bool {
        self.session.current_state() == SessionState::Running
    }

    fn get_player(&self, player_id: usize) -> PyResult<Player> {
        if player_id < self.current_state.players.len() {
            Ok(self.current_state.players[player_id].clone())
        } else {
            Err(PyIndexError::new_err("Player ID out of range"))
        }
    }

    fn add_player(&mut self, _player_type: String, _id: usize) -> PyResult<()> {
        Ok(())
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
