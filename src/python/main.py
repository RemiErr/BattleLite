import pygame
import sys
import os

# 確保路徑正確以匯入 renderer 與 debug_manager
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    from battlelite_core import GGRSSession, Player
    from src.python.renderer import get_screen_pos
    from src.python.debug_manager import DebugManager
except ImportError as e:
    print(f"❌ 匯入失敗: {e}")
    sys.exit(1)

# --- 1. 定義常數 ---
INPUT_RIGHT  = 1 << 0
INPUT_LEFT   = 1 << 1
INPUT_UP     = 1 << 2
INPUT_DOWN   = 1 << 3
INPUT_JUMP   = 1 << 4
INPUT_ATTACK = 1 << 5
INPUT_SKILL  = 1 << 6

STATE_IDLE   = 0
STATE_WALK   = 1
STATE_ATTACK = 2
STATE_HURT   = 3
STATE_SKILL  = 4

SKILL_COST   = 20000 

PLAYER_COLORS = [
    (255, 50, 50),   # P0: 紅
    (50, 255, 50),   # P1: 綠
    (50, 50, 255),   # P2: 藍
    (255, 255, 50),  # P3: 黃
]

CHAR_RECT_W = 30
CHAR_RECT_H = 50

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
    hp_w = max(0, min(40, (hp / 100000.0) * 40))
    pygame.draw.rect(screen, (0, 255, 0), (x, y - 15, hp_w, 5))
    
    pygame.draw.rect(screen, (0, 0, 100), (x, y - 8, 40, 5))
    mp_w = max(0, min(40, (mp / 50000.0) * 40))
    pygame.draw.rect(screen, (0, 200, 255), (x, y - 8, mp_w, 5))

def run_game():
    pygame.init()
    screen_width, screen_height = 800, 600
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("BattleLite - Refined Combat (F2: Dev Mode)")
    clock = pygame.time.Clock()
    debug_manager = DebugManager()

    offline_mode = True 
    controlled_idx = 0
    num_players = 4

    try:
        session = GGRSSession(local_player_id=0, num_players=num_players, port=12345)
    except Exception as e:
        print(f"❌ 無法啟動: {e}"); sys.exit(1)

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
            # 離線模式：手動驅動與同步
            for i in range(num_players):
                p = session.get_player(i)
                current_input = input_mask if i == controlled_idx else 0
                
                if p.state in [STATE_IDLE, STATE_WALK]:
                    p.vx = 0; p.vy = 0
                    if current_input & INPUT_RIGHT: p.vx = 5000; p.state = STATE_WALK; p.facing_right = True
                    if current_input & INPUT_LEFT:  p.vx = -5000; p.state = STATE_WALK; p.facing_right = False
                    if current_input & INPUT_DOWN:  p.vy = 3000; p.state = STATE_WALK
                    if current_input & INPUT_UP:    p.vy = -3000; p.state = STATE_WALK
                    if p.vx == 0 and p.vy == 0: p.state = STATE_IDLE
                    if (current_input & INPUT_JUMP) and p.z == 0: p.vz = 9000
                    if current_input & INPUT_ATTACK:
                        p.state = STATE_ATTACK; p.timer = 20; p.vx = 0; p.vy = 0
                    if (current_input & INPUT_SKILL) and p.mp >= SKILL_COST:
                        p.state = STATE_SKILL; p.timer = 40; p.mp -= SKILL_COST; p.vx = 0; p.vy = 0

                p.update()
                session.set_player(i, p)

            # 離線碰撞判定 (確保結果寫回 Rust)
            for i in range(num_players):
                atk = session.get_player(i)
                if (atk.state == STATE_ATTACK and atk.timer == 15) or (atk.state == STATE_SKILL and atk.timer > 10):
                    for j in range(num_players):
                        if i == j: continue
                        vic = session.get_player(j)
                        if atk.check_attack_hit(vic):
                            vic.state = STATE_HURT; vic.timer = 30; vic.vz = 4000; vic.hp -= 10000
                            session.set_player(j, vic) # 重要：受傷後存回 Rust

        # C. 渲染
        screen.fill((30, 30, 30))
        pygame.draw.line(screen, (60, 60, 60), (0, 300), (screen_width, 300), 1)
        pygame.draw.line(screen, (60, 60, 60), (0, 450), (screen_width, 450), 1)

        # 讀取並進行 Y 軸排序 (Z-ordering)
        render_list = []
        for i in range(num_players):
            render_list.append((i, session.get_player(i)))
        
        # 根據 Y 座標排序，Y 越大的越晚畫 (顯示在越前面)
        render_list.sort(key=lambda item: item[1].y)

        for original_idx, player in render_list:
            shadow_x = player.x / 1000.0
            shadow_y = player.y / 1000.0 + 40
            pygame.draw.ellipse(screen, (10, 10, 10), (shadow_x, shadow_y, 50, 20))
            
            color = PLAYER_COLORS[original_idx]
            if player.state == STATE_ATTACK: color = (255, 255, 255)
            elif player.state == STATE_HURT: color = (150, 150, 150)
            elif player.state == STATE_SKILL: color = (0, 255, 255)
            
            screen_x, screen_y = get_screen_pos(player)
            rect = pygame.Rect(screen_x, screen_y, CHAR_RECT_W + 10, CHAR_RECT_H)
            pygame.draw.rect(screen, color, rect)
            if offline_mode and original_idx == controlled_idx:
                pygame.draw.rect(screen, (255, 255, 255), rect, 2)
            
            draw_status_bar(screen, screen_x, screen_y, player.hp, player.mp)
            
            # 渲染判定框 (修正視覺偏移以符合 Rust 新邏輯)
            if player.state == STATE_ATTACK:
                off = 30 if player.facing_right else -20
                pygame.draw.rect(screen, (255, 0, 0), (screen_x + off, screen_y + 10, 30, 30), 2)
            elif player.state == STATE_SKILL:
                off = 45 if player.facing_right else -35
                pygame.draw.rect(screen, (0, 255, 255), (screen_x + (30 if player.facing_right else -40), screen_y - 10, 50, 70), 2)

        debug_manager.draw(screen, session, [p for _, p in render_list], clock.get_fps())
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    run_game()
