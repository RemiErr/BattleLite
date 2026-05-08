use pyo3::prelude::*;
use pyo3::exceptions::{PyRuntimeError, PyIndexError};
use ggrs::{
    P2PSession, PlayerType, SessionBuilder, SessionState,
    GgrsRequest, UdpNonBlockingSocket,
};
use std::net::SocketAddr;

use crate::config::{CharConfig, do_set_physics_config, do_set_ability};
use crate::player::Player;
use crate::entity::EntityView;
use crate::game_state::{GameState, BattleConfig, perform_tick};

#[pyclass(unsendable)]
pub struct GGRSSession {
    session:         P2PSession<BattleConfig>,
    current_state:   GameState,
    local_player_id: usize,
    #[allow(dead_code)]
    bot_ids:         Vec<usize>,
    char_configs:    Vec<CharConfig>,
    last_inputs:     Vec<u8>,
}

#[pymethods]
impl GGRSSession {
    #[new]
    #[pyo3(signature = (local_player_id, num_players, port, remotes, bot_ids=None))]
    fn new(
        local_player_id: usize, num_players: usize, port: u16,
        remotes: Vec<(usize, String, u16)>,
        bot_ids: Option<Vec<usize>>,
    ) -> PyResult<Self> {
        let bot_ids = bot_ids.unwrap_or_default();
        let socket = UdpNonBlockingSocket::bind_to_port(port)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        let mut builder = SessionBuilder::<BattleConfig>::new()
            .with_num_players(num_players).with_fps(60).unwrap();
        builder = builder.add_player(PlayerType::Local, local_player_id).unwrap();
        for &bot_id in &bot_ids {
            builder = builder.add_player(PlayerType::Local, bot_id).unwrap();
        }
        for (id, ip, p) in remotes {
            if id != local_player_id && !bot_ids.contains(&id) {
                let addr: SocketAddr = format!("{}:{}", ip, p).parse()
                    .map_err(|e: std::net::AddrParseError| PyRuntimeError::new_err(e.to_string()))?;
                builder = builder.add_player(PlayerType::Remote(addr), id).unwrap();
            }
        }
        let session = builder.start_p2p_session(socket)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        let spawn_points = [
            (200000, 300000), (824000, 300000),
            (200000, 450000), (824000, 450000),
        ];
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
            bot_ids,
            char_configs: configs,
            last_inputs: Vec::new(),
        })
    }

    fn set_physics_config(
        &mut self, char_type: usize,
        gravity: i32, jump_impulse: i32, walk_speed_x: i32, walk_speed_y: i32,
        hitstop_frames: u32,
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

    #[pyo3(signature = (local_input, bot_inputs=None))]
    fn advance(&mut self, local_input: u8, bot_inputs: Option<Vec<(usize, u8)>>) -> PyResult<()> {
        self.session.poll_remote_clients();
        if self.session.current_state() == SessionState::Running {
            self.session.add_local_input(self.local_player_id, local_input).ok();
            if let Some(inputs) = bot_inputs {
                for (bot_id, bot_input) in inputs {
                    self.session.add_local_input(bot_id, bot_input).ok();
                }
            }
            match self.session.advance_frame() {
                Ok(requests) => self.handle_requests(requests),
                _ => {}
            }
        }
        Ok(())
    }

    fn get_player(&self, id: usize) -> PyResult<Player> {
        self.current_state.players.get(id).cloned()
            .ok_or_else(|| PyIndexError::new_err("OOR"))
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
            x: e.x, y: e.y, z: e.z, vx: e.vx,
            lifetime: e.lifetime, is_skill: e.is_skill,
        }).ok_or_else(|| PyIndexError::new_err("Entity OOR"))
    }

    fn is_synchronized(&self) -> bool { self.session.current_state() == SessionState::Running }
    fn current_frame(&self) -> i32 { self.session.current_frame() }

    fn get_last_inputs(&self) -> Vec<u8> {
        self.last_inputs.clone()
    }
}

impl GGRSSession {
    fn handle_requests(&mut self, requests: Vec<GgrsRequest<BattleConfig>>) {
        let configs = self.char_configs.clone();
        for req in requests {
            match req {
                GgrsRequest::AdvanceFrame { inputs } => {
                    self.last_inputs = inputs.iter().map(|(inp, _)| *inp).collect();
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
