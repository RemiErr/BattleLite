use ggrs::{Config, InputStatus};
use std::net::SocketAddr;

use crate::config::{CharConfig, get_cfg};
use crate::player::Player;
use crate::entity::Entity;
use crate::{boundary, collision, entity, input};

#[derive(Clone, Default, Debug)]
pub(crate) struct GameState {
    pub(crate) players:  Vec<Player>,
    pub(crate) frame:    i32,
    pub(crate) entities: Vec<Entity>,
}

pub(crate) struct BattleConfig;
impl Config for BattleConfig {
    type Input   = u8;
    type State   = GameState;
    type Address = SocketAddr;
}

pub(crate) fn perform_tick(
    state:   &mut GameState,
    inputs:  &[(u8, InputStatus)],
    configs: &[CharConfig],
) {
    state.frame += 1;
    let mut spawn_queue: Vec<Entity> = Vec::new();

    for (i, (inp, status)) in inputs.iter().enumerate() {
        if i >= state.players.len() || *status == InputStatus::Disconnected { continue; }
        let pcfg = get_cfg(configs, state.players[i].character_type);
        input::process_player_tick(&mut state.players[i], i, *inp, &pcfg, &mut spawn_queue);
    }

    entity::tick_entities(&mut state.entities, spawn_queue);
    collision::resolve_projectile_hits(&state.entities, &mut state.players, configs);
    collision::resolve_melee_hits(&mut state.players, configs);
    boundary::clamp_to_world(&mut state.players);
}
