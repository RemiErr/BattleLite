import pygame
import sys
import os

# 確保路徑正確
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from battlelite_core import GGRSSession, Player
    from src.python.renderer import get_screen_pos
    from src.python.debug_manager import DebugManager
    from src.python.assets_manager.characters.knight import Knight
except ImportError as e:
    print(f"❌ 匯入失敗: {e}")
    sys.exit(1)

# --- 常數對齊 ---
INPUT_RIGHT, INPUT_LEFT, INPUT_UP, INPUT_DOWN, INPUT_JUMP, INPUT_ATTACK, INPUT_SKILL = [1<<i for i in range(7)]
STATE_IDLE, STATE_WALK, STATE_ATTACK, STATE_HURT, STATE_SKILL = range(5)
SKILL_COST = 20000

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
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("BattleLite - OOP Animation System")
    clock = pygame.time.Clock()
    debug_manager = DebugManager()
    
    # 建立角色資源管理器 (目前全體共用 Knight 資源)
    knight_asset = Knight()

    offline_mode, controlled_idx, num_players = True, 0, 4
    session = GGRSSession(local_player_id=0, num_players=num_players, port=12345)

    # 記錄每個玩家在當前狀態已持續的幀數 (用於驅動動畫)
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
        
        # 1. 邏輯推進
        if not offline_mode:
            session.advance(input_mask)
        else:
            for i in range(num_players):
                p = session.get_player(i)
                inp = input_mask if i == controlled_idx else 0
                
                # 簡單模擬 Rust 邏輯 (此部分應最終完全移入 Rust)
                if p.state in [STATE_IDLE, STATE_WALK]:
                    p.vx = 0; p.vy = 0
                    if inp & INPUT_RIGHT: p.vx, p.state, p.facing_right = 5000, STATE_WALK, True
                    if inp & INPUT_LEFT:  p.vx, p.state, p.facing_right = -5000, STATE_WALK, False
                    if inp & INPUT_UP:    p.vy, p.state = -3000, STATE_WALK
                    if inp & INPUT_DOWN:  p.vy, p.state = 3000, STATE_WALK
                    if p.vx == 0 and p.vy == 0: p.state = STATE_IDLE
                    if (inp & INPUT_JUMP) and p.z == 0: p.vz = 9000
                    if inp & INPUT_ATTACK: p.state, p.timer, p.vx, p.vy = STATE_ATTACK, 20, 0, 0
                    if (inp & INPUT_SKILL) and p.mp >= 20000: p.state, p.timer, p.mp, p.vx, p.vy = STATE_SKILL, 40, p.mp-20000, 0, 0
                
                p.update()
                session.set_player(i, p)

            # 離線碰撞
            for i in range(num_players):
                atk = session.get_player(i)
                if (atk.state == STATE_ATTACK and atk.timer == 15) or (atk.state == STATE_SKILL and atk.timer > 10):
                    for j in range(num_players):
                        if i == j: continue
                        vic = session.get_player(j)
                        if atk.check_attack_hit(vic):
                            vic.state, vic.timer, vic.vz, vic.hp = STATE_HURT, 30, 4000, vic.hp-10000
                            session.set_player(j, vic)

        # 2. 準備渲染列表並更新動畫計時器
        render_list = []
        for i in range(num_players):
            p = session.get_player(i)
            # 如果狀態改變，重置計時器
            if p.state != last_states[i]:
                player_elapsed_frames[i] = 0
                last_states[i] = p.state
            else:
                player_elapsed_frames[i] += 1
            render_list.append((i, p))
        
        render_list.sort(key=lambda item: item[1].y)

        # 3. 繪圖
        screen.fill((30, 30, 30))
        for original_idx, p in render_list:
            sx, sy = get_screen_pos(p)
            # 渲染影子
            pygame.draw.ellipse(screen, (10, 10, 10), (p.x/1000.0, p.y/1000.0 + 40, 50, 20))
            
            # 獲取動畫 Sprite
            sprite = knight_asset.get_sprite(p.state, player_elapsed_frames[original_idx], p.facing_right)
            screen.blit(sprite, (sx, sy))
            
            # 高亮與狀態條
            if offline_mode and original_idx == controlled_idx:
                pygame.draw.rect(screen, (255, 255, 255), (sx, sy, 40, 50), 1)
            draw_status_bar(screen, sx, sy, p.hp, p.mp)
            
            # 判定框 Debug
            if p.state == STATE_ATTACK:
                off = 30 if p.facing_right else -20
                pygame.draw.rect(screen, (255, 0, 0), (sx + off, sy + 10, 30, 30), 1)
            elif p.state == STATE_SKILL:
                off = 35 if p.facing_right else -45
                pygame.draw.rect(screen, (0, 255, 255), (sx + (30 if p.facing_right else -40), sy - 10, 50, 70), 1)

        debug_manager.draw(screen, session, [p for _, p in render_list], clock.get_fps())
        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    run_game()
