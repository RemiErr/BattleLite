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

# --- 輸入遮罩定義 ---
INPUT_RIGHT = 1 << 0
INPUT_LEFT  = 1 << 1
INPUT_UP    = 1 << 2
INPUT_DOWN  = 1 << 3
INPUT_JUMP  = 1 << 4

def get_input_mask():
    keys = pygame.key.get_pressed()
    mask = 0
    if keys[pygame.K_RIGHT]: mask |= INPUT_RIGHT
    if keys[pygame.K_LEFT]:  mask |= INPUT_LEFT
    if keys[pygame.K_UP]:    mask |= INPUT_UP
    if keys[pygame.K_DOWN]:  mask |= INPUT_DOWN
    if keys[pygame.K_SPACE]: mask |= INPUT_JUMP
    return mask

def run_game():
    pygame.init()
    screen_width, screen_height = 800, 600
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("BattleLite - Debug Overlay Enabled")
    clock = pygame.time.Clock()
    
    # 初始化 Debug 管理器
    debug_manager = DebugManager()

    try:
        session = GGRSSession(local_player_id=0, num_players=1, port=12345)
        print("✅ GGRS Session 已啟動")
    except Exception as e:
        print(f"❌ 無法啟動 Session: {e}")
        sys.exit(1)

    running = True
    while running:
        # A. 事件處理
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            # 偵測 F1 按鍵切換 Debug Overlay
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F1:
                    debug_manager.toggle()

        # B. 邏輯推進
        input_mask = get_input_mask()
        session.advance(input_mask)

        # C. 渲染
        screen.fill((30, 30, 30))
        
        if not session.is_synchronized():
            font = pygame.font.SysFont("Arial", 24)
            text_surf = font.render("Waiting for synchronization...", True, (255, 255, 255))
            screen.blit(text_surf, (screen_width // 2 - 100, screen_height // 2))
        else:
            player0 = session.get_player(0)
            
            # 渲染影子
            shadow_x = player0.x / 1000.0
            shadow_y = player0.y / 1000.0 + 40
            pygame.draw.ellipse(screen, (10, 10, 10), (shadow_x, shadow_y, 50, 20))
            
            # 渲染玩家
            screen_x, screen_y = get_screen_pos(player0)
            pygame.draw.rect(screen, (255, 50, 50), (screen_x, screen_y, 50, 50))
            
            # 渲染 Debug Overlay
            debug_manager.draw(screen, session, [player0], clock.get_fps())

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    run_game()
