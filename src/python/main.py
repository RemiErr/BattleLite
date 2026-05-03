import pygame
import sys
import os
import argparse
import json
import threading
import urllib.request

if getattr(sys, 'frozen', False):
    PROJECT_ROOT = sys._MEIPASS
else:
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
    from src.python.sfx_manager import SfxManager
    from src.python.crypto_utils import SHARED_SECRET
    from src.python.game_constants import (
        STATE_IDLE, STATE_WALK, STATE_ATTACK, STATE_HURT, STATE_SKILL, STATE_DEAD)
    from src.python.ai.controllers.base import AIController
    from src.python.ai.factory import make_ai
except ImportError as e:
    print(f"[ERR] 匯入失敗: {e}")
    sys.exit(1)

# --- 輸入常數 ---
INPUT_RIGHT, INPUT_LEFT, INPUT_UP, INPUT_DOWN, INPUT_JUMP, INPUT_ATTACK, INPUT_SKILL = [
    1 << i for i in range(7)]

# --- 世界邊界與出生點 ---
WORLD_PX_W = SCREEN_W * 3        # 橫向世界寬度（3 個畫面寬）
WORLD_X_MIN = 0
WORLD_X_MAX = WORLD_PX_W * 1000
WORLD_Y_MIN = 250_000
WORLD_Y_MAX = 520_000
# 最多 4 人的初始出生位置（世界中央左右各散開）
_SPAWN_X = [1_336_000, 1_736_000, 1_136_000, 1_936_000]
_SPAWN_Y = [385_000,   385_000,   370_000,   400_000]


