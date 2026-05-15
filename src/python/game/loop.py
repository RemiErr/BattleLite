import os
import sys
import math
import json
import threading
import time
import datetime

import pygame

from src.python.app_root import PROJECT_ROOT
from src.python.renderer import get_screen_pos
from src.python.debug_manager import DebugManager
from src.python.hud import HUD, SCREEN_W, SCREEN_H, HUD_H
from src.python.fx_manager import FxManager
from src.python.sfx_manager import SfxManager
from src.python.game_constants import (
    STATE_IDLE, STATE_WALK, STATE_HURT, STATE_DEAD)
from src.python.ai.controllers.base import AIController
from src.python.ai.factory import make_ai
from src.python.game.input_manager import get_input_mask, load_key_map
from src.python.game.match_manager import MatchManager
from src.python.replay.writer import ReplayWriter
from src.python.replay.reader import ReplayReader

# --- 世界邊界與出生點 ---
WORLD_PX_W  = SCREEN_W * 3
WORLD_X_MIN = 0
WORLD_X_MAX = WORLD_PX_W * 1000
WORLD_Y_MIN = 250_000
WORLD_Y_MAX = 520_000
_SPAWN_X = [1_336_000, 1_736_000, 1_136_000, 1_936_000]
_SPAWN_Y = [385_000,   385_000,   370_000,   400_000]
_ARROW_ABOVE_SHADOW = 120


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
    import urllib.request
    lobby_url = config.get("lobby_url", "")
    match_id  = config.get("match_id", "")
    if not lobby_url or not match_id:
        return
    if match_result == controlled_idx:
        result = "win"
    elif match_result == -2:
        result = "draw"
    else:
        result = "lose"
    num_human = config.get("num_players", 2) - len(config.get("ai_players", {}))
    payload = json.dumps({
        "match_id":    match_id,
        "room_code":   config.get("room", ""),
        "nickname":    config.get("nickname", "Player"),
        "char_type":   char_type,
        "result":      result,
        "player_id":   controlled_idx,
        "num_players": max(1, num_human),
    }).encode()
    try:
        req = urllib.request.Request(
            f"{lobby_url}/submit_result", data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=5)
        print(f"[OK] Result submitted: {result}")
    except Exception as e:
        print(f"[WARN] Failed to submit result: {e}")


