import pygame

class BaseCharacter:
    """
    角色資源基類。
    負責管理 Sprite Sheet 加載與根據狀態計算當前應顯示的幀。
    """
    def __init__(self, name):
        self.name = name
        # 動畫定義字典: { state: [frame_rects] }
        # 這裡的 frame_rects 可以是 spritesheet 上的座標 (x, y, w, h)
        self.animations = {}
        # 每個狀態的循環模式 (True: 循環播放, False: 播放一次停在最後一幀)
        self.loop_map = {}

    def get_frame_index(self, state, elapsed_frames):
        """
        根據狀態與該狀態已過幀數，計算目前應顯示第幾張圖。
        """
        if state not in self.animations:
            return 0
        
        frames = self.animations[state]
        num_frames = len(frames)
        
        if num_frames == 0:
            return 0
            
        if self.loop_map.get(state, True):
            # 循環播放
            return elapsed_frames % num_frames
        else:
            # 播放一次，停在最後
            return min(elapsed_frames, num_frames - 1)

    def get_sprite_rect(self, state, elapsed_frames):
        """
        回傳當前應繪製的 Sprite 在 Sheet 上的區域。
        """
        idx = self.get_frame_index(state, elapsed_frames)
        if state in self.animations and idx < len(self.animations[state]):
            return self.animations[state][idx]
        return None
