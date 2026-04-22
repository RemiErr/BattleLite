import os
import pygame
from src.python.assets_manager.base_character import BaseCharacter

_SHEET_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "src", "assets", "char", "knight", "sprite-sheet-183-123.png"
)

_FRAME_W = 183
_FRAME_H = 123

# (state, row, num_frames, loop, speed)
_STATE_ROWS = [
    (0, 0, 1, True,  6),  # IDLE:   Row0, 1 frame
    (1, 0, 6, True,  6),  # WALK:   Row0, 6 frames
    (2, 1, 6, False, 4),  # ATTACK: Row1
    (4, 2, 6, False, 4),  # SKILL:  Row2 (Guard)
    (3, 3, 6, False, 4),  # HURT:   Row3
]


class Knight(BaseCharacter):
    def __init__(self):
        super().__init__("Knight")
        self.load_sheet(
            os.path.normpath(_SHEET_PATH),
            _FRAME_W, _FRAME_H,
            _STATE_ROWS,
        )

    def get_sprite(self, state: int, elapsed_frames: int, facing_right: bool = True) -> pygame.Surface:
        surf = self.get_sprite_rect(state, elapsed_frames)
        if surf is None:
            surf = self.get_sprite_rect(0, 0)
        if not facing_right:
            return pygame.transform.flip(surf, True, False)
        return surf
