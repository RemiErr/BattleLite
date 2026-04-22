import pygame
import sys
import os
import argparse
import json

# 確保路徑正確
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    import battlelite_core
    from battlelite_core import Player, OfflineSession, GGRSSession
    from src.python.renderer import get_screen_pos
    from src.python.debug_manager import DebugManager
    from src.python.assets_manager.characters.knight import Knight
    from src.python.crypto_utils import SHARED_SECRET
except ImportError as e:
    print(f"❌ 匯入失敗: {e}")
    sys.exit(1)

# --- 常數對齊 (必須與 Rust 對齊) ---
INPUT_RIGHT, INPUT_LEFT, INPUT_UP, INPUT_DOWN, INPUT_JUMP, INPUT_ATTACK, INPUT_SKILL = [1<<i for i in range(7)]
STATE_IDLE, STATE_WALK, STATE_ATTACK, STATE_HURT, STATE_SKILL = range(5)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", help="Encrypted session data from Launcher")
    return parser.parse_args()

def get_input_mask():
    keys = pygame.key.get_pressed()
    mask = 0
    if keys[pygame.K_RIGHT]: mask |= INPUT_RIGHT
    if keys[pygame.K_LEFT]:  mask |= INPUT_LEFT
    if keys[pygame.K_UP]:    mask |= INPUT_UP
    if keys[pygame.K_DOWN]:  mask |= INPUT_DOWN
    if keys[pygame.K_SPACE]: mask |= INPUT_JUMP
    if keys[pygame.K_z]:     mask |= INPUT_ATTACK
    if keys[pygame.K_x]:     mask |= INPUT_SKILL
    return mask

