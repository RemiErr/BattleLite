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

STATE_IDLE   = 0
STATE_WALK   = 1
STATE_ATTACK = 2
STATE_HURT   = 3

PLAYER_COLORS = [
    (255, 50, 50),   # P0: 紅
    (50, 255, 50),   # P1: 綠
    (50, 50, 255),   # P2: 藍
    (255, 255, 50),  # P3: 黃
]

CHAR_RECT_W = 30
CHAR_RECT_H = 50

# 物理參數 (需與 Rust 對齊)
WALK_SPEED_X = 5000
WALK_SPEED_Y = 3000
JUMP_IMPULSE = 9000

def get_input_mask():
    keys = pygame.key.get_pressed()
    mask = 0
    if keys[pygame.K_RIGHT]: mask |= INPUT_RIGHT
    if keys[pygame.K_LEFT]:  mask |= INPUT_LEFT
    if keys[pygame.K_UP]:    mask |= INPUT_UP
    if keys[pygame.K_DOWN]:  mask |= INPUT_DOWN
    if keys[pygame.K_SPACE]: mask |= INPUT_JUMP
    if keys[pygame.K_z]:     mask |= INPUT_ATTACK
    return mask

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
        print(f"✅ 系統啟動 (F2 切換模式)")
    except Exception as e:
        print(f"❌ 無法啟動: {e}")
        sys.exit(1)

    running = True
    while running:
        # A. 事件處理
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F1:
                    debug_manager.toggle()
                if event.key == pygame.K_F2:
                    offline_mode = not offline_mode
                if event.key == pygame.K_TAB and offline_mode:
                    controlled_idx = (controlled_idx + 1) % num_players

        # B. 邏輯推進
        input_mask = get_input_mask()
        
        all_players = []
        for i in range(num_players):
            all_players.append(session.get_player(i))

        if not offline_mode:
            session.advance(input_mask)
        else:
            for i, p in enumerate(all_players):
                current_input = input_mask if i == controlled_idx else 0
                
                if p.state == STATE_IDLE or p.state == STATE_WALK:
                    p.vx = 0; p.vy = 0
                    if current_input & INPUT_RIGHT: 
                        p.vx = WALK_SPEED_X; p.state = STATE_WALK; p.facing_right = True
                    if current_input & INPUT_LEFT:  
                        p.vx = -WALK_SPEED_X; p.state = STATE_WALK; p.facing_right = False
                    if current_input & INPUT_DOWN:  p.vy = WALK_SPEED_Y; p.state = STATE_WALK
                    if current_input & INPUT_UP:    p.vy = -WALK_SPEED_Y; p.state = STATE_WALK
                    
                    if p.vx == 0 and p.vy == 0: p.state = STATE_IDLE
                    if (current_input & INPUT_JUMP) and p.z == 0: p.vz = JUMP_IMPULSE
                    if current_input & INPUT_ATTACK:
                        p.state = STATE_ATTACK; p.timer = 20; p.vx = 0; p.vy = 0

                p.update()
                session.set_player(i, p)

            # 離線碰撞判定 (使用新的 check_attack_hit)
            for i in range(num_players):
                attacker = all_players[i]
                if attacker.state == STATE_ATTACK and attacker.timer == 15:
                    for j in range(num_players):
                        if i == j: continue
                        victim = all_players[j]
                        if attacker.check_attack_hit(victim):
                            victim.state = STATE_HURT; victim.timer = 30; victim.vz = 3000

        # C. 渲染
        screen.fill((30, 30, 30))
        pygame.draw.line(screen, (60, 60, 60), (0, 300), (screen_width, 300), 1)
        pygame.draw.line(screen, (60, 60, 60), (0, 450), (screen_width, 450), 1)

        for i, player in enumerate(all_players):
            shadow_x = player.x / 1000.0
            shadow_y = player.y / 1000.0 + 40
            pygame.draw.ellipse(screen, (10, 10, 10), (shadow_x, shadow_y, 50, 20))
            
            color = PLAYER_COLORS[i]
            if player.state == STATE_ATTACK: color = (255, 255, 255)
            elif player.state == STATE_HURT: color = (150, 150, 150)
            
            screen_x, screen_y = get_screen_pos(player)
            rect = pygame.Rect(screen_x, screen_y, CHAR_RECT_W + 10, CHAR_RECT_H)
            pygame.draw.rect(screen, color, rect)
            if offline_mode and i == controlled_idx:
                pygame.draw.rect(screen, (255, 255, 255), rect, 2)
            
            # 根據面向繪製攻擊框
            if player.state == STATE_ATTACK:
                atk_offset = 30 if player.facing_right else -20
                atk_rect = pygame.Rect(screen_x + atk_offset, screen_y + 10, 30, 30)
                pygame.draw.rect(screen, (255, 0, 0), atk_rect, 2)

        debug_manager.draw(screen, session, all_players, clock.get_fps())
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    run_game()
