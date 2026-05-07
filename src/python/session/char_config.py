from src.python.assets_manager.base_character import BaseCharacter

try:
    from src.python.game_constants import STATE_IDLE
except ImportError:
    STATE_IDLE = 0


def apply_char_config(session, char_type: int, asset: BaseCharacter) -> None:
    """PhysicsStats + AbilityDef → Rust PhysicsConfig + AbilityConfig。
    每個參數以具名方式傳入 set_ability，與 Rust 參數名稱一一對應。
    """
    p = asset.physics

    hurt_hb = asset.hurt_boxes.get(STATE_IDLE) or next(
        iter(asset.hurt_boxes.values()), None)
    hurt_f, hurt_hw, hurt_hh, hurt_zo = (
        hurt_hb.to_rust_params() if hurt_hb else (0, 15_000, 50_000, 0))

    session.set_physics_config(
        char_type,
        p.gravity, p.jump_impulse, p.walk_speed_x, p.walk_speed_y,
        p.hitstop_frames,
        p.max_hp, p.max_mp,
        hurt_f, hurt_hw, hurt_hh, hurt_zo,
    )

    for slot_idx, ab in enumerate(asset.abilities):
        spd = asset.speed_map.get(ab.state_id, 4)
        ab_f, ab_hw, ab_hh, ab_zo = (
            ab.hit_box.to_rust_params() if ab.hit_box else (0, 0, 0, 0))
        entity_spawn_offset   = (ab.proj_fx.offset_x * 1000) if ab.proj_fx else 0
        entity_spawn_z_offset = (ab.proj_fx.offset_y * 1000) if ab.proj_fx else 0
        spawn_timer = (ab.timer - ab.spawn_frame * spd
                       if ab.spawn_frame >= 0 else ab.spawn_timer_raw)

        session.set_ability(
            char_type, slot_idx,
            ab.trigger_button, ab.trigger_context, ab.state_id,
            ab.mp_cost, ab.timer,
            ab.dmg, ab_f, ab_hw, ab.depth, ab_hh, ab_zo,
            ab.kb_vx, ab.kb_vz, ab.kb_timer,
            ab.melee_enabled,
            ab.hit_frame_start * spd,
            ab.hit_frame_end * spd,
            ab.damage_absorb,
            ab.hp_regen_per_tick,
            ab.on_hit_hp_restore,
            ab.projectile_vx, ab.projectile_lifetime, spawn_timer,
            entity_spawn_offset, entity_spawn_z_offset,
            ab.spawn_entity,
            ab.dash_vx,
            ab.dash_frame * spd,
            ab.is_skill,
        )
