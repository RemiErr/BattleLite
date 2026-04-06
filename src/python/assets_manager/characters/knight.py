import pygame
from src.python.assets_manager.base_character import BaseCharacter

class Knight(BaseCharacter):
    """
    騎士角色類別。
    定義了騎士的各項動畫幀數與視覺表現。
    """
    def __init__(self):
        super().__init__("Knight")
        
        # 1. 定義動畫幀數 (狀態碼需與 Rust 對齊)
        # 格式: { state: [Surface] }
        self.animation_surfaces = {}
        
        # 模擬動畫定義 (狀態碼: 0=IDLE, 1=WALK, 2=ATTACK, 3=HURT, 4=SKILL)
        # 在這裡我們用不同的顏色明度來模擬動畫
        self._create_placeholder_animation(0, 4, (255, 50, 50))   # IDLE: 4幀
        self._create_placeholder_animation(1, 6, (200, 50, 50))   # WALK: 6幀
        self._create_placeholder_animation(2, 5, (255, 255, 255)) # ATTACK: 5幀
        self._create_placeholder_animation(3, 2, (100, 100, 100)) # HURT: 2幀
        self._create_placeholder_animation(4, 8, (0, 255, 255))   # SKILL: 8幀

        # 2. 定義循環模式
        self.loop_map = {
            0: True,  # IDLE 循環
            1: True,  # WALK 循環
            2: False, # ATTACK 播放一次
            3: False, # HURT 播放一次
            4: False  # SKILL 播放一次
        }

    def _create_placeholder_animation(self, state, num_frames, base_color):
        """
        建立占位用的色塊動畫。
        """
        frames = []
        for i in range(num_frames):
            # 透過改變顏色亮度來模擬動畫感
            brightness = 1.0 - (i * 0.1)
            color = tuple(max(0, min(255, int(c * brightness))) for c in base_color)
            
            surf = pygame.Surface((40, 50))
            surf.fill(color)
            # 在方塊上畫一個簡單的臉來區分面向
            pygame.draw.rect(surf, (0, 0, 0), (25, 10, 5, 5)) 
            frames.append(surf)
        
        self.animation_surfaces[state] = frames

    def get_sprite(self, state, elapsed_frames, facing_right=True):
        """
        獲取當前應顯示的 Sprite Surface。
        """
        # 1. 根據狀態與經過幀數計算索引
        frames = self.animation_surfaces.get(state, self.animation_surfaces[0])
        idx = self.get_frame_index(state, elapsed_frames)
        
        # 2. 取得對應的 Surface (安全檢查)
        if idx >= len(frames):
            idx = 0
        sprite = frames[idx]
        
        # 3. 處理左右鏡像翻轉
        if not facing_right:
            return pygame.transform.flip(sprite, True, False)
        return sprite

    def get_frame_index(self, state, elapsed_frames):
        """
        覆寫基類邏輯：處理動畫播放一次的情況。
        """
        frames = self.animation_surfaces.get(state, self.animation_surfaces[0])
        num_frames = len(frames)
        
        if self.loop_map.get(state, True):
            # 每一幀動畫持續 6 幀遊戲時間 (讓動畫慢一點)
            return (elapsed_frames // 6) % num_frames
        else:
            # 攻擊等狀態通常動畫速度較快 (每 4 幀切換一次)
            return min(elapsed_frames // 4, num_frames - 1)
