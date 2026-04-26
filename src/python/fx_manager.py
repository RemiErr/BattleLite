import pygame
from dataclasses import dataclass


class FxEffect:
    def __init__(self, frames: list[pygame.Surface], x: int, y: int, speed: int = 3,
                 flip_x: bool = False, scale: float = 1.0):
        self.frames = frames
        self.x = x
        self.y = y
        self.speed = speed
        self.flip_x = flip_x
        self.scale = scale
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
        if self.scale != 1.0:
            w = max(1, int(frame.get_width()  * self.scale))
            h = max(1, int(frame.get_height() * self.scale))
            frame = pygame.transform.scale(frame, (w, h))
        blit_x = self.x - frame.get_width() // 2
        blit_y = self.y - frame.get_height() // 2
        screen.blit(frame, (blit_x, blit_y))


@dataclass
class _PlayerFxState:
    """跟隨玩家位置的持久迴圈 FX，當玩家 state 改變時自動停止。"""
    state_id:   int           # 有效的玩家 state；改變時停播
    path:       str
    frame_w:    int
    frame_h:    int
    offset_x:   int           # 相對玩家螢幕位置的水平偏移（px）
    offset_y:   int           # 相對玩家螢幕位置的垂直偏移（px）
    speed:      int
    scale:      float
    elapsed:    int = 0


class FxManager:
    """
    通用 2D 特效管理器。
    以 sheet path 為 key 快取切幀結果，避免重複載入。

    兩種特效模式：
      - 一次性（spawn）：播完即結束，用於攻擊命中等瞬間特效。
      - 玩家附著（attach_player_fx）：跟隨玩家位置持續循環播放，
        當玩家 state 不符時自動停止，適合長 timer 技能的整段視覺回饋。
    """

    def __init__(self) -> None:
        self._cache:      dict[str, list[pygame.Surface]] = {}
        self.effects:     list[FxEffect] = []
        self._player_fx:  dict[int, _PlayerFxState] = {}  # player_id → state

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
              x: int, y: int, speed: int = 3, flip_x: bool = False,
              scale: float = 1.0) -> None:
        """生成一次性特效（播完自動移除）。"""
        frames = self._load(path, frame_w, frame_h)
        self.effects.append(FxEffect(frames, x, y, speed, flip_x, scale))

    def attach_player_fx(
        self, player_id: int, state_id: int,
        path: str, frame_w: int, frame_h: int,
        offset_x: int = 0, offset_y: int = 0,
        speed: int = 3, scale: float = 1.0,
    ) -> None:
        """
        附著持久 FX 到指定玩家。
        - 循環播放，直到玩家 state 不再等於 state_id 時自動停止。
        - 每次切換到新技能狀態前呼叫一次；同一 player_id 的舊附著會被取代。
        """
        self._player_fx[player_id] = _PlayerFxState(
            state_id=state_id,
            path=path, frame_w=frame_w, frame_h=frame_h,
            offset_x=offset_x, offset_y=offset_y,
            speed=speed, scale=scale,
        )

    def detach_player_fx(self, player_id: int) -> None:
        """手動移除指定玩家的附著 FX。"""
        self._player_fx.pop(player_id, None)

    def update_player_fx(self, player_states: dict[int, int]) -> None:
        """
        更新玩家附著 FX 的存活狀態。每幀在渲染前呼叫一次。

        player_states: {player_id: current_state}
        """
        expired = [pid for pid, fx in self._player_fx.items()
                   if player_states.get(pid) != fx.state_id]
        for pid in expired:
            del self._player_fx[pid]
        for fx in self._player_fx.values():
            fx.elapsed += 1

    def draw_player_fx(self, screen: pygame.Surface,
                       player_screen_pos: dict[int, tuple[int, int]]) -> None:
        """
        繪製玩家附著 FX 到螢幕。

        player_screen_pos: {player_id: (sx, sy)} 玩家螢幕座標
        """
        for pid, fx in self._player_fx.items():
            if pid not in player_screen_pos:
                continue
            frames = self._load(fx.path, fx.frame_w, fx.frame_h)
            if not frames:
                continue
            idx = (fx.elapsed // max(1, fx.speed)) % len(frames)
            frame = frames[idx]
            if fx.scale != 1.0:
                w = max(1, int(frame.get_width()  * fx.scale))
                h = max(1, int(frame.get_height() * fx.scale))
                frame = pygame.transform.scale(frame, (w, h))
            sx, sy = player_screen_pos[pid]
            blit_x = sx + fx.offset_x - frame.get_width()  // 2
            blit_y = sy + fx.offset_y - frame.get_height() // 2
            screen.blit(frame, (blit_x, blit_y))

    def update_and_draw(self, screen: pygame.Surface) -> None:
        """更新並繪製所有一次性特效（不含玩家附著 FX）。"""
        for fx in self.effects:
            fx.update()
            fx.draw(screen)
        self.effects = [fx for fx in self.effects if not fx.done]
