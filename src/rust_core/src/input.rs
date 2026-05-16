use crate::config::{
    CharConfig, STATE_IDLE, STATE_WALK, STATE_DEAD,
    INPUT_RIGHT, INPUT_LEFT, INPUT_UP, INPUT_DOWN, INPUT_JUMP,
};
use crate::entity::{Entity, try_build_entity};
use crate::physics::apply_per_tick_buffs;
use crate::player::Player;

/// 單一玩家的完整 per-tick 處理。
/// 執行順序為時序合約，不得變動：
///   1. DEAD 快速路徑
///   2. 輸入解析（移動 / 跳躍 / 技能觸發）
///   3. Entity 生成（在 update_internal 遞減 timer 前）
///   4. Dash 衝刺（elapsed 在 update_internal 遞減前計算）
///   5. update_internal（物理推進 + timer 遞減）
///   6. apply_per_tick_buffs（MP/HP 回復）
pub(crate) fn process_player_tick(
    p:           &mut Player,
    player_idx:  usize,
    input:       u8,
    pcfg:        &CharConfig,
    spawn_queue: &mut Vec<Entity>,
) {
    let phy = &pcfg.physics;

    if p.state == STATE_DEAD {
        p.update_internal(phy.gravity, false);
        return;
    }

    if p.state == STATE_IDLE || p.state == STATE_WALK {
        p.vx = 0; p.vy = 0;
        if input & INPUT_RIGHT != 0 { p.vx += phy.walk_speed_x; p.state = STATE_WALK; p.facing_right = true; }
        if input & INPUT_LEFT  != 0 { p.vx -= phy.walk_speed_x; p.state = STATE_WALK; p.facing_right = false; }
        if input & INPUT_DOWN  != 0 { p.vy += phy.walk_speed_y; p.state = STATE_WALK; }
        if input & INPUT_UP    != 0 { p.vy -= phy.walk_speed_y; p.state = STATE_WALK; }
        if p.vx == 0 && p.vy == 0  { p.state = STATE_IDLE; }
        if input & INPUT_JUMP != 0 && p.z == 0 { p.vz = phy.jump_impulse; }
        for ab in &pcfg.abilities {
            if input & ab.trigger_button != 0 && p.mp >= ab.mp_cost {
                p.state = ab.state_id;
                p.timer = ab.timer;
                p.mp   -= ab.mp_cost;
                p.vx    = 0; p.vy = 0;
                if ab.damage_absorb > 0 { p.shield_hp = ab.damage_absorb; }
                break;
            }
        }
    }

    if let Some(entity) = try_build_entity(p, player_idx, pcfg) {
        spawn_queue.push(entity);
    }

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
