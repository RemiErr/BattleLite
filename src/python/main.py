import pygame
import sys
import os

# 確保路徑正確以匯入 renderer
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    from battlelite_core import GGRSSession, Player
    from src.python.renderer import get_screen_pos
except ImportError as e:
    print(f"❌ 匯入失敗: {e}")
    print("請確保已執行 'maturin develop' 且啟動了虛擬環境。")
    sys.exit(1)

# --- 1. 定義輸入遮罩 (與 Rust 對齊) ---
INPUT_RIGHT = 1 << 0
INPUT_LEFT  = 1 << 1
INPUT_UP    = 1 << 2
INPUT_DOWN  = 1 << 3
INPUT_JUMP  = 1 << 4

def get_input_mask():
    """將 Pygame 鍵盤狀態轉換為 8-bit Input Mask"""
    keys = pygame.key.get_pressed()
    mask = 0
    if keys[pygame.K_RIGHT]: mask |= INPUT_RIGHT
    if keys[pygame.K_LEFT]:  mask |= INPUT_LEFT
    if keys[pygame.K_UP]:    mask |= INPUT_UP
    if keys[pygame.K_DOWN]:  mask |= INPUT_DOWN
    if keys[pygame.K_SPACE]: mask |= INPUT_JUMP
    return mask

def run_game():
    # 1. 初始化 Pygame
    pygame.init()
    screen_width, screen_height = 800, 600
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("BattleLite - Integrated Physics Prototype")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 24)

    # 2. 初始化 GGRS Session (本地 1 人模式以便測試)
    # 使用 1 人模式時，GGRS 通常會立即進入 Running 狀態
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

        # B. 獲取輸入並推進 GGRS (Rust 物理核心在此運行)
        input_mask = get_input_mask()
        session.advance(input_mask)

        # C. 渲染 (Rendering)
        screen.fill((30, 30, 30)) # 背景色
        
        if not session.is_synchronized():
            # 顯示等待同步文字
            text_surf = font.render("Waiting for synchronization...", True, (255, 255, 255))
            screen.blit(text_surf, (screen_width // 2 - 100, screen_height // 2))
        else:
            # 取得玩家 0 的物理狀態 (由 Rust 計算)
            player = session.get_player(0)
            
            # 繪製影子 (顯示 Y 軸深度)
            # 影子座標只受 X, Y 影響
            shadow_x = player.x / 1000.0
            shadow_y = player.y / 1000.0 + 40
            pygame.draw.ellipse(screen, (10, 10, 10), (shadow_x, shadow_y, 50, 20))
            
            # 繪製玩家方塊 (由 renderer 處理 2.5D 座標轉換)
            screen_x, screen_y = get_screen_pos(player)
            pygame.draw.rect(screen, (255, 50, 50), (screen_x, screen_y, 50, 50))
            
            # 顯示座標資訊
            debug_info = f"Pos: ({player.x//1000}, {player.y//1000}, {player.z//1000}) | Vel: {player.vz}"
            debug_surf = font.render(debug_info, True, (200, 200, 200))
            screen.blit(debug_surf, (10, 10))

        pygame.display.flip()
        clock.tick(60) # 限制 60 FPS (與 GGRS 設定對齊)

    pygame.quit()

if __name__ == "__main__":
    run_game()
