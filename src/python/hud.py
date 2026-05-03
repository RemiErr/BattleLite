import pygame
import os
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
_HP_H = 10
_MP_H = 7

# bar 圖片內側寬（green/red/yellow/purple 為 100px，background 為 110px）
_BAR_INNER_W = int(_BAR_W * 100 / 110)
_BAR_OFFSET = (_BAR_W - _BAR_INNER_W) // 2   # 左側留邊

# 緩降速率（像素/幀，60fps 下約 1.5 秒跑完整條 HP）
_HP_DRAIN_PX = 1.5
_MP_DRAIN_PX = 1.0

_COL_BG = (0,   0,   0,   190)
_COL_SEP = (70,  70,  70)
_COL_NAME = (255, 240, 180)
_COL_HP_VAL = (101, 206,  69)
_COL_MP_VAL = (255, 228,  71)
_COL_SHIELD = (255, 215,   0)
# 圖片載入失敗時的顏色備援
_COL_HP_BG = (70,   0,   0)
_COL_MP_BG = (0,    0,  70)
_COL_HP = (101, 206,  69)   # HP green
_COL_HP_D = (200,  30,  30)
_COL_MP = (255, 228,  71)   # MP yellow
_COL_MP_D = (130,  50, 200)


def _load_bar(bar_dir: str, name: str, w: int, h: int) -> pygame.Surface | None:
    try:
        img = pygame.image.load(os.path.join(bar_dir, name)).convert_alpha()
        return pygame.transform.smoothscale(img, (w, h))
    except Exception:
        return None


