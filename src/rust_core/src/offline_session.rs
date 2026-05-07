use pyo3::prelude::*;
use pyo3::exceptions::PyIndexError;
use ggrs::InputStatus;

use crate::config::{CharConfig, do_set_physics_config, do_set_ability};
use crate::player::Player;
use crate::entity::EntityView;
use crate::game_state::{GameState, perform_tick};

#[pyclass]
pub struct OfflineSession {
    state:        GameState,
    char_configs: Vec<CharConfig>,
}

#[pymethods]
impl OfflineSession {
    #[new]
    fn new(num_players: usize) -> Self {
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
        OfflineSession {
            state: GameState { players, frame: 0, entities: Vec::new() },
            char_configs: configs,
        }
    }

    fn set_physics_config(
        &mut self, char_type: usize,
        gravity: i32, jump_impulse: i32, walk_speed_x: i32, walk_speed_y: i32,
        hitstop_frames: u32,
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
        self.state.players.get(id).cloned()
            .ok_or_else(|| PyIndexError::new_err("OOR"))
    }

    fn set_player(&mut self, id: usize, player: Player) -> PyResult<()> {
        self.state.players.get_mut(id).map(|p| *p = player)
            .ok_or_else(|| PyIndexError::new_err("OOR"))
    }

    fn clear_entities(&mut self) { self.state.entities.clear(); }

    fn get_entity_count(&self) -> usize { self.state.entities.len() }

    fn get_entity(&self, id: usize) -> PyResult<EntityView> {
        self.state.entities.get(id).map(|e| EntityView {
            owner_id: e.owner_id, character_type: e.character_type,
            ability_state_id: e.ability_state_id,
            x: e.x, y: e.y, z: e.z, vx: e.vx,
            lifetime: e.lifetime, is_skill: e.is_skill,
        }).ok_or_else(|| PyIndexError::new_err("Entity OOR"))
    }

    fn current_frame(&self) -> i32 { self.state.frame }
    fn is_synchronized(&self) -> bool { true }
}
