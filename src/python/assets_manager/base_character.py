from __future__ import annotations
from dataclasses import dataclass
import pygame


@dataclass
class HitboxDef:
    """
    判定框定義，所有座標以 Sprite 中心為原點、單位為像素。

    ox / oy : 預設朝向（未翻轉）時，框左上角相對 Sprite 中心的偏移。
               ox 正值 = 向右；oy 正值 = 向下。
    w / h   : 框的寬高。

    設定慣例（以 sheet 角色朝左為例）：
      - hurt_box  覆蓋角色身體，通常偏中心略向左（front 方向）。
      - hit_box   覆蓋武器/技能接觸區，通常在角色前方（朝左時 ox 為負且絕對值大）。
    """
    ox: int
    oy: int
    w: int
    h: int

    def to_screen_rect(self, cx: float, cy: float, facing_right: bool) -> pygame.Rect:
        """轉換為螢幕 Rect，facing_right 時自動水平鏡像。"""
        if facing_right:
            # 水平鏡像：原本左邊緣 ox → 新左邊緣 = -(ox + w)
            left = int(cx) - self.ox - self.w
        else:
            left = int(cx) + self.ox
        return pygame.Rect(left, int(cy) + self.oy, self.w, self.h)


class BaseCharacter:
    """
    角色資源基類。
    負責從 Sprite Sheet 切幀、管理動畫播放，以及持有判定框定義。
    """

    def __init__(self, name: str):
        self.name = name
        # { state: [pygame.Surface, ...] }
        self.animations: dict[int, list[pygame.Surface]] = {}
        # { state: bool }  True=循環, False=播放一次停在最後
        self.loop_map: dict[int, bool] = {}
        # { state: int }  每幀動畫持續幾個遊戲幀
        self.speed_map: dict[int, int] = {}

        # 判定框：子類別在 __init__ 填入
        # hurt_box : 角色被命中的範圍（身體）
        self.hurt_boxes: dict[int, HitboxDef] = {}
        # hit_box  : 攻擊動作傷害敵人的範圍；None 表示該狀態不造成傷害
        self.hit_boxes: dict[int, HitboxDef | None] = {}

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

    def get_hurt_box(self, state: int) -> HitboxDef | None:
        """回傳該狀態的 hurt box，找不到時 fallback 到 IDLE(0)。"""
        return self.hurt_boxes.get(state) or self.hurt_boxes.get(0)

    def get_hit_box(self, state: int) -> HitboxDef | None:
        """回傳該狀態的 hit box；None 代表不造成傷害。"""
        return self.hit_boxes.get(state)
