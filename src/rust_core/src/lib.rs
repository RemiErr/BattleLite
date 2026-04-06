use pyo3::prelude::*;
use pyo3::exceptions::{PyRuntimeError, PyIndexError};
use ggrs::{Config, GgrsError, P2PSession, PlayerType, SessionBuilder, InputStatus, GgrsRequest, UdpNonBlockingSocket, SessionState};
use std::net::SocketAddr;

// --- 1. 物理與戰鬥常數 (定點數，1000 = 1 像素/單位) ---
const GRAVITY: i32 = 400;
const JUMP_IMPULSE: i32 = 9000;
const WALK_SPEED_X: i32 = 5000;
const WALK_SPEED_Y: i32 = 3000;

// 碰撞箱大小
const CHAR_WIDTH: i32 = 30000;
const CHAR_DEPTH: i32 = 15000;
const CHAR_HEIGHT: i32 = 4000;
const ATK_DEPTH_REACH: i32 = 25000;

// 狀態定義
const STATE_IDLE: u8 = 0;
const STATE_WALK: u8 = 1;
const STATE_ATTACK: u8 = 2;
const STATE_HURT: u8 = 3;
const STATE_SKILL: u8 = 4;

// 數值常數
const MAX_HP: i32 = 100000; // 100.0 HP
const MAX_MP: i32 = 50000;  // 50.0 MP
const MP_REGEN: i32 = 50;   // 0.05 MP per frame
const SKILL_COST: i32 = 20000; // 20.0 MP

// --- 2. 輸入遮罩定義 ---
const INPUT_RIGHT: u8  = 1 << 0;
const INPUT_LEFT: u8   = 1 << 1;
const INPUT_UP: u8     = 1 << 2;
const INPUT_DOWN: u8   = 1 << 3;
const INPUT_JUMP: u8   = 1 << 4;
const INPUT_ATTACK: u8 = 1 << 5;
const INPUT_SKILL: u8  = 1 << 6; // 新增：技能鍵

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
    // 數值屬性
    #[pyo3(get, set)]
    pub hp: i32,
    #[pyo3(get, set)]
    pub mp: i32,
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
        let atk_offset_x = if self.facing_right { 30000 } else { -30000 };
        let atk_x = self.x + atk_offset_x;
        let dx = (atk_x - other.x).abs();
        let dy = (self.y - other.y).abs();
        let dz = (self.z - other.z).abs();
        
        // 精準判定：X 軸 35px, Y 軸容差 ATK_DEPTH_REACH, Z 軸高度差 5px 內
        dx < 35000 && dy < ATK_DEPTH_REACH && dz < 5000
    }

    fn update(&mut self) {
        // A. 處理計時器與狀態恢復
        if self.timer > 0 {
            self.timer -= 1;
            if self.timer == 0 {
                self.state = STATE_IDLE;
            }
        }

        // B. MP 自動回復
        if self.mp < MAX_MP {
            self.mp += MP_REGEN;
            if self.mp > MAX_MP { self.mp = MAX_MP; }
        }

        // C. 應用重力
        if self.z > 0 || self.vz > 0 {
            self.vz -= GRAVITY;
        }

        // D. 更新座標
        if self.state != STATE_ATTACK && self.state != STATE_HURT && self.state != STATE_SKILL {
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
            let addr = if i == local_player_id { PlayerType::Local } 
                      else { PlayerType::Remote(format!("127.0.0.1:{}", 7000+i).parse().unwrap()) };
            builder = builder.add_player(addr, i).unwrap();
        }

        let session = builder.start_p2p_session(socket).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

        let mut players = Vec::new();
        let spawn_points = [(200000, 300000), (600000, 300000), (200000, 450000), (600000, 450000)];
        for i in 0..num_players {
            let mut p = Player::new(); // 使用自定義 new 以初始化 HP/MP
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

    fn is_synchronized(&self) -> bool { self.session_p2p.as_ref().map_or(false, |s| s.current_state() == SessionState::Running) }
    fn current_frame(&self) -> i32 { self.session_p2p.as_ref().map_or(0, |s| s.current_frame()) }
    fn get_player(&self, player_id: usize) -> PyResult<Player> {
        self.current_state.players.get(player_id).cloned().ok_or_else(|| PyIndexError::new_err("Out of range"))
    }
    fn set_player(&mut self, player_id: usize, player: Player) -> PyResult<()> {
        if let Some(p) = self.current_state.players.get_mut(player_id) {
            *p = player; Ok(())
        } else { Err(PyIndexError::new_err("Out of range")) }
    }
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
                                
                                // 攻擊觸發
                                if input & INPUT_ATTACK != 0 {
                                    p.state = STATE_ATTACK; p.timer = 20; p.vx = 0; p.vy = 0;
                                }
                                
                                // 技能觸發 (Bit 6)
                                if input & INPUT_SKILL != 0 && p.mp >= SKILL_COST {
                                    p.state = STATE_SKILL;
                                    p.timer = 40; // 技能硬直較長
                                    p.mp -= SKILL_COST;
                                    p.vx = 0; p.vy = 0;
                                }
                            }
                            p.update();
                        }
                    }
                    // 戰鬥判定
                    let num_players = self.current_state.players.len();
                    for i in 0..num_players {
                        let attacker = self.current_state.players[i].clone();
                        if (attacker.state == STATE_ATTACK && attacker.timer == 15) || 
                           (attacker.state == STATE_SKILL && attacker.timer > 10) {
                            for j in 0..num_players {
                                if i == j { continue; }
                                let victim = &mut self.current_state.players[j];
                                if attacker.check_attack_hit(victim) {
                                    victim.state = STATE_HURT; victim.timer = 30; victim.vz = 4000;
                                    victim.hp -= 10000; // 扣 10% 血
                                }
                            }
                        }
                    }
                }
                GgrsRequest::SaveGameState { cell, frame } => { cell.save(frame, Some(self.current_state.clone()), None); }
                GgrsRequest::LoadGameState { cell, .. } => { self.current_state = cell.load().unwrap_or_default(); }
            }
        }
    }
}

#[pymodule]
fn battlelite_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<Player>()?;
    m.add_class::<GGRSSession>()?;
    Ok(())
}
