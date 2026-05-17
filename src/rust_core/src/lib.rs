use pyo3::prelude::*;

mod config;
mod player;
mod entity;
mod physics;
mod boundary;
mod collision;
mod input;
mod game_state;
mod offline_session;
mod ggrs_session;

use config::{STATE_IDLE, STATE_WALK, STATE_ATTACK, STATE_HURT, STATE_SKILL, STATE_DEAD};
use player::Player;
use entity::EntityView;
use offline_session::OfflineSession;
use ggrs_session::GGRSSession;

#[pyfunction]
fn hello_from_rust() -> PyResult<String> { Ok("Hello from BattleLite Rust Core!".to_string()) }

#[pymodule]
fn battlelite_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(hello_from_rust, m)?)?;
    m.add_class::<Player>()?;
    m.add_class::<EntityView>()?;
    m.add_class::<OfflineSession>()?;
    m.add_class::<GGRSSession>()?;
    m.add("STATE_IDLE",   STATE_IDLE)?;
    m.add("STATE_WALK",   STATE_WALK)?;
    m.add("STATE_ATTACK", STATE_ATTACK)?;
    m.add("STATE_HURT",   STATE_HURT)?;
    m.add("STATE_SKILL",  STATE_SKILL)?;
    m.add("STATE_DEAD",   STATE_DEAD)?;
    Ok(())
}
