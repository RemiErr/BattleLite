import pygame
from src.python.assets_manager.base_character import BaseCharacter

SCREEN_W = 1024
SCREEN_H = 640
HUD_H = 60          # HUD 橫條像素高度，renderer 需加此偏移

_NUM_SLOTS = 4
_SLOT_W = SCREEN_W // _NUM_SLOTS   # 256px per player
_FACE_SZ = 44
_PAD_V = (HUD_H - _FACE_SZ) // 2  # 垂直居中偏移 = 8px
_PAD_L = 6
_BAR_W = 140
_HP_H = 8
_MP_H = 6

_COL_HP = (50,  210,  50)
_COL_MP = (50,  150, 255)
_COL_HP_BG = (70,    0,   0)
_COL_MP_BG = (0,    0,  70)
_COL_BORDER = (140,  140, 140)
_COL_BG = (0,    0,   0, 190)
_COL_SEP = (70,   70,  70)
_COL_NAME = (255,  240, 180)
_COL_HP_VAL = (220,  220, 220)
_COL_MP_VAL = (180,  200, 255)
_COL_SHIELD = (255,  215,   0)  # 護盾啟動時的金色邊框

class HUD:
    """
    橫排對戰 HUD，固定在畫面頂部。
    每個玩家占 _SLOT_W 寬，從左到右依 P0→P3 排列。
    char_assets: {char_type: BaseCharacter}
    """

    def __init__(self, char_assets: dict[int, BaseCharacter],
                 player_names: dict[int, str] | None = None):
        self.font_name = pygame.font.SysFont("Consolas", 12, bold=True) \
            or pygame.font.SysFont("monospace", 12, bold=True)
        self.font_val = pygame.font.SysFont("Consolas", 10) \
            or pygame.font.SysFont("monospace", 10)

        self.player_names: dict[int, str] = player_names or {}
        self.faces: dict[int, pygame.Surface] = {}
        self.max_hp: dict[int, int] = {}
        self.max_mp: dict[int, int] = {}
        self.char_names: dict[int, str] = {}

        self.shield_states: dict[int, set[int]] = {}

        for char_type, asset in char_assets.items():
            self.max_hp[char_type] = asset.physics.max_hp
            self.max_mp[char_type] = asset.physics.max_mp
            self.char_names[char_type] = asset.name
            self.shield_states[char_type] = {ab.state_id for ab in asset.abilities if ab.damage_absorb > 0}
            if asset.faceset_path:
                try:
                    img = pygame.image.load(asset.faceset_path).convert_alpha()
                    self.faces[char_type] = pygame.transform.smoothscale(
                        img, (_FACE_SZ, _FACE_SZ))
                except Exception:
                    pass

    def draw(self, screen: pygame.Surface, players: list[tuple[int, object]]) -> None:
        # 整條 HUD 背景
        bg = pygame.Surface((SCREEN_W, HUD_H), pygame.SRCALPHA)
        bg.fill(_COL_BG)
        screen.blit(bg, (0, 0))
        pygame.draw.line(screen, _COL_SEP, (0, HUD_H - 1),
                         (SCREEN_W, HUD_H - 1))

        for pid, p in sorted(players, key=lambda t: t[0]):
            if pid >= _NUM_SLOTS:
                continue
            slot_x = pid * _SLOT_W
            if pid > 0:
                pygame.draw.line(screen, _COL_SEP, (slot_x, 0),
                                 (slot_x, HUD_H - 1))
            self._draw_slot(screen, slot_x, pid, p)

    def _draw_slot(self, screen: pygame.Surface, sx: int, pid: int, p) -> None:
        char_type = getattr(p, "character_type", 0)

        # 頭像
        is_shielding = getattr(p, "state", -1) in self.shield_states.get(char_type, set())
        face = self.faces.get(char_type)
        if face:
            face_surf = pygame.transform.flip(
                face, True, False) if pid >= 2 else face
            screen.blit(face_surf, (sx + _PAD_L, _PAD_V))
        if is_shielding:
            pygame.draw.rect(screen, _COL_SHIELD,
                             (sx + _PAD_L - 2, _PAD_V - 2,
                              _FACE_SZ + 4, _FACE_SZ + 4), 2)

        # 文字 / 條狀區起點（頭像右側）
        bx = sx + _PAD_L + _FACE_SZ + _PAD_L
        by = _PAD_V

        # 使用者名稱優先，否則用職業名稱
        class_name   = self.char_names.get(char_type, "?")
        display_name = self.player_names.get(pid) or class_name
        label = self.font_name.render(f"P{pid}  {display_name}", True, _COL_NAME)
        screen.blit(label, (bx, by))
        if is_shielding:
            shield_label = self.font_val.render("SHIELD", True, _COL_SHIELD)
            screen.blit(shield_label, (bx + _BAR_W - shield_label.get_width(), by))

        # HP 條
        max_hp = self.max_hp.get(char_type, 100_000)
        hp_ratio = max(0.0, min(1.0, p.hp / max_hp))
        hp_y = by + 16
        pygame.draw.rect(screen, _COL_HP_BG,  (bx, hp_y, _BAR_W, _HP_H))
        pygame.draw.rect(screen, _COL_HP,     (bx, hp_y,
                         int(_BAR_W * hp_ratio), _HP_H))
        pygame.draw.rect(screen, _COL_BORDER, (bx, hp_y, _BAR_W, _HP_H), 1)
        hp_surf = self.font_val.render(
            str(max(0, p.hp // 1000)), True, _COL_HP_VAL)
        screen.blit(hp_surf, (bx + _BAR_W + 4, hp_y))

        # MP 條
        max_mp = self.max_mp.get(char_type, 50_000)
        mp_ratio = max(0.0, min(1.0, p.mp / max_mp))
        mp_y = hp_y + _HP_H + 4
        pygame.draw.rect(screen, _COL_MP_BG,  (bx, mp_y, _BAR_W, _MP_H))
        pygame.draw.rect(screen, _COL_MP,     (bx, mp_y,
                         int(_BAR_W * mp_ratio), _MP_H))
        pygame.draw.rect(screen, _COL_BORDER, (bx, mp_y, _BAR_W, _MP_H), 1)
        mp_surf = self.font_val.render(
            str(max(0, p.mp // 1000)), True, _COL_MP_VAL)
        screen.blit(mp_surf, (bx + _BAR_W + 4, mp_y))