def draw_status_bar(screen, x, y, hp, mp):
    # HP Bar
    pygame.draw.rect(screen, (100, 0, 0), (x, y - 15, 40, 5))
    pygame.draw.rect(screen, (0, 255, 0), (x, y - 15, max(0, (hp/100000.0)*40), 5))
    # MP Bar
    pygame.draw.rect(screen, (0, 0, 100), (x, y - 8, 40, 5))
    pygame.draw.rect(screen, (0, 200, 255), (x, y - 8, max(0, (mp/50000.0)*40), 5))

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
            decrypted_str = battlelite_core.decrypt_payload(args.payload, SHARED_SECRET)
            config.update(json.loads(decrypted_str))
            print(f"✅ Session Handoff Success: Hello {config['nickname']}")
        except Exception as e:
            print(f"❌ Handshake Decryption Failed: {e}"); sys.exit(1)

    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption(f"BattleLite - {config['nickname']}")
    clock = pygame.time.Clock()
    debug_manager = DebugManager()
    knight_asset = Knight()

    # --- Session 工廠：組合模式的核心實作 ---
    is_offline = config["is_offline"]
    num_players = config["num_players"]
    controlled_idx = config["local_id"]

    if is_offline:
        print("🕹 Mode: Offline Sandbox (Pure Rust Simulation)")
        session = OfflineSession(num_players)
    else:
        print("🌐 Mode: Online P2P (GGRS Rollback)")
        print(f"  local_id={controlled_idx}  local_port={config['local_port']}")
        remote_players_list = []
        if "players" in config:
            for p in config["players"]:
                remote_players_list.append((p["id"], p["ip"], p["port"]))
                tag = "← me" if p["id"] == controlled_idx else "→ remote"
                print(f"  player id={p['id']}  {p['ip']}:{p['port']}  {tag}")
        session = GGRSSession(controlled_idx, num_players, config["local_port"], remote_players_list)

    player_elapsed_frames = [0] * num_players
    last_states = [STATE_IDLE] * num_players
    sync_wait_frames = 0

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F1: debug_manager.toggle()

        # 1. 邏輯推進 (不論模式，介面完全對等)
        input_mask = get_input_mask()
        
        if is_offline:
            # 離線模式傳入所有玩家的輸入陣列
            inputs = [0] * num_players
            inputs[controlled_idx] = input_mask
            session.advance(inputs)
        else:
            # 線上模式由 GGRS 處理
            session.advance(input_mask)

        # 2. 渲染處理 (根據 Y 軸排序)
        screen.fill((30, 30, 30))
        pygame.draw.line(screen, (60, 60, 60), (0, 300), (800, 300), 1)
        pygame.draw.line(screen, (60, 60, 60), (0, 450), (800, 450), 1)

        render_list = []
        for i in range(num_players):
            p = session.get_player(i)
            if p.state != last_states[i]:
                player_elapsed_frames[i] = 0
                last_states[i] = p.state
            else:
                player_elapsed_frames[i] += 1
            render_list.append((i, p))
        
        render_list.sort(key=lambda item: item[1].y)

        for original_idx, p in render_list:
            sx, sy = get_screen_pos(p)
            sprite = knight_asset.get_sprite(p.state, player_elapsed_frames[original_idx], p.facing_right)
            sw, sh = sprite.get_width(), sprite.get_height()
            # 以圖像中心對齊角色物理位置
            blit_x = int(sx - sw // 2)
            blit_y = int(sy - sh // 2)
            # 陰影跟隨圖像底部中心
            shadow_x = int(sx - 25)
            shadow_y = int(sy + sh // 2 - 8)
            pygame.draw.ellipse(screen, (10, 10, 10), (shadow_x, shadow_y, 50, 14))
            screen.blit(sprite, (blit_x, blit_y))

            # 如果是離線模式，高亮當前操作的角色
            if is_offline and original_idx == controlled_idx:
                pygame.draw.rect(screen, (255, 255, 255), (blit_x, blit_y, sw, sh), 1)

            draw_status_bar(screen, blit_x, blit_y, p.hp, p.mp)

            # 判定框視覺輔助 (僅用於開發者 Debug)
            if p.state == STATE_ATTACK:
                off = sw // 2 if p.facing_right else -(sw // 2 + 30)
                pygame.draw.rect(screen, (255, 0, 0), (int(sx) + off, blit_y + sh // 3, 30, 30), 1)
            elif p.state == STATE_SKILL:
                off = sw // 2 if p.facing_right else -(sw // 2 + 50)
                pygame.draw.rect(screen, (0, 255, 255), (int(sx) + off, blit_y + sh // 4, 50, 70), 1)

        debug_manager.draw(screen, session, [p for _, p in render_list], clock.get_fps())

        # 同步等待提示
        if not is_offline and not session.is_synchronized():
            sync_wait_frames += 1
            if sync_wait_frames % (60 * 5) == 0:  # 每 5 秒印一次
                remotes = [(p["id"], p["ip"], p["port"]) for p in config.get("players", []) if p["id"] != controlled_idx]
                print(f"[SYNC] waiting... {sync_wait_frames//60}s  my_port={config['local_port']}  remotes={remotes}")

            overlay = pygame.Surface((800, 600), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            screen.blit(overlay, (0, 0))
            wait_font = pygame.font.SysFont("Arial", 36, bold=True)
            text_surf = wait_font.render("WAITING FOR SYNC...", True, (255, 255, 0))
            screen.blit(text_surf, text_surf.get_rect(center=(400, 300)))

            info_font = pygame.font.SysFont("Arial", 16)
            remotes_str = "  ".join(f"id={p['id']} {p['ip']}:{p['port']}" for p in config.get("players", []) if p["id"] != controlled_idx)
            info1 = info_font.render(f"My id={controlled_idx}  local_port={config['local_port']}", True, (200, 200, 200))
            info2 = info_font.render(f"Remote: {remotes_str}", True, (200, 200, 200))
            info3 = info_font.render(f"Waiting {sync_wait_frames // 60}s", True, (150, 150, 150))
            screen.blit(info1, info1.get_rect(center=(400, 350)))
            screen.blit(info2, info2.get_rect(center=(400, 375)))
            screen.blit(info3, info3.get_rect(center=(400, 400)))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    run_game()
