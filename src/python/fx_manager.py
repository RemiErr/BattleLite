import pygame


class FxEffect:
    def __init__(self, frames: list[pygame.Surface], x: int, y: int, speed: int = 3,
                 flip_x: bool = False):
        self.frames = frames
        self.x = x
        self.y = y
        self.speed = speed
        self.flip_x = flip_x
        self.elapsed = 0
        self.done = False

    def update(self) -> None:
        self.elapsed += 1
        if self.elapsed >= len(self.frames) * self.speed:
            self.done = True

    def draw(self, screen: pygame.Surface) -> None:
        if self.done:
            return
        idx = min(self.elapsed // self.speed, len(self.frames) - 1)
        frame = self.frames[idx]
        if self.flip_x:
            frame = pygame.transform.flip(frame, True, False)
        blit_x = self.x - frame.get_width() // 2
        blit_y = self.y - frame.get_height() // 2
        screen.blit(frame, (blit_x, blit_y))


class FxManager:
    """
    通用 2D 特效管理器。
    以 sheet path 為 key 快取切幀結果，避免重複載入。
    """

    def __init__(self) -> None:
        self._cache: dict[str, list[pygame.Surface]] = {}
        self.effects: list[FxEffect] = []

    def _load(self, path: str, frame_w: int, frame_h: int) -> list[pygame.Surface]:
        if path in self._cache:
            return self._cache[path]
        sheet = pygame.image.load(path).convert_alpha()
        cols = sheet.get_width() // frame_w
        frames: list[pygame.Surface] = []
        for i in range(cols):
            surf = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
            surf.blit(sheet, (0, 0), pygame.Rect(i * frame_w, 0, frame_w, frame_h))
            frames.append(surf)
        self._cache[path] = frames
        return frames

    def spawn(self, path: str, frame_w: int, frame_h: int,
              x: int, y: int, speed: int = 3, flip_x: bool = False) -> None:
        frames = self._load(path, frame_w, frame_h)
        self.effects.append(FxEffect(frames, x, y, speed, flip_x))

    def update_and_draw(self, screen: pygame.Surface) -> None:
        for fx in self.effects:
            fx.update()
            fx.draw(screen)
        self.effects = [fx for fx in self.effects if not fx.done]
