import pygame
import sys
import os
import argparse
import json

# 確保路徑正確
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    import battlelite_core
    from battlelite_core import Player, OfflineSession, GGRSSession
    from src.python.renderer import get_screen_pos
    from src.python.debug_manager import DebugManager
    from src.python.hud import HUD, SCREEN_W, SCREEN_H, HUD_H
    from src.python.assets_manager.characters.knight import Knight
    from src.python.assets_manager.characters.mage import Mage
    from src.python.assets_manager.characters.archer import Archer
    from src.python.assets_manager.characters.paladin import Paladin
    from src.python.assets_manager.characters.wizard import Wizard
    from src.python.assets_manager.base_character import BaseCharacter
    from src.python.fx_manager import FxManager
    from src.python.crypto_utils import SHARED_SECRET
except ImportError as e:
    print(f"❌ 匯入失敗: {e}")
    sys.exit(1)

# --- 常數對齊 (必須與 Rust 對齊) ---
INPUT_RIGHT, INPUT_LEFT, INPUT_UP, INPUT_DOWN, INPUT_JUMP, INPUT_ATTACK, INPUT_SKILL = [
    1 << i for i in range(7)]
STATE_IDLE, STATE_WALK, STATE_ATTACK, STATE_HURT, STATE_SKILL = range(5)
STATE_DEAD = 5


def apply_char_config(session, char_type: int, asset: BaseCharacter) -> None:
    """PhysicsStats + AbilityDef → Rust PhysicsConfig + AbilityConfig。"""
    p = asset.physics

    # Hurt box 從 STATE_IDLE 推導（所有狀態共用同一 Rust hurt box）
    hurt_hb = asset.hurt_boxes.get(STATE_IDLE) or next(iter(asset.hurt_boxes.values()), None)
    if hurt_hb is not None:
        hurt_f, hurt_hw, hurt_hh, hurt_zo = hurt_hb.to_rust_params()
    else:
        hurt_f, hurt_hw, hurt_hh, hurt_zo = 0, 15_000, 50_000, 0

    session.set_physics_config(
        char_type,
        p.gravity, p.jump_impulse, p.walk_speed_x, p.walk_speed_y, p.hitstop_frames,
        p.max_hp, p.max_mp,
        hurt_f, hurt_hw, hurt_hh, hurt_zo,
    )

    for slot_idx, ab in enumerate(asset.abilities):
        spd = asset.speed_map.get(ab.state_id, 4)
        hit_start = ab.hit_frame_start * spd
        hit_end   = ab.hit_frame_end   * spd
        dash_tick = ab.dash_frame * spd
        # spawn_timer：幀索引優先於舊版 timer 倒數值
        spawn_timer = (ab.timer - ab.spawn_frame * spd
                       if ab.spawn_frame >= 0 else ab.spawn_timer_raw)

        if ab.hit_box is not None:
            ab_f, ab_hw, ab_hh, ab_zo = ab.hit_box.to_rust_params()
        else:
            ab_f, ab_hw, ab_hh, ab_zo = 0, 0, 0, 0

        entity_offset   = (ab.proj_fx.offset_x * 1000) if ab.proj_fx else 0
        entity_z_offset = (ab.proj_fx.offset_y * 1000) if ab.proj_fx else 0

        session.set_ability(
            char_type, slot_idx,
            ab.trigger_button, ab.trigger_context, ab.state_id,
            ab.mp_cost, ab.timer,
            ab.dmg, ab_f, ab_hw, ab.depth, ab_hh, ab_zo,
            ab.kb_vx, ab.kb_vz, ab.kb_timer,
            ab.melee_enabled, hit_start, hit_end,
            ab.damage_absorb,
            ab.projectile_vx, ab.projectile_lifetime, spawn_timer,
            entity_offset, entity_z_offset,
            ab.spawn_entity,
            ab.dash_vx, dash_tick,
            ab.is_skill,
        )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--payload", help="Encrypted session data from Launcher")
    return parser.parse_args()


def get_input_mask():
    keys = pygame.key.get_pressed()
    mask = 0
    if keys[pygame.K_RIGHT]:
        mask |= INPUT_RIGHT
    if keys[pygame.K_LEFT]:
        mask |= INPUT_LEFT
    if keys[pygame.K_UP]:
        mask |= INPUT_UP
    if keys[pygame.K_DOWN]:
        mask |= INPUT_DOWN
    if keys[pygame.K_SPACE]:
        mask |= INPUT_JUMP
    if keys[pygame.K_z]:
        mask |= INPUT_ATTACK
    if keys[pygame.K_x]:
        mask |= INPUT_SKILL
    return mask


