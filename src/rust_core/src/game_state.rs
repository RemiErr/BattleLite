use ggrs::{Config, InputStatus};
use std::net::SocketAddr;

use crate::config::{
    CharConfig, get_cfg,
    STATE_IDLE, STATE_WALK, STATE_HURT, STATE_DEAD,
    INPUT_RIGHT, INPUT_LEFT, INPUT_UP, INPUT_DOWN, INPUT_JUMP,
};
use crate::player::Player;
use crate::player::check_attack_hit_cfg;
use crate::entity::Entity;
use crate::physics::{apply_hit, apply_per_tick_buffs};

#[derive(Clone, Default, Debug)]
pub(crate) struct GameState {
    pub(crate) players:  Vec<Player>,
    pub(crate) frame:    i32,
    pub(crate) entities: Vec<Entity>,
}

const WORLD_X_MIN: i32 = 0;
const WORLD_X_MAX: i32 = 3_072_000;
const WORLD_Y_MIN: i32 = 250_000;
const WORLD_Y_MAX: i32 = 520_000;

pub(crate) struct BattleConfig;
impl Config for BattleConfig {
    type Input   = u8;
    type State   = GameState;
    type Address = SocketAddr;
}

pub(crate) fn perform_tick(
    state: &mut GameState,
    inputs: &[(u8, InputStatus)],
    configs: &[CharConfig],
) {
    state.frame += 1;

    let mut spawn_queue: Vec<Entity> = Vec::new();

    for (i, (input, status)) in inputs.iter().enumerate() {
        if i >= state.players.len() || *status == InputStatus::Disconnected { continue; }
        let p = &mut state.players[i];
        let pcfg = get_cfg(configs, p.character_type);
        let phy  = &pcfg.physics;

        if p.state == STATE_DEAD {
            p.update_internal(phy.gravity, false);
            continue;
        }

        // 移動輸入 + 觸發技能
        if p.state == STATE_IDLE || p.state == STATE_WALK {
            p.vx = 0; p.vy = 0;
            if input & INPUT_RIGHT != 0 { p.vx += phy.walk_speed_x; p.state = STATE_WALK; p.facing_right = true; }
            if input & INPUT_LEFT  != 0 { p.vx -= phy.walk_speed_x; p.state = STATE_WALK; p.facing_right = false; }
            if input & INPUT_DOWN  != 0 { p.vy += phy.walk_speed_y; p.state = STATE_WALK; }
            if input & INPUT_UP    != 0 { p.vy -= phy.walk_speed_y; p.state = STATE_WALK; }
            if p.vx == 0 && p.vy == 0  { p.state = STATE_IDLE; }
            if input & INPUT_JUMP != 0 && p.z == 0 { p.vz = phy.jump_impulse; }
            for ab in &pcfg.abilities {
                if *input & ab.trigger_button != 0 && p.mp >= ab.mp_cost {
                    p.state = ab.state_id;
                    p.timer = ab.timer;
                    p.mp   -= ab.mp_cost;
                    p.vx    = 0; p.vy = 0;
                    if ab.damage_absorb > 0 {
                        p.shield_hp = ab.damage_absorb;
                    }
                    break;
                }
            }
        }

        // Entity 生成（以 timer 倒數值比對，在 update_internal 遞減前判斷）
        if let Some(ab) = pcfg.abilities.iter().find(|ab| {
            ab.state_id == p.state
                && p.timer == ab.spawn_timer
                && (ab.projectile_vx != 0 || ab.spawn_entity)
        }) {
            let vx = if p.facing_right { ab.projectile_vx } else { -ab.projectile_vx };
            let spawn_x = if p.facing_right { p.x + ab.entity_spawn_offset } else { p.x - ab.entity_spawn_offset };
            spawn_queue.push(Entity {
                owner_id:         i,
                character_type:   p.character_type,
                ability_state_id: ab.state_id,
                x: spawn_x, y: p.y, z: p.z + ab.entity_spawn_z_offset,
                vx, vy: 0,
                lifetime: ab.projectile_lifetime,
                is_skill: ab.is_skill,
            });
        }

        // 衝刺（elapsed = timer_max – timer，在 update_internal 遞減前計算）
        if let Some(ab) = pcfg.abilities.iter().find(|ab| ab.state_id == p.state && ab.dash_vx != 0) {
            let elapsed = ab.timer.saturating_sub(p.timer);
            if elapsed == ab.dash_tick {
                let dash = if p.facing_right { ab.dash_vx } else { -ab.dash_vx };
                p.x += dash;
            }
        }

        let active_ab = pcfg.abilities.iter().find(|ab| ab.state_id == p.state);
        p.update_internal(phy.gravity, active_ab.is_some());
        apply_per_tick_buffs(p, phy, active_ab);
    }

    // 實體移動 + 壽命遞減
    state.entities.retain_mut(|e| {
        e.x += e.vx;
        e.y += e.vy;
        e.lifetime = e.lifetime.saturating_sub(1);
        e.lifetime > 0
    });
    state.entities.extend(spawn_queue);

    // 投擲物碰撞判定
    struct EntityHit {
        victim: usize, owner_id: usize,
        vx: i32, vz: i32, timer: u32, damage: i32, on_hit_hp_restore: i32,
    }
    let mut entity_hits: Vec<EntityHit> = Vec::new();
    for e in &state.entities {
        let atk_cfg = get_cfg(configs, e.character_type);
        let Some(ab) = atk_cfg.abilities.iter().find(|ab| ab.state_id == e.ability_state_id) else { continue };
        for j in 0..state.players.len() {
            if e.owner_id == j { continue; }
            let victim = &state.players[j];
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
    let mut entity_hp_restores: Vec<(usize, i32)> = Vec::new();
    for hit in entity_hits {
        if state.players[hit.victim].state == STATE_DEAD { continue; }
        let (victim_state, victim_char) = {
            let v = &state.players[hit.victim];
            (v.state, v.character_type)
        };
        let vic_cfg = get_cfg(configs, victim_char);
        let shield = vic_cfg.abilities.iter()
            .find(|ab| ab.state_id == victim_state && ab.damage_absorb > 0)
            .map(|ab| ab.damage_absorb).unwrap_or(0);
        let hit_landed = apply_hit(
            &mut state.players[hit.victim],
            hit.damage, hit.vx, hit.vz, hit.timer,
            shield, vic_cfg.physics.hitstop_frames,
        );
        if hit_landed && hit.on_hit_hp_restore > 0 {
            entity_hp_restores.push((hit.owner_id, hit.on_hit_hp_restore));
        }
    }
    for (pid, amount) in entity_hp_restores {
        if let Some(owner) = state.players.get_mut(pid) {
            if owner.state != STATE_DEAD {
                let max_hp = get_cfg(configs, owner.character_type).physics.max_hp;
                owner.hp = (owner.hp + amount).min(max_hp);
            }
        }
    }

    // 近戰判定
    let num_players = state.players.len();
    for i in 0..num_players {
        let atk_info = state.players[i].clone();
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
            if state.players[j].state == STATE_HURT || state.players[j].state == STATE_DEAD { continue; }
            let vic_cfg = get_cfg(configs, state.players[j].character_type);
            if check_attack_hit_cfg(&atk_info, &state.players[j], ab, &vic_cfg.physics) {
                let victim_state = state.players[j].state;
                let shield = vic_cfg.abilities.iter()
                    .find(|a| a.state_id == victim_state && a.damage_absorb > 0)
                    .map(|a| a.damage_absorb).unwrap_or(0);
                if apply_hit(
                    &mut state.players[j],
                    ab.dmg, kb_vx, ab.kb_vz, ab.kb_timer,
                    shield, atk_cfg.physics.hitstop_frames,
                ) {
                    hit_landed = true;
                }
            }
        }
        if hit_landed {
            state.players[i].hitstop = atk_cfg.physics.hitstop_frames;
            if ab.on_hit_hp_restore > 0 {
                let max_hp = atk_cfg.physics.max_hp;
                state.players[i].hp = (state.players[i].hp + ab.on_hit_hp_restore).min(max_hp);
            }
        }
    }

    // 世界邊界夾緊（在 GGRS 快照週期內，確保 rollback 後確定性一致）
    for p in state.players.iter_mut() {
        if p.x < WORLD_X_MIN      { p.x = WORLD_X_MIN; p.vx = 0; }
        else if p.x > WORLD_X_MAX { p.x = WORLD_X_MAX; p.vx = 0; }
        if p.y < WORLD_Y_MIN      { p.y = WORLD_Y_MIN; p.vy = 0; }
        else if p.y > WORLD_Y_MAX { p.y = WORLD_Y_MAX; p.vy = 0; }
    }
}
