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

# 玩家顏色清單
PLAYER_COLORS = [
    (255, 50, 50),   # P0: 紅
    (50, 255, 50),   # P1: 綠
    (50, 50, 255),   # P2: 藍
    (255, 255, 50),  # P3: 黃
]

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
    pygame.display.set_caption("BattleLite - 4 Player Support Enabled")
    clock = pygame.time.Clock()
    
    debug_manager = DebugManager()

    # 初始化 4 人 Session (本地測試)
    num_players = 4
    try:
        session = GGRSSession(local_player_id=0, num_players=num_players, port=12345)
        print(f"✅ {num_players} 人 GGRS Session 已啟動")
    except Exception as e:
        print(f"❌ 無法啟動 Session: {e}")
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

        # B. 邏輯推進
        # 在目前的單機測試中，我們只傳送本地玩家 (P0) 的輸入
        # 其他玩家因為沒收到遠端輸入，會處於「等待」或「預測」狀態
        input_mask = get_input_mask()
        session.advance(input_mask)

        # C. 渲染
        screen.fill((30, 30, 30))
        
        # 即使未同步也可以獲取初始資料進行渲染
        all_players = []
        for i in range(num_players):
            try:
                p = session.get_player(i)
                all_players.append(p)
            except:
                break

        if not session.is_synchronized():
            font = pygame.font.SysFont("Arial", 24)
            text_surf = font.render(f"Waiting for synchronization (4 players)...", True, (255, 255, 255))
            screen.blit(text_surf, (screen_width // 2 - 150, screen_height // 2))
        
        # 繪製所有玩家與影子
        for i, player in enumerate(all_players):
            # 渲染影子
            shadow_x = player.x / 1000.0
            shadow_y = player.y / 1000.0 + 40
            pygame.draw.ellipse(screen, (10, 10, 10), (shadow_x, shadow_y, 50, 20))
            
            # 渲染玩家
            screen_x, screen_y = get_screen_pos(player)
            pygame.draw.rect(screen, PLAYER_COLORS[i], (screen_x, screen_y, 50, 50))
            
        # 渲染 Debug Overlay
        debug_manager.draw(screen, session, all_players, clock.get_fps())

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    run_game()