def run_game():
    args = parse_args()

    # 預設啟動設定
    config = {
        "nickname": "DevPlayer",
        "is_offline": True,
        "local_id": 0,
        "num_players": 4,
        "local_port": 5000
    }

    if args.payload:
        try:
            decrypted_str = battlelite_core.decrypt_payload(
                args.payload, SHARED_SECRET)
            config.update(json.loads(decrypted_str))
            print(f"✅ Session Handoff Success: Hello {config['nickname']}")
        except Exception as e:
            print(f"❌ Handshake Decryption Failed: {e}")
            sys.exit(1)

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption(f"BattleLite - {config['nickname']}")
    clock = pygame.time.Clock()
    debug_manager = DebugManager()
    fx_manager = FxManager()
    char_assets: dict[int, BaseCharacter] = {
        0: Knight(), 1: Mage(), 2: Archer(), 3: Paladin(), 4: Wizard()}

    # 建立玩家名稱對照表
    player_names: dict[int, str] = {
        config["local_id"]: config.get("nickname", "Player")}
    for p_info in config.get("players", []):
        if "nickname" in p_info:
            player_names[p_info["id"]] = p_info["nickname"]
    hud = HUD(char_assets, player_names=player_names)

    # --- Session 工廠 ---
    is_offline = config["is_offline"]
    num_players = config["num_players"]
    controlled_idx = config["local_id"]

    if is_offline:
        print("🕹 Mode: Offline Sandbox (Pure Rust Simulation)")
        session = OfflineSession(num_players)
        for char_type, asset in char_assets.items():
            apply_char_config(session, char_type, asset)
    else:
        print("🌐 Mode: Online P2P (GGRS Rollback)")
        print(
            f"  local_id={controlled_idx}  local_port={config['local_port']}")
        remote_players_list = []
        if "players" in config:
            for p in config["players"]:
                remote_players_list.append((p["id"], p["ip"], p["port"]))
                tag = "← me" if p["id"] == controlled_idx else "→ remote"
                print(f"  player id={p['id']}  {p['ip']}:{p['port']}  {tag}")
        session = GGRSSession(controlled_idx, num_players,
                              config["local_port"], remote_players_list)
        for char_type, asset in char_assets.items():
            apply_char_config(session, char_type, asset)

    player_elapsed_frames = [0] * num_players
    last_states = [STATE_IDLE] * num_players
    sync_wait_frames = 0
    switch_player = 0
    match_result: int | None = None  # None=進行中, -2=平手, 0..n=勝者 idx
    result_font_big   = pygame.font.SysFont("Arial", 56, bold=True)
    result_font_small = pygame.font.SysFont("Arial", 24)

    def _check_match(n: int) -> int | None:
        alive = [i for i in range(n) if session.get_player(i).state != STATE_DEAD]
        if len(alive) == 1:
            return alive[0]
        if len(alive) == 0:
            return -2
        return None

    def _restart_offline():
        nonlocal match_result, player_elapsed_frames, last_states
        for i in range(num_players):
            p = session.get_player(i)
            asset = char_assets.get(p.character_type, char_assets[0])
            p.hp    = asset.physics.max_hp
            p.mp    = asset.physics.max_mp
            p.state = STATE_IDLE
            p.timer = 0
            p.vx = p.vy = p.vz = 0
            p.z  = 0
            session.set_player(i, p)
        match_result = None
        player_elapsed_frames = [0] * num_players
        last_states = [STATE_IDLE] * num_players

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if match_result is not None:
                    if event.key == pygame.K_r and is_offline:
                        _restart_offline()
                    elif event.key == pygame.K_ESCAPE:
                        running = False
                    continue
                if event.key == pygame.K_F1:
                    debug_manager.toggle()
                if event.key == pygame.K_F2 and is_offline:
                    player_names.pop(controlled_idx, None)
                    switch_player = (switch_player + 1) % num_players
                    controlled_idx = switch_player
                    player_names[controlled_idx] = config.get("nickname", "Player")
                if event.key == pygame.K_F3 and is_offline:
                    p = session.get_player(controlled_idx)
                    new_type = (p.character_type + 1) % len(char_assets)
                    p.character_type = new_type
                    asset = char_assets[new_type]
                    p.hp = asset.physics.max_hp
                    p.mp = asset.physics.max_mp
                    session.set_player(controlled_idx, p)
                    player_elapsed_frames[controlled_idx] = 0
                    last_states[controlled_idx] = STATE_IDLE

        # 1. 邏輯推進
        input_mask = get_input_mask()

        if match_result is None:
            if is_offline:
                inputs = [0] * num_players
                inputs[controlled_idx] = input_mask
                session.advance(inputs)
            else:
                session.advance(input_mask)
            if num_players > 1:
                match_result = _check_match(num_players)

        # 2. 渲染
        screen.fill((30, 30, 30))
        pygame.draw.line(screen, (60, 60, 60), (0, 300 + HUD_H),
                         (SCREEN_W, 300 + HUD_H), 1)
        pygame.draw.line(screen, (60, 60, 60), (0, 450 + HUD_H),
                         (SCREEN_W, 450 + HUD_H), 1)

        state_changed: dict[int, bool] = {}
        render_list = []
        for i in range(num_players):
            p = session.get_player(i)
            state_changed[i] = (p.state != last_states[i])
            if state_changed[i]:
                player_elapsed_frames[i] = 0
                last_states[i] = p.state
            elif p.hitstop == 0:
                player_elapsed_frames[i] += 1
            render_list.append((i, p))

        render_list.sort(key=lambda item: item[1].y)

        for original_idx, p in render_list:
            sx, sy = get_screen_pos(p)
            asset = char_assets.get(p.character_type, char_assets[0])
            if p.state == STATE_DEAD:
                sprite = asset.get_sprite(STATE_HURT, 9999, p.facing_right)
                sprite = sprite.copy()
                sprite.set_alpha(80)
            else:
                sprite = asset.get_sprite(
                    p.state, player_elapsed_frames[original_idx], p.facing_right)
            sw, sh = sprite.get_width(), sprite.get_height()
            anchor_x_eff = asset.anchor_x if not p.facing_right else -asset.anchor_x
            blit_x = int(sx - sw // 2 - anchor_x_eff)
            blit_y = int(sy - sh // 2 - asset.anchor_y)
            shadow_x = int(sx - 25)
            shadow_y = int(sy + p.z / 1000.0)
            pygame.draw.ellipse(screen, (10, 10, 10),
                                (shadow_x, shadow_y, 50, 14))
            screen.blit(sprite, (blit_x, blit_y))

            if is_offline and original_idx == controlled_idx:
                pygame.draw.rect(screen, (255, 255, 255),
                                 (blit_x, blit_y, sw, sh), 1)

            # 狀態進入時播放非投射物特效
            if state_changed.get(original_idx):
                ab = asset.get_ability(p.state)
                if ab is not None and ab.projectile_vx == 0 and ab.fx is not None:
                    fxdef = ab.fx
                    hit_def = ab.hit_box
                    if hit_def is not None:
                        fx_x, fx_y = hit_def.screen_center(sx, sy, p.facing_right)
                        fx_x, fx_y = int(fx_x), int(fx_y)
                    else:
                        fx_x = int(sx + (fxdef.offset_x if p.facing_right else -fxdef.offset_x))
                        fx_y = int(sy + fxdef.offset_y)
                    fx_manager.spawn(fxdef.path, fxdef.frame_w, fxdef.frame_h,
                                     fx_x, fx_y, speed=fxdef.speed, scale=fxdef.scale)

            # 判定框 debug 顯示
            if debug_manager.enabled:
                hurt_def = asset.get_hurt_box(p.state)
                if hurt_def:
                    pygame.draw.rect(screen, (0, 255, 0),
                                     hurt_def.to_screen_rect(sx, sy, p.facing_right), 1)

                def _in_hit_window(state: int, timer: int) -> bool:
                    a = asset.get_ability(state)
                    if a is None or not a.melee_enabled:
                        return False
                    spd = asset.speed_map.get(state, 4)
                    elapsed = (a.timer - timer) // spd
                    return a.hit_frame_start <= elapsed <= a.hit_frame_end

                ab_cur = asset.get_ability(p.state)
                melee_on = (ab_cur is not None and ab_cur.melee_enabled
                            and _in_hit_window(p.state, p.timer))
                hit_def = asset.get_hit_box(p.state)
                if hit_def and melee_on:
                    pygame.draw.rect(screen, (255, 50, 50),
                                     hit_def.to_screen_rect(sx, sy, p.facing_right), 1)

        # 渲染投擲物實體
        for eid in range(session.get_entity_count()):
            e = session.get_entity(eid)
            ex = int(e.x / 1000.0)
            ey = int((e.y / 1000.0) - (e.z / 1000.0) + HUD_H)

            owner_asset = char_assets.get(e.character_type, char_assets[0])
            ab = owner_asset.get_ability(e.ability_state_id)
            fxdef    = ab.proj_fx if ab else None
            hit_def  = ab.hit_box if ab else None
            total    = ab.projectile_lifetime if ab else 30

            if hit_def is not None:
                fx_cx, fx_cy = hit_def.entity_screen_center(ex, ey)
            else:
                fx_cx, fx_cy = ex, ey

            # 影子錨定 hitbox 底部
            if hit_def is not None:
                shadow_gy = int(ey + hit_def.oy + hit_def.h + e.z / 1000.0)
            else:
                shadow_gy = int(e.y / 1000.0 + HUD_H)
            shadow_w = max(
                8, int(30 * (fxdef.scale if fxdef is not None else 1.0)))
            pygame.draw.ellipse(screen, (10, 10, 10),
                                (ex - shadow_w // 2, shadow_gy - 4, shadow_w, 8))

            if fxdef is not None:
                elapsed = max(0, total - e.lifetime)
                frames = fx_manager._load(fxdef.path, fxdef.frame_w, fxdef.frame_h)
                idx = (elapsed // max(1, fxdef.speed)) % len(frames)
                frame = frames[idx]
                if e.vx < 0:
                    frame = pygame.transform.flip(frame, True, False)
                if fxdef.scale != 1.0:
                    fw = max(1, int(frame.get_width() * fxdef.scale))
                    fh = max(1, int(frame.get_height() * fxdef.scale))
                    frame = pygame.transform.scale(frame, (fw, fh))
                screen.blit(frame, (int(fx_cx) - frame.get_width() // 2,
                                    int(fx_cy) - frame.get_height() // 2))
            else:
                pygame.draw.circle(screen, (255, 100, 0),
                                   (int(fx_cx), int(fx_cy)), 10)
                pygame.draw.circle(screen, (255, 220, 60),
                                   (int(fx_cx), int(fx_cy)), 6)

            if debug_manager.enabled and hit_def:
                pygame.draw.rect(screen, (255, 50, 50),
                                 hit_def.to_entity_screen_rect(ex, ey), 1)

        fx_manager.update_and_draw(screen)
        hud.draw(screen, render_list)
        debug_manager.draw(screen, session, render_list, clock.get_fps())

        # 同步等待提示
        if not is_offline and not session.is_synchronized():
            sync_wait_frames += 1
            if sync_wait_frames % (60 * 5) == 0:
                remotes = [(p["id"], p["ip"], p["port"]) for p in config.get(
                    "players", []) if p["id"] != controlled_idx]
                print(
                    f"[SYNC] waiting... {sync_wait_frames//60}s  my_port={config['local_port']}  remotes={remotes}")

            overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            screen.blit(overlay, (0, 0))
            cx, cy = SCREEN_W // 2, SCREEN_H // 2
            wait_font = pygame.font.SysFont("Arial", 36, bold=True)
            text_surf = wait_font.render("WAITING FOR SYNC...", True, (255, 255, 0))
            screen.blit(text_surf, text_surf.get_rect(center=(cx, cy)))

            info_font = pygame.font.SysFont("Arial", 16)
            remotes_str = "  ".join(f"id={p['id']} {p['ip']}:{p['port']}" for p in config.get(
                "players", []) if p["id"] != controlled_idx)
            info1 = info_font.render(
                f"My id={controlled_idx}  local_port={config['local_port']}", True, (200, 200, 200))
            info2 = info_font.render(f"Remote: {remotes_str}", True, (200, 200, 200))
            info3 = info_font.render(f"Waiting {sync_wait_frames // 60}s", True, (150, 150, 150))
            screen.blit(info1, info1.get_rect(center=(cx, cy + 50)))
            screen.blit(info2, info2.get_rect(center=(cx, cy + 75)))
            screen.blit(info3, info3.get_rect(center=(cx, cy + 100)))

        # 結算畫面
        if match_result is not None:
            ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 160))
            screen.blit(ov, (0, 0))
            cx, cy = SCREEN_W // 2, SCREEN_H // 2
            if match_result == -2:
                msg = "DRAW!"
                color = (200, 200, 200)
            else:
                name = player_names.get(match_result, f"Player {match_result + 1}")
                char_name = char_assets.get(
                    session.get_player(match_result).character_type,
                    char_assets[0]).name
                msg = f"{name}  ({char_name})  WINS!"
                color = (255, 220, 60)
            big_surf = result_font_big.render(msg, True, color)
            screen.blit(big_surf, big_surf.get_rect(center=(cx, cy - 20)))
            hint = "R: Restart  ESC: Quit" if is_offline else "ESC: Quit"
            sm_surf = result_font_small.render(hint, True, (180, 180, 180))
            screen.blit(sm_surf, sm_surf.get_rect(center=(cx, cy + 50)))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    run_game()