def apply_char_config(session, char_type: int, asset: BaseCharacter) -> None:
    """PhysicsStats + AbilityDef → Rust PhysicsConfig + AbilityConfig。"""
    p = asset.physics

    # Hurt box 從 STATE_IDLE 推導（所有狀態共用同一 Rust hurt box）
    hurt_hb = asset.hurt_boxes.get(STATE_IDLE) or next(
        iter(asset.hurt_boxes.values()), None)
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
        hit_end = ab.hit_frame_end * spd
        dash_tick = ab.dash_frame * spd
        # spawn_timer：幀索引優先於舊版 timer 倒數值
        spawn_timer = (ab.timer - ab.spawn_frame * spd
                       if ab.spawn_frame >= 0 else ab.spawn_timer_raw)

        if ab.hit_box is not None:
            ab_f, ab_hw, ab_hh, ab_zo = ab.hit_box.to_rust_params()
        else:
            ab_f, ab_hw, ab_hh, ab_zo = 0, 0, 0, 0

        entity_offset = (ab.proj_fx.offset_x * 1000) if ab.proj_fx else 0
        entity_z_offset = (ab.proj_fx.offset_y * 1000) if ab.proj_fx else 0

        session.set_ability(
            char_type, slot_idx,
            ab.trigger_button, ab.trigger_context, ab.state_id,
            ab.mp_cost, ab.timer,
            ab.dmg, ab_f, ab_hw, ab.depth, ab_hh, ab_zo,
            ab.kb_vx, ab.kb_vz, ab.kb_timer,
            ab.melee_enabled, hit_start, hit_end,
            ab.damage_absorb, ab.hp_regen, ab.on_hit_restore,
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


_KEY_PRESETS = [
    # Preset 0: 方向鍵 + Z/X + Space
    {INPUT_RIGHT: pygame.K_RIGHT, INPUT_LEFT: pygame.K_LEFT,
     INPUT_UP: pygame.K_UP,       INPUT_DOWN: pygame.K_DOWN,
     INPUT_JUMP: pygame.K_SPACE,  INPUT_ATTACK: pygame.K_z, INPUT_SKILL: pygame.K_x},
    # Preset 1: WASD + J/K + Space
    {INPUT_RIGHT: pygame.K_d,    INPUT_LEFT: pygame.K_a,
     INPUT_UP: pygame.K_w,       INPUT_DOWN: pygame.K_s,
     INPUT_JUMP: pygame.K_SPACE, INPUT_ATTACK: pygame.K_j, INPUT_SKILL: pygame.K_k},
]


def get_input_mask(key_map: dict) -> int:
    keys = pygame.key.get_pressed()
    mask = 0
    for bit, k in key_map.items():
        if keys[k]:
            mask |= bit
    return mask


def _set_spawn_positions(session, num_players: int):
    for i in range(num_players):
        p = session.get_player(i)
        p.x = _SPAWN_X[i] if i < len(_SPAWN_X) else WORLD_X_MAX // 2
        p.y = _SPAWN_Y[i] if i < len(_SPAWN_Y) else 385_000
        p.vx = p.vy = p.vz = 0
        session.set_player(i, p)


def _clamp_world_bounds(session, num_players: int):
    for i in range(num_players):
        p = session.get_player(i)
        changed = False
        if p.x < WORLD_X_MIN:
            p.x, p.vx = WORLD_X_MIN, 0
            changed = True
        elif p.x > WORLD_X_MAX:
            p.x, p.vx = WORLD_X_MAX, 0
            changed = True
        if p.y < WORLD_Y_MIN:
            p.y, p.vy = WORLD_Y_MIN, 0
            changed = True
        elif p.y > WORLD_Y_MAX:
            p.y, p.vy = WORLD_Y_MAX, 0
            changed = True
        if changed:
            session.set_player(i, p)


def _submit_result(config: dict, controlled_idx: int, char_type: int, match_result: int):
    lobby_url = config.get("lobby_url", "")
    match_id = config.get("match_id", "")
    if not lobby_url or not match_id:
        return
    if match_result == controlled_idx:
        result = "win"
    elif match_result == -2:
        result = "draw"
    else:
        result = "lose"
    payload = json.dumps({
        "match_id":  match_id,
        "room_code": config.get("room", ""),
        "nickname":  config.get("nickname", "Player"),
        "char_type": char_type,
        "result":    result,
    }).encode()
    try:
        req = urllib.request.Request(
            f"{lobby_url}/submit_result", data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=5)
        print(f"[OK] Result submitted: {result}")
    except Exception as e:
        print(f"[WARN] Failed to submit result: {e}")


def run_game():
    args = parse_args()

    # 預設啟動設定（離線開發用，P1~P3 為 FSM lv1 AI）
    config = {
        "nickname": "DevPlayer",
        "is_offline": True,
        "local_id": 0,
        "num_players": 4,
        "local_port": 5000,
        "ai_players": {
            "1": {"char_type": 1, "level": 3},
            "2": {"char_type": 4, "level": 2},
            "3": {"char_type": 0, "level": 1},
        }
    }

    if args.payload:
        try:
            decrypted_str = battlelite_core.decrypt_payload(
                args.payload, SHARED_SECRET)
            config.update(json.loads(decrypted_str))
            print(f"[OK] Session Handoff Success: Hello {config['nickname']}")
        except Exception as e:
            print(f"[ERR] Handshake Decryption Failed: {e}")
            sys.exit(1)

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption(f"BattleLite - {config['nickname']}")
    clock = pygame.time.Clock()
    debug_manager = DebugManager()
    fx_manager = FxManager()

    # 從 settings.json 讀音量與按鍵組合
    _settings_path = os.path.join(PROJECT_ROOT, 'settings.json')
    _vol = 50
    _preset_idx = 0
    if os.path.exists(_settings_path):
        try:
            with open(_settings_path) as _f:
                _s = json.load(_f)
                _vol = _s.get("volume", 50)
                _preset_idx = int(_s.get("key_preset", 0))
        except Exception:
            pass
    sfx_manager = SfxManager(volume=_vol / 100.0)
    key_map = _KEY_PRESETS[_preset_idx % len(_KEY_PRESETS)]

    char_assets: dict[int, BaseCharacter] = {
        0: Knight(), 1: Mage(), 2: Archer(), 3: Paladin(), 4: Wizard()}

    # 建立玩家名稱對照表
    player_names: dict[int, str] = {
        config["local_id"]: config.get("nickname", "Player")}
    for p_info in config.get("players", []):
        if "nickname" in p_info:
            player_names[p_info["id"]] = p_info["nickname"]
    hud = HUD(char_assets, player_names=player_names)
    for ct, asset in char_assets.items():
        sfx_manager.register(ct, asset.sfx)

    # --- Session 工廠 ---
    is_offline = config["is_offline"]
    num_players = config["num_players"]
    controlled_idx = config["local_id"]
    host_id = config.get("host_id", 0)
    i_am_host = is_offline or (controlled_idx == host_id)

    if is_offline:
        print("[Mode] Offline Sandbox (Pure Rust Simulation)")
        session = OfflineSession(num_players)
        for char_type, asset in char_assets.items():
            apply_char_config(session, char_type, asset)
    else:
        print("[Mode] Online P2P (GGRS Rollback)")
        print(
            f"  local_id={controlled_idx}  local_port={config['local_port']}")
        ai_player_ids = [int(k) for k in config.get("ai_players", {}).keys()]
        remote_players_list = []
        if "players" in config:
            for p in config["players"]:
                remote_players_list.append((p["id"], p["ip"], p["port"]))
                tag = "← me" if p["id"] == controlled_idx else "→ remote"
                print(f"  player id={p['id']}  {p['ip']}:{p['port']}  {tag}")
        if not i_am_host and ai_player_ids:
            # 非 host：AI 輸入由 host 發送，以 host 的地址將 AI 槽位注冊為 Remote
            host_player = next((p for p in config.get("players", [])
                                if p["id"] == host_id), None)
            if host_player:
                for pid in ai_player_ids:
                    remote_players_list.append(
                        (pid, host_player["ip"], host_player["port"]))
                    print(f"  player id={pid}  (AI @ host)  {host_player['ip']}:{host_player['port']}")
        bot_ids_for_session = ai_player_ids if i_am_host else []
        session = GGRSSession(controlled_idx, num_players,
                              config["local_port"], remote_players_list,
                              bot_ids_for_session)
        for char_type, asset in char_assets.items():
            apply_char_config(session, char_type, asset)

    # 線上模式：依 payload 的 char_type 初始化各玩家角色
    if not is_offline:
        for p_info in config.get("players", []):
            pid = p_info.get("id", 0)
            ct = p_info.get("char_type", 0)
            if 0 <= pid < num_players and ct in char_assets:
                p = session.get_player(pid)
                p.character_type = ct
                p.hp = char_assets[ct].physics.max_hp
                p.mp = char_assets[ct].physics.max_mp
                session.set_player(pid, p)

    # AI 玩家初始化
    ai_controllers: dict[int, AIController] = {}
    seed = config.get("seed", 0)
    for p_id_str, ai_info in config.get("ai_players", {}).items():
        pid = int(p_id_str)
        ct = ai_info.get("char_type", 0)
        if 0 <= pid < num_players and ct in char_assets:
            p = session.get_player(pid)
            p.character_type = ct
            p.hp = char_assets[ct].physics.max_hp
            p.mp = char_assets[ct].physics.max_mp
            session.set_player(pid, p)
            # 線上模式只有 host 負責產生 AI 輸入；非 host 靠 GGRS rollback 接收
            if is_offline or i_am_host:
                ai_controllers[pid] = make_ai(ct, ai_info.get("level", 1), seed)

    _set_spawn_positions(session, num_players)

    player_elapsed_frames = [0] * num_players
    last_states = [STATE_IDLE] * num_players
    sync_wait_frames = 0
    switch_player = 0
    match_result: int | None = None  # None=進行中, -2=平手, 0..n=勝者 idx
    _result_submitted = False
    result_font_big = pygame.font.SysFont("Arial", 56, bold=True)
    result_font_small = pygame.font.SysFont("Arial", 24)

    def _check_match(n: int) -> int | None:
        alive = [i for i in range(n) if session.get_player(
            i).state != STATE_DEAD]
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
            p.hp = asset.physics.max_hp
            p.mp = asset.physics.max_mp
            p.state = STATE_IDLE
            p.timer = 0
            p.z = 0
            session.set_player(i, p)
        _set_spawn_positions(session, num_players)
        match_result = None
        player_elapsed_frames = [0] * num_players
        last_states = [STATE_IDLE] * num_players

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                    continue
                if match_result is not None:
                    if event.key == pygame.K_r and is_offline:
                        _restart_offline()
                    continue
                if event.key == pygame.K_F1:
                    debug_manager.toggle()
                if event.key == pygame.K_F2 and is_offline:
                    player_names.pop(controlled_idx, None)
                    switch_player = (switch_player + 1) % num_players
                    controlled_idx = switch_player
                    player_names[controlled_idx] = config.get(
                        "nickname", "Player")
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
        input_mask = get_input_mask(key_map)

        if match_result is None:
            prev_z = [session.get_player(i).z for i in range(num_players)]
            prev_entity_count = session.get_entity_count()

            if is_offline:
                inputs = []
                for pid in range(num_players):
                    if pid == controlled_idx:
                        inputs.append(input_mask)
                    elif pid in ai_controllers:
                        ai_p = session.get_player(pid)
                        entities = [session.get_entity(i)
                                    for i in range(session.get_entity_count())]
                        alive_opponents = [
                            session.get_player(j)
                            for j in range(num_players)
                            if j != pid
                            and session.get_player(j).state != STATE_DEAD
                        ]
                        opp_p = min(
                            alive_opponents,
                            key=lambda q: max(
                                abs(ai_p.x - q.x), abs(ai_p.y - q.y)),
                            default=session.get_player(controlled_idx),
                        )
                        inputs.append(ai_controllers[pid].decide(
                            ai_p, opp_p, entities))
                    else:
                        inputs.append(0)
                session.advance(inputs)
            else:
                bot_inputs = []
                for pid, controller in ai_controllers.items():
                    ai_p = session.get_player(pid)
                    entities = [session.get_entity(i)
                                for i in range(session.get_entity_count())]
                    alive_opponents = [
                        session.get_player(j)
                        for j in range(num_players)
                        if j != pid
                        and session.get_player(j).state != STATE_DEAD
                    ]
                    opp_p = min(
                        alive_opponents,
                        key=lambda q: max(
                            abs(ai_p.x - q.x), abs(ai_p.y - q.y)),
                        default=session.get_player(controlled_idx),
                    )
                    bot_inputs.append((pid, controller.decide(ai_p, opp_p, entities)))
                session.advance(input_mask, bot_inputs if bot_inputs else None)
            _clamp_world_bounds(session, num_players)

            # --- SFX 事件偵測 ---
            for i in range(num_players):
                p = session.get_player(i)
                ct = p.character_type
                old_state = last_states[i]
                if p.state != old_state:
                    if p.state == STATE_HURT:
                        sfx_manager.on_hurt(ct)
                        # 找近戰攻擊方：上一幀處於 melee ability 狀態的玩家
                        for j in range(num_players):
                            if j == i:
                                continue
                            atk = session.get_player(j)
                            ab = char_assets.get(
                                atk.character_type, char_assets[0]).get_ability(last_states[j])
                            if ab and ab.melee_enabled:
                                sfx_manager.on_hit(
                                    atk.character_type, last_states[j])
                                break
                    elif p.state == STATE_DEAD:
                        sfx_manager.on_dead(ct)
                    elif p.state not in (STATE_IDLE, STATE_WALK):
                        sfx_manager.on_ability(ct, p.state)
                if prev_z[i] == 0 and p.z > 0 and p.state not in (STATE_HURT, STATE_DEAD):
                    sfx_manager.on_jump(ct)
                if prev_z[i] > 0 and p.z == 0:
                    sfx_manager.on_land(ct)

            for eid in range(prev_entity_count, session.get_entity_count()):
                e = session.get_entity(eid)
                sfx_manager.on_proj(e.character_type, e.ability_state_id)
            # --- SFX 事件偵測結束 ---

            if num_players > 1:
                match_result = _check_match(num_players)
                if match_result is not None and not _result_submitted and not is_offline:
                    _result_submitted = True
                    ct = session.get_player(controlled_idx).character_type
                    threading.Thread(
                        target=_submit_result,
                        args=(config, controlled_idx, ct, match_result),
                        daemon=True,
                    ).start()

        # 2. 渲染
        # 鏡頭：跟隨受控角色，夾在世界邊界內
        _ctrl_p = session.get_player(controlled_idx)
        cam_x = _ctrl_p.x / 1000.0 - SCREEN_W / 2
        cam_x = max(0.0, min(cam_x, float(WORLD_PX_W - SCREEN_W)))

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
            sx -= cam_x
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

            if is_offline and debug_manager.enabled and original_idx == controlled_idx:
                pygame.draw.rect(screen, (255, 255, 255),
                                 (blit_x, blit_y, sw, sh), 1)

            # 狀態進入時播放非投射物特效
            if state_changed.get(original_idx):
                ab = asset.get_ability(p.state)
                if ab is not None and ab.projectile_vx == 0 and ab.fx is not None:
                    fxdef = ab.fx
                    hit_def = ab.hit_box
                    if hit_def is not None:
                        fx_x, fx_y = hit_def.screen_center(
                            sx, sy, p.facing_right)
                        fx_x, fx_y = int(fx_x), int(fx_y)
                    else:
                        fx_x = int(
                            sx + (fxdef.offset_x if p.facing_right else -fxdef.offset_x))
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
            ex = int(e.x / 1000.0 - cam_x)
            ey = int((e.y / 1000.0) - (e.z / 1000.0) + HUD_H)

            owner_asset = char_assets.get(e.character_type, char_assets[0])
            ab = owner_asset.get_ability(e.ability_state_id)
            fxdef = ab.proj_fx if ab else None
            hit_def = ab.hit_box if ab else None
            total = ab.projectile_lifetime if ab else 30

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
                frames = fx_manager._load(
                    fxdef.path, fxdef.frame_w, fxdef.frame_h)
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
        debug_manager.draw(screen, session, render_list,
                           clock.get_fps(), ai_controllers)

        # 同步等待提示
        if not is_offline and not session.is_synchronized():
            sync_wait_frames += 1
            if sync_wait_frames == 1:
                remotes = [(p["id"], p["ip"], p["port"]) for p in config.get(
                    "players", []) if p["id"] != controlled_idx]
                print(
                    f"[SYNC] start  my_id={controlled_idx}  my_port={config['local_port']}  remotes={remotes}")
            elif sync_wait_frames % (60 * 5) == 0:
                remotes = [(p["id"], p["ip"], p["port"]) for p in config.get(
                    "players", []) if p["id"] != controlled_idx]
                print(
                    f"[SYNC] waiting... {sync_wait_frames//60}s  my_port={config['local_port']}  remotes={remotes}")

            overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            screen.blit(overlay, (0, 0))
            cx, cy = SCREEN_W // 2, SCREEN_H // 2
            wait_font = pygame.font.SysFont("Arial", 36, bold=True)
            text_surf = wait_font.render(
                "WAITING FOR SYNC...", True, (255, 255, 0))
            screen.blit(text_surf, text_surf.get_rect(center=(cx, cy)))

            info_font = pygame.font.SysFont("Arial", 16)
            remotes_str = "  ".join(f"id={p['id']} {p['ip']}:{p['port']}" for p in config.get(
                "players", []) if p["id"] != controlled_idx)
            info1 = info_font.render(
                f"My id={controlled_idx}  local_port={config['local_port']}", True, (200, 200, 200))
            info2 = info_font.render(
                f"Remote: {remotes_str}", True, (200, 200, 200))
            info3 = info_font.render(
                f"Waiting {sync_wait_frames // 60}s", True, (150, 150, 150))
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
                name = player_names.get(
                    match_result, f"Player {match_result + 1}")
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

    del session  # 確保 GGRS UDP socket 在 pygame.quit() 前釋放
    pygame.quit()


if __name__ == "__main__":
    run_game()
