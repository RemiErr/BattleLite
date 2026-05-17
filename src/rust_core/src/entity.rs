use pyo3::prelude::*;
use crate::config::CharConfig;
use crate::player::Player;

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

pub(crate) fn try_build_entity(p: &Player, player_idx: usize, pcfg: &CharConfig) -> Option<Entity> {
    pcfg.abilities.iter().find(|ab| {
        ab.state_id == p.state
            && p.timer == ab.spawn_timer
            && (ab.projectile_vx != 0 || ab.spawn_entity)
    }).map(|ab| {
        let vx = if p.facing_right { ab.projectile_vx } else { -ab.projectile_vx };
        let spawn_x = if p.facing_right { p.x + ab.entity_spawn_offset } else { p.x - ab.entity_spawn_offset };
        Entity {
            owner_id:         player_idx,
            character_type:   p.character_type,
            ability_state_id: ab.state_id,
            x: spawn_x, y: p.y, z: p.z + ab.entity_spawn_z_offset,
            vx, vy: 0,
            lifetime: ab.projectile_lifetime,
            is_skill: ab.is_skill,
        }
    })
}

pub(crate) fn tick_entities(entities: &mut Vec<Entity>, spawn_queue: Vec<Entity>) {
    entities.retain_mut(|e| {
        e.x += e.vx;
        e.y += e.vy;
        e.lifetime = e.lifetime.saturating_sub(1);
        e.lifetime > 0
    });
    entities.extend(spawn_queue);
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
