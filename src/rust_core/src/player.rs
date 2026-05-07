use pyo3::prelude::*;
use crate::config::{PhysicsConfig, AbilityConfig, MAX_HP, MAX_MP, STATE_IDLE, STATE_HURT, STATE_DEAD};

#[pyclass]
#[derive(Clone, Default, Debug)]
pub struct Player {
    #[pyo3(get, set)] pub x:              i32,
    #[pyo3(get, set)] pub y:              i32,
    #[pyo3(get, set)] pub z:              i32,
    #[pyo3(get, set)] pub vx:             i32,
    #[pyo3(get, set)] pub vy:             i32,
    #[pyo3(get, set)] pub vz:             i32,
    #[pyo3(get, set)] pub state:          u8,
    #[pyo3(get, set)] pub timer:          u32,
    #[pyo3(get, set)] pub facing_right:   bool,
    #[pyo3(get, set)] pub hp:             i32,
    #[pyo3(get, set)] pub mp:             i32,
    #[pyo3(get, set)] pub character_type: u8,
    #[pyo3(get, set)] pub hitstop:        u32,
    #[pyo3(get, set)] pub shield_hp:      i32,
}

#[pymethods]
impl Player {
    #[new]
    pub fn new() -> Self {
        let mut p = Player::default();
        p.facing_right = true;
        p.hp = MAX_HP;
        p.mp = MAX_MP;
        p
    }

    // Python 測試相容：使用預設 AbilityConfig（ATK slot）
    fn check_attack_hit(&self, other: &Player) -> bool {
        check_attack_hit_cfg(self, other, &AbilityConfig::default(), &PhysicsConfig::default())
    }

    // Python 測試相容：使用預設物理常數，不鎖定移動
    fn update(&mut self) {
        self.update_internal(PhysicsConfig::default().gravity, false);
    }
}

impl Player {
    // in_ability: 若為 true，本幀不套用 vx/vy 位移（技能鎖定狀態）
    pub(crate) fn update_internal(&mut self, gravity: i32, in_ability: bool) {
        if self.state == STATE_DEAD {
            if self.z > 0 || self.vz > 0 { self.vz -= gravity; }
            self.z += self.vz;
            if self.z <= 0 { self.z = 0; self.vz = 0; self.vx = 0; self.vy = 0; }
            return;
        }
        if self.hitstop > 0 {
            self.hitstop -= 1;
            return;
        }
        if self.timer > 0 {
            self.timer -= 1;
            if self.timer == 0 { self.state = STATE_IDLE; }
        }
        if self.z > 0 || self.vz > 0 { self.vz -= gravity; }
        if !in_ability {
            self.x += self.vx;
            self.y += self.vy;
        }
        if self.state == STATE_HURT {
            self.vx = self.vx * 9 / 10;
            self.vy = self.vy * 9 / 10;
        }
        self.z += self.vz;
        if self.z <= 0 {
            self.z = 0;
            self.vz = 0;
            if self.state == STATE_HURT {
                self.vx /= 2;
                self.vy /= 2;
            }
        }
    }
}

pub(crate) fn check_attack_hit_cfg(
    attacker: &Player, victim: &Player,
    ab: &AbilityConfig, vic_phy: &PhysicsConfig,
) -> bool {
    let atk_offset_x = if attacker.facing_right { ab.front } else { -ab.front };
    let atk_center_x = attacker.x + atk_offset_x;
    let atk_center_z = attacker.z + ab.z_offset;
    let vic_offset_x = if victim.facing_right { vic_phy.hurt_front } else { -vic_phy.hurt_front };
    let vic_center_x = victim.x + vic_offset_x;
    let vic_center_z = victim.z + vic_phy.hurt_z_offset;
    let dx = (atk_center_x - vic_center_x).abs();
    let dy = (attacker.y - victim.y).abs();
    let dz = (atk_center_z - vic_center_z).abs();
    dx < (ab.half_w + vic_phy.hurt_half_w)
        && dy < ab.depth
        && dz < (ab.half_h + vic_phy.hurt_half_h)
}
