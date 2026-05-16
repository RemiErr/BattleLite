use crate::config::{CharConfig, get_cfg, STATE_HURT, STATE_DEAD};
use crate::player::{Player, check_attack_hit_cfg};
use crate::physics::apply_hit;
use crate::entity::Entity;

pub(crate) fn resolve_projectile_hits(
    entities: &[Entity],
    players:  &mut Vec<Player>,
    configs:  &[CharConfig],
) {
    struct EntityHit {
        victim: usize, owner_id: usize,
        vx: i32, vz: i32, timer: u32, damage: i32, on_hit_hp_restore: i32,
    }
    let mut entity_hits: Vec<EntityHit> = Vec::new();
    for e in entities {
        let atk_cfg = get_cfg(configs, e.character_type);
        let Some(ab) = atk_cfg.abilities.iter().find(|ab| ab.state_id == e.ability_state_id) else { continue };
        for j in 0..players.len() {
            if e.owner_id == j { continue; }
            let victim = &players[j];
            if victim.state == STATE_HURT || victim.state == STATE_DEAD { continue; }
            let vic_cfg = get_cfg(configs, victim.character_type);
            let vic_phy = &vic_cfg.physics;
            let vic_off_x = if victim.facing_right { vic_phy.hurt_front } else { -vic_phy.hurt_front };
            let dx = (e.x - (victim.x + vic_off_x)).abs();
            let dy = (e.y - victim.y).abs();
            let dz = (e.z + ab.z_offset - (victim.z + vic_phy.hurt_z_offset)).abs();
            if dx < ab.half_w + vic_phy.hurt_half_w
                && dy < ab.depth
                && dz < ab.half_h + vic_phy.hurt_half_h
            {
                let kb_vx = if e.vx >= 0 { ab.kb_vx } else { -ab.kb_vx };
                let ratio = if ab.projectile_lifetime > 0 {
                    e.lifetime as i32 * 1000 / ab.projectile_lifetime as i32
                } else { 1000 };
                let damage = ab.dmg * ratio / 1000;
                entity_hits.push(EntityHit {
                    victim: j, owner_id: e.owner_id,
                    vx: kb_vx, vz: ab.kb_vz, timer: ab.kb_timer,
                    damage, on_hit_hp_restore: ab.on_hit_hp_restore,
                });
            }
        }
    }
    let mut hp_restores: Vec<(usize, i32)> = Vec::new();
    for hit in entity_hits {
        if players[hit.victim].state == STATE_DEAD { continue; }
        let (victim_state, victim_char) = {
            let v = &players[hit.victim];
            (v.state, v.character_type)
        };
        let vic_cfg = get_cfg(configs, victim_char);
        let shield = vic_cfg.abilities.iter()
            .find(|ab| ab.state_id == victim_state && ab.damage_absorb > 0)
            .map(|ab| ab.damage_absorb).unwrap_or(0);
        let hit_landed = apply_hit(
            &mut players[hit.victim],
            hit.damage, hit.vx, hit.vz, hit.timer,
            shield, vic_cfg.physics.hitstop_frames,
        );
        if hit_landed && hit.on_hit_hp_restore > 0 {
            hp_restores.push((hit.owner_id, hit.on_hit_hp_restore));
        }
    }
    for (pid, amount) in hp_restores {
        if let Some(owner) = players.get_mut(pid) {
            if owner.state != STATE_DEAD {
                let max_hp = get_cfg(configs, owner.character_type).physics.max_hp;
                owner.hp = (owner.hp + amount).min(max_hp);
            }
        }
    }
}

pub(crate) fn resolve_melee_hits(players: &mut Vec<Player>, configs: &[CharConfig]) {
    let num_players = players.len();
    for i in 0..num_players {
        let atk_info = players[i].clone();
        let atk_cfg  = get_cfg(configs, atk_info.character_type);
        let Some(ab) = atk_cfg.abilities.iter().find(|ab| {
            if ab.state_id != atk_info.state || !ab.melee_enabled { return false; }
            let elapsed = ab.timer.saturating_sub(atk_info.timer);
            elapsed >= ab.hit_start && elapsed <= ab.hit_end
        }) else { continue };

        let kb_vx = if atk_info.facing_right { ab.kb_vx } else { -ab.kb_vx };
        let mut hit_landed = false;

        for j in 0..num_players {
            if i == j { continue; }
            if players[j].state == STATE_HURT || players[j].state == STATE_DEAD { continue; }
            let vic_cfg = get_cfg(configs, players[j].character_type);
            if check_attack_hit_cfg(&atk_info, &players[j], ab, &vic_cfg.physics) {
                let victim_state = players[j].state;
                let shield = vic_cfg.abilities.iter()
                    .find(|a| a.state_id == victim_state && a.damage_absorb > 0)
                    .map(|a| a.damage_absorb).unwrap_or(0);
                if apply_hit(
                    &mut players[j],
                    ab.dmg, kb_vx, ab.kb_vz, ab.kb_timer,
                    shield, atk_cfg.physics.hitstop_frames,
                ) {
                    hit_landed = true;
                }
            }
        }
        if hit_landed {
            players[i].hitstop = atk_cfg.physics.hitstop_frames;
            if ab.on_hit_hp_restore > 0 {
                let max_hp = atk_cfg.physics.max_hp;
                players[i].hp = (players[i].hp + ab.on_hit_hp_restore).min(max_hp);
            }
        }
    }
}
