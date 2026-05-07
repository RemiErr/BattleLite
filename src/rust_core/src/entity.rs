use pyo3::prelude::*;

#[derive(Clone, Default, Debug)]
pub(crate) struct Entity {
    pub(crate) owner_id:         usize,
    pub(crate) character_type:   u8,
    pub(crate) ability_state_id: u8,
    pub(crate) x:                i32,
    pub(crate) y:                i32,
    pub(crate) z:                i32,
    pub(crate) vx:               i32,
    pub(crate) vy:               i32,
    pub(crate) lifetime:         u32,
    pub(crate) is_skill:         bool,
}

#[pyclass]
#[derive(Clone, Debug)]
pub struct EntityView {
    #[pyo3(get)] pub owner_id:         usize,
    #[pyo3(get)] pub character_type:   u8,
    #[pyo3(get)] pub ability_state_id: u8,
    #[pyo3(get)] pub x:                i32,
    #[pyo3(get)] pub y:                i32,
    #[pyo3(get)] pub z:                i32,
    #[pyo3(get)] pub vx:               i32,
    #[pyo3(get)] pub lifetime:         u32,
    #[pyo3(get)] pub is_skill:         bool,
}
