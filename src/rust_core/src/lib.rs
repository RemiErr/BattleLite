use pyo3::prelude::*;
use pyo3::exceptions::PyRuntimeError;
use chacha20poly1305::{ChaCha20Poly1305, Key, Nonce, KeyInit, aead::Aead};
use base64::{engine::general_purpose, Engine as _};

mod config;
mod player;
mod entity;
mod physics;
mod game_state;
mod offline_session;
mod ggrs_session;

use config::{STATE_IDLE, STATE_WALK, STATE_HURT, STATE_DEAD};
use player::Player;
use entity::EntityView;
use offline_session::OfflineSession;
use ggrs_session::GGRSSession;

#[pyfunction]
fn decrypt_payload(payload: String, key: &[u8]) -> PyResult<String> {
    let data = general_purpose::STANDARD.decode(payload)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    let (nonce_bytes, ciphertext) = data.split_at(12);
    let cipher = ChaCha20Poly1305::new(Key::from_slice(key));
    let plaintext = cipher.decrypt(Nonce::from_slice(nonce_bytes), ciphertext)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    String::from_utf8(plaintext).map_err(|e| PyRuntimeError::new_err(e.to_string()))
}

#[pyfunction]
fn hello_from_rust() -> PyResult<String> { Ok("Hello from BattleLite Rust Core!".to_string()) }

#[pymodule]
fn battlelite_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(hello_from_rust, m)?)?;
    m.add_function(wrap_pyfunction!(decrypt_payload, m)?)?;
    m.add_class::<Player>()?;
    m.add_class::<EntityView>()?;
    m.add_class::<OfflineSession>()?;
    m.add_class::<GGRSSession>()?;
    m.add("STATE_IDLE",  STATE_IDLE)?;
    m.add("STATE_WALK",  STATE_WALK)?;
    m.add("STATE_HURT",  STATE_HURT)?;
    m.add("STATE_DEAD",  STATE_DEAD)?;
    Ok(())
}
