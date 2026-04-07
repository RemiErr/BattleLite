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
    from battlelite_core import GGRSSession, Player
    from src.python.renderer import get_screen_pos
    from src.python.debug_manager import DebugManager
    from src.python.assets_manager.characters.knight import Knight
    from src.python.crypto_utils import SHARED_SECRET
except ImportError as e:
    print(f"❌ 匯入失敗: {e}")
    sys.exit(1)

# --- 常數對齊 ---
INPUT_RIGHT, INPUT_LEFT, INPUT_UP, INPUT_DOWN, INPUT_JUMP, INPUT_ATTACK, INPUT_SKILL = [1<<i for i in range(7)]
STATE_IDLE, STATE_WALK, STATE_ATTACK, STATE_HURT, STATE_SKILL = range(5)

def parse_args():
    """解析命令行參數，支援加密的 Payload。"""
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
    pygame.draw.rect(screen, (100, 0, 0), (x, y - 15, 40, 5))
    pygame.draw.rect(screen, (0, 255, 0), (x, y - 15, max(0, (hp/100000.0)*40), 5))
    pygame.draw.rect(screen, (0, 0, 100), (x, y - 8, 40, 5))
    pygame.draw.rect(screen, (0, 200, 255), (x, y - 8, max(0, (mp/50000.0)*40), 5))

def run_game():
    args = parse_args()
    
    # 預設設定
    config = {
        "nickname": "Player",
        "is_offline": True,
        "local_id": 0,
        "num_players": 4
    }

    # 如果有加密 Payload，由 Rust 進行解密
    if args.payload:
        try:
            print("🔐 Decrypting launcher payload via Rust core...")
            decrypted_str = battlelite_core.decrypt_payload(args.payload, SHARED_SECRET)
            config.update(json.loads(decrypted_str))
            print(f"✅ Hello, {config['nickname']}! Session initialized.")
        except Exception as e:
            print(f"❌ Decryption failed: {e}")
            sys.exit(1)

    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption(f"BattleLite - {config['nickname']}")
    clock = pygame.time.Clock()
    debug_manager = DebugManager()
    knight_asset = Knight()

    offline_mode = config["is_offline"]
    num_players = config["num_players"]
    controlled_idx = config["local_id"]
    
    session = GGRSSession(local_player_id=controlled_idx, num_players=num_players, port=12345 + controlled_idx)

    player_elapsed_frames = [0] * num_players
    last_states = [STATE_IDLE] * num_players

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F1: debug_manager.toggle()
                if event.key == pygame.K_F2: offline_mode = not offline_mode
                if event.key == pygame.K_TAB and offline_mode:
                    controlled_idx = (controlled_idx + 1) % num_players

        input_mask = get_input_mask()
        
        if not offline_mode:
            session.advance(input_mask)
        else:
            inputs = [0] * num_players
            inputs[controlled_idx] = input_mask
            session.advance_local(inputs)

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
            pygame.draw.ellipse(screen, (10, 10, 10), (p.x/1000.0, p.y/1000.0 + 40, 50, 20))
            sprite = knight_asset.get_sprite(p.state, player_elapsed_frames[original_idx], p.facing_right)
            screen.blit(sprite, (sx, sy))
            if offline_mode and original_idx == controlled_idx:
                pygame.draw.rect(screen, (255, 255, 255), (sx, sy, 40, 50), 1)
            draw_status_bar(screen, sx, sy, p.hp, p.mp)
            if p.state == STATE_ATTACK:
                off = 30 if p.facing_right else -20
                pygame.draw.rect(screen, (255, 0, 0), (sx + off, sy + 10, 30, 30), 1)
            elif p.state == STATE_SKILL:
                off = 35 if p.facing_right else -45
                pygame.draw.rect(screen, (0, 255, 255), (sx + (30 if p.facing_right else -40), sy - 10, 50, 70), 1)

        debug_manager.draw(screen, session, [p for _, p in render_list], clock.get_fps())

        # --- 醒目的同步等待提示 (獨立於 Debug UI) ---
        if not offline_mode and not session.is_synchronized():
            overlay = pygame.Surface((800, 600), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            screen.blit(overlay, (0, 0))
            
            wait_font = pygame.font.SysFont("Arial", 36, bold=True)
            msg = "WAITING FOR OTHER PLAYERS..."
            text_surf = wait_font.render(msg, True, (255, 255, 0))
            text_rect = text_surf.get_rect(center=(400, 300))
            screen.blit(text_surf, text_rect)

        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    run_game()
