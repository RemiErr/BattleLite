import pygame

INPUT_RIGHT  = 1 << 0
INPUT_LEFT   = 1 << 1
INPUT_UP     = 1 << 2
INPUT_DOWN   = 1 << 3
INPUT_JUMP   = 1 << 4
INPUT_ATTACK = 1 << 5
INPUT_SKILL  = 1 << 6

_KEY_PRESETS = [
    # Preset 0: 方向鍵 + Z/X + Space
    {INPUT_RIGHT: pygame.K_RIGHT, INPUT_LEFT: pygame.K_LEFT,
     INPUT_UP: pygame.K_UP,       INPUT_DOWN: pygame.K_DOWN,
     INPUT_JUMP: pygame.K_SPACE,  INPUT_ATTACK: pygame.K_z, INPUT_SKILL: pygame.K_x},
    # Preset 1: WASD + J/K + Space
    {INPUT_RIGHT: pygame.K_d,    INPUT_LEFT: pygame.K_a,
     INPUT_UP: pygame.K_w,       INPUT_DOWN: pygame.K_s,
     INPUT_JUMP: pygame.K_SPACE, INPUT_ATTACK: pygame.K_j, INPUT_SKILL: pygame.K_k},
]


def get_input_mask(key_map: dict) -> int:
    keys = pygame.key.get_pressed()
    mask = 0
    for bit, k in key_map.items():
        if keys[k]:
            mask |= bit
    return mask


def load_key_map(preset_idx: int) -> dict:
    return _KEY_PRESETS[preset_idx % len(_KEY_PRESETS)]