def run_loop(config: dict, build_char_assets, build_session) -> None:
    """遊戲主迴圈。

    build_char_assets() → dict[int, BaseCharacter]
    build_session(char_assets) → SessionAdapter

    兩個 factory 在 pygame.display.set_mode() 之後才呼叫，以確保
    pygame.image.convert_alpha() 可正常執行。
    """
    # --- pygame 初始化 ---
    pygame.init()

    game_icon_path = os.path.join(PROJECT_ROOT, "src/assets/img/game.png")
    if os.path.exists(game_icon_path):
        try:
            pygame.display.set_icon(pygame.image.load(game_icon_path))
        except Exception as e:
            print(f"[WARN] Failed to set game window icon: {e}")

    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption(f"BattleLite - {config['nickname']}")
    clock = pygame.time.Clock()
    debug_manager = DebugManager()
    fx_manager    = FxManager()

    # --- 角色資源與 Session（需在 display 初始化後建立）---
    char_assets = build_char_assets()
    session     = build_session(char_assets)

    # --- 載入設定（音量 + 按鍵組合）---
    if getattr(sys, 'frozen', False):
        _settings_path = os.path.join(os.path.dirname(sys.executable), 'settings.json')
    else:
        _settings_path = os.path.join(PROJECT_ROOT, 'settings.json')
    _vol, _preset_idx = 50, 0
    _bg_enabled, _bg_id = True, 1
    if os.path.exists(_settings_path):
        try:
            with open(_settings_path) as f:
                s = json.load(f)
                _vol        = s.get("volume", 50)
                _preset_idx = int(s.get("key_preset", 0))
                _bg_enabled = s.get("background_enabled", True)
                _bg_id      = int(s.get("background_id", 1))
        except Exception:
            pass

    sfx_manager = SfxManager(volume=_vol / 100.0)
    key_map     = load_key_map(_preset_idx)

    _BG_PARALLAX = 0.3
    _BG_W        = SCREEN_W + int((WORLD_PX_W - SCREEN_W) * _BG_PARALLAX) + 1
    _bg_surface  = None
    if _bg_enabled:
        _bg_path = os.path.join(PROJECT_ROOT, "src", "assets", "background", f"{_bg_id}.png")
        if os.path.exists(_bg_path):
            try:
                _raw = pygame.image.load(_bg_path).convert()
                _bg_surface = pygame.transform.scale(
                    _raw, (_BG_W, _raw.get_height()))
            except Exception as e:
                print(f"[WARN] 背景圖載入失敗: {e}")

    # --- HUD、SFX 初始化 ---
    player_names: dict[int, str] = {config["local_id"]: config.get("nickname", "Player")}
    for p_info in config.get("players", []):
        if "nickname" in p_info:
            player_names[p_info["id"]] = p_info["nickname"]
    hud = HUD(char_assets, player_names=player_names)
    for ct, asset in char_assets.items():
        sfx_manager.register(ct, asset.sfx)

    _arrow_path = os.path.join(PROJECT_ROOT, "src", "assets", "HUD", "arrow-down.png")
    try:
        _arrow_img = pygame.image.load(_arrow_path).convert_alpha()
    except Exception:
        _arrow_img = None

    # --- 字型 ---
    font_path = os.path.join(PROJECT_ROOT, "src/assets/fonts/NotoSansTC-VariableFont_wght.ttf")
    if os.path.exists(font_path):
        result_font_big   = pygame.font.SysFont("Arial", 56, bold=True)
        result_font_small = pygame.font.Font(font_path, 24)
        wait_font         = pygame.font.SysFont("Arial", 36, bold=True)
        info_font         = pygame.font.Font(font_path, 16)
    else:
        result_font_big   = pygame.font.SysFont("Arial", 56, bold=True)
        result_font_small = pygame.font.SysFont("Arial", 24)
        wait_font         = pygame.font.SysFont("Arial", 36, bold=True)
        info_font         = pygame.font.SysFont("Arial", 16)

    # --- 場次設定 ---
    is_offline     = config["is_offline"]
    num_players    = config["num_players"]
    controlled_idx = config["local_id"]
    host_id        = config.get("host_id", 0)
    i_am_host      = is_offline or (controlled_idx == host_id)
    is_replay      = bool(config.get("replay_path"))

    # 線上模式或重播：依 payload / replay header 初始化各玩家角色
    if not is_offline or is_replay:
        for p_info in config.get("players", []):
            pid = p_info.get("id", 0)
            ct  = p_info.get("char_type", 0)
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
        ct  = ai_info.get("char_type", 0)
        if 0 <= pid < num_players and ct in char_assets:
            p = session.get_player(pid)
            p.character_type = ct
            p.hp = char_assets[ct].physics.max_hp
            p.mp = char_assets[ct].physics.max_mp
            session.set_player(pid, p)
            if is_offline or i_am_host:
                ai_controllers[pid] = make_ai(ct, ai_info.get("level", 1), seed)

    _set_spawn_positions(session, num_players)

    mm = MatchManager(session, num_players, char_assets, fx_manager, hud)
    switch_player    = 0
    sync_wait_frames = 0

    # --- 重播系統 ---
    _replay_writer: ReplayWriter | None = None
    if not is_offline and not is_replay:
        _rp_players = [{"id": p["id"], "nickname": p.get("nickname", ""),
                        "char_type": p.get("char_type", 0)}
                       for p in config.get("players", [])]
        for _pid_str, _ai in config.get("ai_players", {}).items():
            _rp_players.append({"id": int(_pid_str), "nickname": "CPU",
                                 "char_type": _ai.get("char_type", 0)})
        _rp_players.sort(key=lambda x: x["id"])
        _replay_writer = ReplayWriter({
            "version":     1,
            "timestamp":   datetime.datetime.now().isoformat(timespec="seconds"),
            "match_id":    config.get("match_id", ""),
            "room_code":   config.get("room", ""),
            "room_type":   "ranked" if config.get("room", "").startswith("__queue_") else "custom",
            "num_players": num_players,
            "seed":        config.get("seed", 0),
            "players":     _rp_players,
        })
    _reader: ReplayReader | None = ReplayReader(config["replay_path"]) if is_replay else None
    _replay_paused  = False
    _replay_speed   = 1.0
    _advance_budget = 0.0

    _perf_enabled = os.environ.get("DEBUG_PERF") == "1"
    _frame_times: list[float] = []

    # ================================================================
    # 主迴圈
    # ================================================================
    running = True
    while running:
        _t0 = time.perf_counter() if _perf_enabled else 0.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                    continue
                # 重播控制鍵
                if is_replay:
                    if event.key == pygame.K_p:
                        _replay_paused = not _replay_paused
                        continue
                    if event.key == pygame.K_1:
                        _replay_speed = 0.5
                        continue
                    if event.key == pygame.K_2:
                        _replay_speed = 1.0
                        continue
                    if event.key == pygame.K_3:
                        _replay_speed = 2.0
                        continue
                if event.key == pygame.K_p and is_offline:
                    mm.paused = not mm.paused
                    continue
                if mm.paused:
                    continue
                if mm.match_result is not None:
                    if event.key == pygame.K_r and is_offline:
                        if is_replay:
                            _reader = ReplayReader(config["replay_path"])
                            _advance_budget = 0.0
                            _replay_paused  = False
                        mm.restart(_set_spawn_positions)
                    continue
                if event.key == pygame.K_F1 and is_offline:
                    debug_manager.toggle()
                if event.key == pygame.K_F2 and is_offline:
                    player_names.pop(controlled_idx, None)
                    switch_player  = (switch_player + 1) % num_players
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
                    mm.player_elapsed_frames[controlled_idx] = 0
                    mm.last_states[controlled_idx] = STATE_IDLE

        # 1. 邏輯推進
        input_mask = get_input_mask(key_map)
        if mm.countdown_frames > 0 and (is_offline or session.is_synchronized()):
            mm.countdown_frames -= 1
            input_mask = 0

        if mm.match_result is None and not mm.paused and mm.countdown_frames == 0:
            prev_z            = [session.get_player(i).z for i in range(num_players)]
            prev_entity_count = session.get_entity_count()

            if is_replay:
                assert _reader is not None
                if not _replay_paused:
                    _advance_budget += _replay_speed
                    while _advance_budget >= 1.0:
                        inp = _reader.next_inputs()
                        if inp is None:
                            mm.match_result = -2
                            break
                        session.advance(inp)
                        _clamp_world_bounds(session, num_players)
                        _advance_budget -= 1.0

            elif is_offline:
                entities_snapshot = [session.get_entity(i)
                                     for i in range(session.get_entity_count())]
                goap_replan_budget = 1
                inputs = []
                for pid in range(num_players):
                    if pid == controlled_idx:
                        inputs.append(input_mask)
                    elif pid in ai_controllers:
                        ai_p = session.get_player(pid)
                        alive_opponents = [
                            session.get_player(j)
                            for j in range(num_players)
                            if j != pid and session.get_player(j).state != STATE_DEAD
                        ]
                        opp_p = min(
                            alive_opponents,
                            key=lambda q: max(abs(ai_p.x - q.x), abs(ai_p.y - q.y)),
                            default=session.get_player(controlled_idx),
                        )
                        ctrl = ai_controllers[pid]
                        if hasattr(ctrl, 'set_replan_budget'):
                            ctrl.set_replan_budget(goap_replan_budget > 0)
                        mask = ctrl.decide(ai_p, opp_p, entities_snapshot)
                        if getattr(ctrl, 'did_replan', False):
                            goap_replan_budget -= 1
                        inputs.append(mask)
                    else:
                        inputs.append(0)
                session.advance(inputs)
                _clamp_world_bounds(session, num_players)

            else:
                inputs = [0] * num_players
                inputs[controlled_idx] = input_mask
                entities_snapshot = [session.get_entity(i)
                                     for i in range(session.get_entity_count())]
                goap_replan_budget = 1
                for pid, controller in ai_controllers.items():
                    ai_p = session.get_player(pid)
                    alive_opponents = [
                        session.get_player(j)
                        for j in range(num_players)
                        if j != pid and session.get_player(j).state != STATE_DEAD
                    ]
                    opp_p = min(
                        alive_opponents,
                        key=lambda q: max(abs(ai_p.x - q.x), abs(ai_p.y - q.y)),
                        default=session.get_player(controlled_idx),
                    )
                    if hasattr(controller, 'set_replan_budget'):
                        controller.set_replan_budget(goap_replan_budget > 0)
                    mask = controller.decide(ai_p, opp_p, entities_snapshot)
                    if getattr(controller, 'did_replan', False):
                        goap_replan_budget -= 1
                    inputs[pid] = mask
                session.advance(inputs)
                if _replay_writer:
                    _replay_writer.append_frame(session.get_last_inputs())
                _clamp_world_bounds(session, num_players)

            # --- SFX 事件偵測 ---
            for i in range(num_players):
                p      = session.get_player(i)
                ct     = p.character_type
                old_st = mm.last_states[i]
                if p.state != old_st:
                    if p.state == STATE_HURT:
                        sfx_manager.on_hurt(ct)
                        for j in range(num_players):
                            if j == i:
                                continue
                            atk = session.get_player(j)
                            ab  = char_assets.get(
                                atk.character_type, char_assets[0]).get_ability(mm.last_states[j])
                            if ab and ab.melee_enabled:
                                sfx_manager.on_hit(atk.character_type, mm.last_states[j])
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

            if num_players > 1 and mm.match_result is None:
                r = mm.check_match()
                if r is not None:
                    mm.match_result = r
                    if _replay_writer:
                        _replay_writer.finalize(mm.match_result)
                        _replay_writer = None
                    if not mm._result_submitted and not is_offline:
                        mm._result_submitted = True
                        ct = session.get_player(controlled_idx).character_type
                        threading.Thread(
                            target=_submit_result,
                            args=(config, controlled_idx, ct, mm.match_result),
                            daemon=True,
                        ).start()

        # 2. 渲染
        _ctrl_p = session.get_player(controlled_idx)
        cam_x   = _ctrl_p.x / 1000.0 - SCREEN_W / 2
        cam_x   = max(0.0, min(cam_x, float(WORLD_PX_W - SCREEN_W)))

        # --- 背景與場景 ---
        floor_y_min = WORLD_Y_MIN // 1000 + HUD_H
        floor_y_max = WORLD_Y_MAX // 1000 + HUD_H
        screen.fill((15, 15, 15))
        if _bg_surface is not None:
            screen.blit(_bg_surface, (int(-cam_x * _BG_PARALLAX), HUD_H))
        pygame.draw.rect(screen, (30, 30, 30),
                         (0, floor_y_min, SCREEN_W, floor_y_max - floor_y_min))
        line_col  = (80, 80, 80) if _bg_surface else (45, 45, 45)
        line_col2 = (95, 95, 95) if _bg_surface else (55, 55, 55)
        pygame.draw.line(screen, line_col,  (0, floor_y_min), (SCREEN_W, floor_y_min), 1)
        pygame.draw.line(screen, line_col,  (0, floor_y_max), (SCREEN_W, floor_y_max), 1)
        pygame.draw.line(screen, line_col2, (0, 300 + HUD_H),  (SCREEN_W, 300 + HUD_H),  1)
        pygame.draw.line(screen, line_col2, (0, 450 + HUD_H),  (SCREEN_W, 450 + HUD_H),  1)

        state_changed: dict[int, bool] = {}
        render_list = []
        for i in range(num_players):
            p = session.get_player(i)
            state_changed[i] = (p.state != mm.last_states[i])
            if state_changed[i]:
                mm.player_elapsed_frames[i] = 0
                mm.last_states[i]           = p.state
            elif p.hitstop == 0:
                mm.player_elapsed_frames[i] += 1
            render_list.append((i, p))
        render_list.sort(key=lambda item: item[1].y)

        # --- [Phase 1] 影子層 ---
        for original_idx, p in render_list:
            sx, sy = get_screen_pos(p)
            sx -= cam_x
            pygame.draw.ellipse(screen, (10, 10, 10),
                                (int(sx - 25), int(sy + p.z / 1000.0), 50, 14))

        for eid in range(session.get_entity_count()):
            e    = session.get_entity(eid)
            ex   = int(e.x / 1000.0 - cam_x)
            ey   = int((e.y / 1000.0) - (e.z / 1000.0) + HUD_H)
            ab   = char_assets.get(e.character_type, char_assets[0]).get_ability(e.ability_state_id)
            hdef = ab.hit_box if ab else None
            if hdef is not None:
                shadow_gy = int(ey + hdef.oy + hdef.h + e.z / 1000.0)
            else:
                shadow_gy = int(e.y / 1000.0 + HUD_H)
            shadow_w = max(8, int(30 * (ab.proj_fx.scale if ab and ab.proj_fx else 1.0)))
            pygame.draw.ellipse(screen, (10, 10, 10),
                                (ex - shadow_w // 2, shadow_gy - 4, shadow_w, 8))

        # --- [Phase 2] 特效後層 ---
        fx_manager.update_and_draw(screen, layer="behind")

        # --- [Phase 2.5] 位置指示器 ---
        if _arrow_img:
            bob = int(4 * math.sin(pygame.time.get_ticks() * 0.004))
            aw, ah = _arrow_img.get_size()
            for original_idx, p in render_list:
                if original_idx != controlled_idx or p.state == STATE_DEAD:
                    continue
                sx, sy = get_screen_pos(p)
                sx -= cam_x
                screen.blit(_arrow_img,
                            (int(sx) - aw // 2,
                             int(sy + p.z / 1000.0) - _ARROW_ABOVE_SHADOW - ah + bob))

        # --- [Phase 3] 角色與實體層 ---
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
                    p.state, mm.player_elapsed_frames[original_idx], p.facing_right)
            sw, sh = sprite.get_width(), sprite.get_height()
            anchor_x_eff = asset.anchor_x if not p.facing_right else -asset.anchor_x
            blit_x = int(sx - sw // 2 - anchor_x_eff)
            blit_y = int(sy - sh // 2 - asset.anchor_y)
            screen.blit(sprite, (blit_x, blit_y))

            if p.state == STATE_WALK and p.z == 0 and mm.player_elapsed_frames[original_idx] % 12 == 0:
                heel_offset = 20 if p.facing_right else -20
                fx_path = os.path.join(PROJECT_ROOT, "src/assets/fx/13 - Copie.png")
                p_vx = -1.2 if p.facing_right else 1.2
                fx_manager.spawn(fx_path, 126, 116, sx - heel_offset, sy,
                                 speed=4, scale=0.3, vy=-0.7, vx=p_vx, layer="behind")

            if is_offline and debug_manager.enabled and original_idx == controlled_idx:
                pygame.draw.rect(screen, (255, 255, 255), (blit_x, blit_y, sw, sh), 1)

            if state_changed.get(original_idx):
                ab = asset.get_ability(p.state)
                if ab is not None and ab.projectile_vx == 0 and ab.fx is not None:
                    fxdef   = ab.fx
                    hit_def = ab.hit_box
                    if hit_def is not None:
                        fx_x, fx_y = hit_def.screen_center(sx, sy, p.facing_right)
                        fx_x, fx_y = int(fx_x), int(fx_y)
                    else:
                        fx_x = int(sx + (fxdef.offset_x if p.facing_right else -fxdef.offset_x))
                        fx_y = int(sy + fxdef.offset_y)
                    fx_manager.spawn(fxdef.path, fxdef.frame_w, fxdef.frame_h,
                                     fx_x, fx_y, speed=fxdef.speed, scale=fxdef.scale)

            if debug_manager.enabled:
                hurt_def = asset.get_hurt_box(p.state)
                if hurt_def:
                    pygame.draw.rect(screen, (0, 255, 0),
                                     hurt_def.to_screen_rect(sx, sy, p.facing_right), 1)

                def _in_hit_window(state: int, timer: int) -> bool:
                    a = asset.get_ability(state)
                    if a is None or not a.melee_enabled:
                        return False
                    spd     = asset.speed_map.get(state, 4)
                    elapsed = (a.timer - timer) // spd
                    return a.hit_frame_start <= elapsed <= a.hit_frame_end

                ab_cur   = asset.get_ability(p.state)
                melee_on = (ab_cur is not None and ab_cur.melee_enabled
                            and _in_hit_window(p.state, p.timer))
                hit_def  = asset.get_hit_box(p.state)
                if hit_def and melee_on:
                    pygame.draw.rect(screen, (255, 50, 50),
                                     hit_def.to_screen_rect(sx, sy, p.facing_right), 1)

        # [Phase 3 續] 投擲物實體
        for eid in range(session.get_entity_count()):
            e    = session.get_entity(eid)
            ex   = int(e.x / 1000.0 - cam_x)
            ey   = int((e.y / 1000.0) - (e.z / 1000.0) + HUD_H)
            ab   = char_assets.get(e.character_type, char_assets[0]).get_ability(e.ability_state_id)
            fxdef   = ab.proj_fx  if ab else None
            hit_def = ab.hit_box  if ab else None
            total   = ab.projectile_lifetime if ab else 30
            if hit_def is not None:
                fx_cx, fx_cy = hit_def.entity_screen_center(ex, ey)
            else:
                fx_cx, fx_cy = ex, ey
            if fxdef is not None:
                elapsed = max(0, total - e.lifetime)
                frames  = fx_manager._load(fxdef.path, fxdef.frame_w, fxdef.frame_h)
                idx     = (elapsed // max(1, fxdef.speed)) % len(frames)
                frame   = frames[idx]
                if e.vx < 0:
                    frame = pygame.transform.flip(frame, True, False)
                if fxdef.scale != 1.0:
                    fw = max(1, int(frame.get_width()  * fxdef.scale))
                    fh = max(1, int(frame.get_height() * fxdef.scale))
                    frame = pygame.transform.scale(frame, (fw, fh))
                screen.blit(frame, (int(fx_cx) - frame.get_width()  // 2,
                                    int(fx_cy) - frame.get_height() // 2))
            else:
                pygame.draw.circle(screen, (255, 100,  0), (int(fx_cx), int(fx_cy)), 10)
                pygame.draw.circle(screen, (255, 220, 60), (int(fx_cx), int(fx_cy)),  6)
            if debug_manager.enabled and hit_def:
                pygame.draw.rect(screen, (255, 50, 50),
                                 hit_def.to_entity_screen_rect(ex, ey), 1)

        # --- [Phase 4] 特效前層 ---
        fx_manager.update_and_draw(screen, layer="front")

        hud.draw(screen, render_list)
        debug_manager.draw(screen, session, render_list, clock.get_fps(), ai_controllers)

        # 同步等待提示
        if not is_offline and not session.is_synchronized():
            sync_wait_frames += 1
            if sync_wait_frames == 1:
                remotes = [(p["id"], p["ip"], p["port"]) for p in config.get("players", [])
                           if p["id"] != controlled_idx]
                print(f"[SYNC] start  my_id={controlled_idx}  my_port={config['local_port']}  remotes={remotes}")
            elif sync_wait_frames % (60 * 5) == 0:
                remotes = [(p["id"], p["ip"], p["port"]) for p in config.get("players", [])
                           if p["id"] != controlled_idx]
                print(f"[SYNC] waiting... {sync_wait_frames//60}s  my_port={config['local_port']}  remotes={remotes}")
            overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            screen.blit(overlay, (0, 0))
            cx, cy    = SCREEN_W // 2, SCREEN_H // 2
            text_surf = wait_font.render("WAITING FOR SYNC...", True, (255, 255, 0))
            screen.blit(text_surf, text_surf.get_rect(center=(cx, cy)))
            remotes_str = "  ".join(
                f"id={p['id']} {p['ip']}:{p['port']}"
                for p in config.get("players", []) if p["id"] != controlled_idx)
            info1 = info_font.render(
                f"My id={controlled_idx}  local_port={config['local_port']}", True, (200, 200, 200))
            info2 = info_font.render(f"Remote: {remotes_str}", True, (200, 200, 200))
            info3 = info_font.render(f"Waiting {sync_wait_frames // 60}s", True, (150, 150, 150))
            screen.blit(info1, info1.get_rect(center=(cx, cy + 50)))
            screen.blit(info2, info2.get_rect(center=(cx, cy + 75)))
            screen.blit(info3, info3.get_rect(center=(cx, cy + 100)))

        # 開場倒數
        if mm.countdown_frames > 0 and mm.match_result is None and (is_offline or session.is_synchronized()):
            ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 120))
            screen.blit(ov, (0, 0))
            cx, cy  = SCREEN_W // 2, SCREEN_H // 2
            num     = (mm.countdown_frames + 59) // 60
            cd_surf = result_font_big.render(str(num), True, (255, 220, 60))
            screen.blit(cd_surf, cd_surf.get_rect(center=(cx, cy)))
            sub     = "準備！" if num == 1 else "GET READY"
            sub_surf = result_font_small.render(sub, True, (200, 200, 200))
            screen.blit(sub_surf, sub_surf.get_rect(center=(cx, cy + 60)))

        # 結算畫面
        if mm.match_result is not None:
            ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 160))
            screen.blit(ov, (0, 0))
            cx, cy = SCREEN_W // 2, SCREEN_H // 2
            if mm.match_result == -2:
                msg, color = "DRAW!", (200, 200, 200)
            else:
                name      = player_names.get(mm.match_result, f"Player {mm.match_result + 1}")
                char_name = char_assets.get(
                    session.get_player(mm.match_result).character_type, char_assets[0]).name
                msg, color = f"{name}  ({char_name})  WINS!", (255, 220, 60)
            big_surf = result_font_big.render(msg, True, color)
            screen.blit(big_surf, big_surf.get_rect(center=(cx, cy - 20)))
            hint    = "R: 重播  ESC: Quit" if is_replay else ("R: Restart  ESC: Quit" if is_offline else "ESC: Quit")
            sm_surf = result_font_small.render(hint, True, (180, 180, 180))
            screen.blit(sm_surf, sm_surf.get_rect(center=(cx, cy + 50)))

        # 暫停畫面
        if mm.paused and is_offline:
            ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 140))
            screen.blit(ov, (0, 0))
            cx, cy     = SCREEN_W // 2, SCREEN_H // 2
            pause_surf = result_font_big.render("PAUSED", True, (255, 255, 255))
            screen.blit(pause_surf, pause_surf.get_rect(center=(cx, cy - 20)))
            hint_surf  = result_font_small.render("P: Resume  ESC: Quit", True, (180, 180, 180))
            screen.blit(hint_surf, hint_surf.get_rect(center=(cx, cy + 40)))

        # 重播覆蓋提示
        if is_replay:
            speed_str  = f"{_replay_speed:.1f}x"
            pause_str  = "  [PAUSED]" if _replay_paused else ""
            replay_txt = f"REPLAY  {speed_str}{pause_str}  |  P: 暫停  1: 0.5x  2: 1x  3: 2x"
            rt_surf    = info_font.render(replay_txt, True, (220, 220, 60))
            screen.blit(rt_surf, (SCREEN_W - rt_surf.get_width() - 10,
                                  SCREEN_H - rt_surf.get_height() - 10))

        pygame.display.flip()
        if _perf_enabled:
            _frame_times.append(time.perf_counter() - _t0)
            if len(_frame_times) >= 300:
                p99 = sorted(_frame_times)[-3]
                avg = sum(_frame_times) / len(_frame_times)
                print(f"[perf] p99={p99*1000:.1f}ms  avg={avg*1000:.1f}ms")
                _frame_times.clear()
        clock.tick(60)

    del session  # 確保 GGRS UDP socket 在 pygame.quit() 前釋放
    pygame.quit()