class HUD:
    """
    橫排對戰 HUD，固定在畫面頂部。
    每個玩家占 _SLOT_W 寬，從左到右依 P0→P3 排列。
    HP/MP 使用圖片 bar，受傷/耗 MP 時顯示緩降特效。
    """

    def __init__(self, char_assets: dict[int, BaseCharacter],
                 player_names: dict[int, str] | None = None):
        self.font_name = (pygame.font.SysFont("Consolas", 12, bold=True)
                          or pygame.font.SysFont("monospace", 12, bold=True))
        self.font_val = (pygame.font.SysFont("Consolas", 12, bold=True)
                         or pygame.font.SysFont("monospace", 12, bold=True))

        self.player_names:  dict[int, str] = player_names or {}
        self.faces:         dict[int, pygame.Surface] = {}
        self.max_hp:        dict[int, int] = {}
        self.max_mp:        dict[int, int] = {}
        self.char_names:    dict[int, str] = {}
        self.shield_states: dict[int, set[int]] = {}

        for char_type, asset in char_assets.items():
            self.max_hp[char_type] = asset.physics.max_hp
            self.max_mp[char_type] = asset.physics.max_mp
            self.char_names[char_type] = asset.name
            self.shield_states[char_type] = {
                ab.state_id for ab in asset.abilities if ab.damage_absorb > 0}
            if asset.faceset_path:
                try:
                    img = pygame.image.load(asset.faceset_path).convert_alpha()
                    self.faces[char_type] = pygame.transform.smoothscale(
                        img, (_FACE_SZ, _FACE_SZ))
                except Exception:
                    pass

        # 載入 bar 圖片資源
        bar_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__),
                         '..', '..', 'src', 'assets', 'HUD', 'bar'))
        self._bar_bg_hp = _load_bar(
            bar_dir, 'background.png', _BAR_W,       _HP_H)
        self._bar_bg_mp = _load_bar(
            bar_dir, 'background.png', _BAR_W,       _MP_H)
        self._bar_green = _load_bar(bar_dir, 'green.png',  _BAR_INNER_W, _HP_H)
        self._bar_red = _load_bar(bar_dir, 'red.png',    _BAR_INNER_W, _HP_H)
        self._bar_yellow = _load_bar(
            bar_dir, 'yellow.png', _BAR_INNER_W, _MP_H)
        self._bar_purple = _load_bar(
            bar_dir, 'purple.png', _BAR_INNER_W, _MP_H)

        # 緩降特效狀態（keyed by pid，float 保持亞像素精度）
        self._hp_drain: dict[int, float] = {}
        self._mp_drain: dict[int, float] = {}

    def draw(self, screen: pygame.Surface, players: list[tuple[int, object]]) -> None:
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
        max_hp = self.max_hp.get(char_type, 100_000)
        max_mp = self.max_mp.get(char_type,  50_000)

        # ── 更新緩降狀態 ──────────────────────────────────────
        hp_step = _HP_DRAIN_PX / _BAR_INNER_W * max_hp
        mp_step = _MP_DRAIN_PX / _BAR_INNER_W * max_mp

        if pid not in self._hp_drain:
            self._hp_drain[pid] = float(p.hp)
        if pid not in self._mp_drain:
            self._mp_drain[pid] = float(p.mp)

        if p.hp < self._hp_drain[pid]:
            self._hp_drain[pid] = max(
                float(p.hp), self._hp_drain[pid] - hp_step)
        else:
            self._hp_drain[pid] = float(p.hp)

        if p.mp < self._mp_drain[pid]:
            self._mp_drain[pid] = max(
                float(p.mp), self._mp_drain[pid] - mp_step)
        else:
            self._mp_drain[pid] = float(p.mp)

        # ── 頭像 ──────────────────────────────────────────────
        is_shielding = getattr(
            p, "state", -1) in self.shield_states.get(char_type, set())
        face = self.faces.get(char_type)
        if face:
            screen.blit(face, (sx + _PAD_L, _PAD_V))
        if is_shielding:
            pygame.draw.rect(screen, _COL_SHIELD,
                             (sx + _PAD_L - 2, _PAD_V - 2,
                              _FACE_SZ + 4, _FACE_SZ + 4), 2)

        bx = sx + _PAD_L + _FACE_SZ + _PAD_L

        # 動態計算垂直置中：名稱 + 間隔 + HP + 間隔 + MP 整體置中於 HUD_H
        name_h = self.font_name.get_height()
        content_h = name_h + 3 + _HP_H + 4 + _MP_H
        by = max(_PAD_V, (HUD_H - content_h) // 2)

        # ── 名稱 ──────────────────────────────────────────────
        class_name = self.char_names.get(char_type, "?")
        display_name = self.player_names.get(pid) or class_name
        label = self.font_name.render(
            f"P{pid}  {display_name}", True, _COL_NAME)
        screen.blit(label, (bx, by - 3))
        if is_shielding:
            shield_lbl = self.font_val.render("SHIELD", True, _COL_SHIELD)
            screen.blit(shield_lbl, (bx + _BAR_W - shield_lbl.get_width(), by))

        # ── HP 條 ─────────────────────────────────────────────
        hp_ratio = max(0.0, min(1.0, p.hp / max_hp))
        drain_ratio = max(0.0, min(1.0, self._hp_drain[pid] / max_hp))
        hp_px = int(_BAR_INNER_W * hp_ratio)
        drain_px = int(_BAR_INNER_W * drain_ratio)
        hp_y = by + name_h + 3

        if self._bar_bg_hp:
            screen.blit(self._bar_bg_hp, (bx, hp_y))
        else:
            pygame.draw.rect(screen, _COL_HP_BG, (bx, hp_y, _BAR_W, _HP_H))

        # 紅色緩降層（先畫，在綠色底下）
        if drain_px > hp_px:
            if self._bar_red:
                screen.blit(self._bar_red,
                            (bx + _BAR_OFFSET, hp_y), (0, 0, drain_px, _HP_H))
            else:
                pygame.draw.rect(screen, _COL_HP_D,
                                 (bx + hp_px, hp_y, drain_px - hp_px, _HP_H))

        # 綠色當前血量
        if hp_px > 0:
            if self._bar_green:
                screen.blit(self._bar_green,
                            (bx + _BAR_OFFSET, hp_y), (0, 0, hp_px, _HP_H))
            else:
                pygame.draw.rect(screen, _COL_HP, (bx, hp_y, hp_px, _HP_H))

        hp_surf = self.font_val.render(
            str(max(0, p.hp // 1000)), True, _COL_HP_VAL)
        screen.blit(hp_surf, (bx + _BAR_W + 4, hp_y - 3))

        # ── MP 條 ─────────────────────────────────────────────
        mp_ratio = max(0.0, min(1.0, p.mp / max_mp))
        mp_drain_r = max(0.0, min(1.0, self._mp_drain[pid] / max_mp))
        mp_px = int(_BAR_INNER_W * mp_ratio)
        mp_drain_px = int(_BAR_INNER_W * mp_drain_r)
        mp_y = hp_y + _HP_H + 4

        if self._bar_bg_mp:
            screen.blit(self._bar_bg_mp, (bx, mp_y))
        else:
            pygame.draw.rect(screen, _COL_MP_BG, (bx, mp_y, _BAR_W, _MP_H))

        # 紫色緩降層
        if mp_drain_px > mp_px:
            if self._bar_purple:
                screen.blit(self._bar_purple,
                            (bx + _BAR_OFFSET, mp_y), (0, 0, mp_drain_px, _MP_H))
            else:
                pygame.draw.rect(screen, _COL_MP_D,
                                 (bx + mp_px, mp_y, mp_drain_px - mp_px, _MP_H))

        # 黃色當前 MP
        if mp_px > 0:
            if self._bar_yellow:
                screen.blit(self._bar_yellow,
                            (bx + _BAR_OFFSET, mp_y), (0, 0, mp_px, _MP_H))
            else:
                pygame.draw.rect(screen, _COL_MP, (bx, mp_y, mp_px, _MP_H))

        mp_surf = self.font_val.render(
            str(max(0, p.mp // 1000)), True, _COL_MP_VAL)
        screen.blit(mp_surf, (bx + _BAR_W + 4, mp_y - 4))
