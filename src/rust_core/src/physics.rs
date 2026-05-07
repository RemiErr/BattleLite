use crate::config::{PhysicsConfig, AbilityConfig, STATE_HURT, STATE_DEAD};
use crate::player::Player;

pub(crate) fn apply_hit(
    victim: &mut Player,
    damage: i32, kb_vx: i32, kb_vz: i32, kb_timer: u32,
    shield: i32, hitstop: u32,
) -> bool {
    if shield > 0 {
        let shield_taken = damage.min(shield);
        victim.shield_hp = (victim.shield_hp - shield_taken).max(0);
        victim.hp = (victim.hp - (damage - shield).max(0)).max(0);
    } else {
        victim.state   = STATE_HURT;
        victim.timer   = kb_timer;
        victim.vx      = kb_vx;
        victim.vz      = kb_vz;
        victim.hp      = (victim.hp - damage).max(0);
        victim.hitstop = hitstop;
    }
    if victim.hp == 0 { victim.state = STATE_DEAD; victim.timer = 0; }
    shield == 0
}

pub(crate) fn apply_per_tick_buffs(
    p: &mut Player,
    phy: &PhysicsConfig,
    active_ab: Option<&AbilityConfig>,
) {
    if p.mp < phy.max_mp { p.mp = (p.mp + crate::config::MP_REGEN).min(phy.max_mp); }
    if p.hp > phy.max_hp { p.hp = phy.max_hp; }
    if let Some(ab) = active_ab {
        if ab.hp_regen_per_tick > 0 && p.hp > 0 && p.state != STATE_DEAD {
            p.hp = (p.hp + ab.hp_regen_per_tick).min(phy.max_hp);
        }
    }
}
