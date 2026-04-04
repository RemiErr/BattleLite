import pygame
import sys
import os

# 確保路徑正確以匯入 renderer
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    from battlelite_core import Player
    from src.python.renderer import get_screen_pos
except ImportError as e:
    print(f"❌ 匯入失敗: {e}")
    print("請確保已執行 'maturin develop' 且啟動了虛擬環境。")
    sys.exit(1)

def run_game():
    # 1. 初始化 Pygame
    pygame.init()
    screen_width, screen_height = 800, 600
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("BattleLite - MVP Prototype")
    clock = pygame.time.Clock()

    # 2. 建立 Rust 物理實體
    player = Player()
    # 初始位置設在畫面中心 (定點數 1000 = 1 像素)
    player.x = (screen_width // 2) * 1000
    player.y = (screen_height // 2) * 1000
    player.z = 0
    
    # 移動速度 (每幀移動的物理單位)
    speed = 5000 

    running = True
    while running:
        # A. 事件處理 (Input Handling)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # B. 讀取按鍵並直接更新 Rust 座標 (暫時性邏輯，尚未整合 GGRS)
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            player.x -= speed
        if keys[pygame.K_RIGHT]:
            player.x += speed
        if keys[pygame.K_UP]:
            player.y -= speed
        if keys[pygame.K_DOWN]:
            player.y += speed
        # 簡單的跳躍測試 (Z 軸)
        if keys[pygame.K_SPACE]:
            player.z += speed
        elif player.z > 0:
            player.z -= speed # 簡單的回落

        # C. 渲染 (Rendering)
        screen.fill((30, 30, 30)) # 背景色
        
        # 取得螢幕位置
        screen_x, screen_y = get_screen_pos(player)
        
        # 繪製影子 (顯示 Y 軸深度)
        pygame.draw.ellipse(screen, (10, 10, 10), (screen_x, (player.y / 1000.0) + 40, 50, 20))
        
        # 繪製玩家方塊 (紅色)
        # 50x50 的方塊
        pygame.draw.rect(screen, (255, 50, 50), (screen_x, screen_y, 50, 50))

        pygame.display.flip()
        clock.tick(60) # 限制 60 FPS

    pygame.quit()

if __name__ == "__main__":
    run_game()
