import pygame


class BaseCharacter:
    """
    角色資源基類。
    負責從 Sprite Sheet 切幀並依狀態管理動畫播放。
    """

    def __init__(self, name: str):
        self.name = name
        # { state: [pygame.Surface, ...] }
        self.animations: dict[int, list[pygame.Surface]] = {}
        # { state: bool }  True=循環, False=播放一次停在最後
        self.loop_map: dict[int, bool] = {}
        # { state: int }  每幀動畫持續幾個遊戲幀
        self.speed_map: dict[int, int] = {}

    def load_sheet(self, path: str, frame_w: int, frame_h: int,
                   state_rows: list[tuple]) -> None:
        """
        載入 Sprite Sheet 並切幀存入 self.animations。

        state_rows 格式：[(state, row, num_frames, loop, speed), ...]
            state      : Rust 狀態碼
            row        : Sheet 列索引（0-based）
            num_frames : 該動畫的幀數
            loop       : True=循環, False=播放一次
            speed      : 每張動畫圖維持幾個遊戲幀
        """
        sheet = pygame.image.load(path).convert_alpha()
        for state, row, num_frames, loop, speed in state_rows:
            frames: list[pygame.Surface] = []
            for col in range(num_frames):
                src_rect = pygame.Rect(col * frame_w, row * frame_h, frame_w, frame_h)
                frame = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
                frame.blit(sheet, (0, 0), src_rect)
                frames.append(frame)
            self.animations[state] = frames
            self.loop_map[state]   = loop
            self.speed_map[state]  = speed

    def get_frame_index(self, state: int, elapsed_frames: int) -> int:
        if state not in self.animations:
            return 0
        num_frames = len(self.animations[state])
        if num_frames == 0:
            return 0
        speed = self.speed_map.get(state, 6)
        if self.loop_map.get(state, True):
            return (elapsed_frames // speed) % num_frames
        else:
            return min(elapsed_frames // speed, num_frames - 1)

    def get_sprite_rect(self, state: int, elapsed_frames: int):
        idx = self.get_frame_index(state, elapsed_frames)
        frames = self.animations.get(state)
        if frames and idx < len(frames):
            return frames[idx]
        return None
