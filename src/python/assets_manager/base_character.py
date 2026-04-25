from __future__ import annotations
from dataclasses import dataclass, field
import pygame


@dataclass
class CharStats:
    """
    角色數值定義，單位與 Rust 遊戲單位一致（px × 1000）。
    session.set_char_config() 會把這些值傳入 Rust，驅動實際判定。
    """
    # 物理常數（per-character，預設值與原 Rust 全域常數相同）
    gravity:        int =    400
    jump_impulse:   int =  9_000
    walk_speed_x:   int =  5_000
    walk_speed_y:   int =  3_000
    hitstop_frames: int =      4
    max_hp:       int = 100_000   # 血量上限
    max_mp:       int =  50_000   # 魔力上限
    skill_cost:   int =  20_000   # 技能消耗魔力
    atk_dmg:      int =  10_000   # 普攻傷害
    skill_dmg:    int =  15_000   # 技能傷害
    # y 軸深度容許誤差（非 2D 螢幕概念，維持預設即可）
    atk_depth:    int =  25_000
    skl_depth:    int =  40_000
    # 普攻擊飛
    atk_kb_vx:    int =   8_000
    atk_kb_vz:    int =   4_000
    atk_kb_timer: int =      30
    # 技能擊飛
    skl_kb_vx:    int =   8_000
    skl_kb_vz:    int =   6_000
    skl_kb_timer: int =      40
    # SKILL 投射物（0 = 此角色技能無投射物）
    skl_projectile_vx:       int =      0   # 投射物每幀速度（×1000）
    skl_projectile_lifetime: int =     60   # 投射物存活幀數
    skl_spawn_timer:         int =     35   # SKILL 動作第幾幀發射（timer 倒數值）
    atk_timer:           int =      20  # ATTACK 狀態持續 tick 數
    skl_timer:           int =      40  # SKILL 狀態持續 tick 數
    # ATTACK 投射物（0 = 此角色的 ATTACK 是近戰）
    atk_projectile_vx:       int =      0   # ATTACK 投射物速度（×1000）
    atk_projectile_lifetime: int =     30   # ATTACK 投射物存活幀數
    atk_spawn_timer:         int =     10   # ATTACK 動作第幾 tick 發射
    # 近戰啟用旗標（可與投射物獨立設定）
    atk_melee_enabled: bool = True   # False = ATTACK 不走近戰判定
    skl_melee_enabled: bool = True   # False = SKILL 不走近戰判定


@dataclass
class FxDef:
    """
    角色特效定義，由角色 Python 設定、main.py 透過 FxManager 執行。

    path     : 特效 sprite sheet 絕對路徑
    frame_w  : 每幀寬度（px）
    frame_h  : 每幀高度（px）
    offset_x : 特效中心距角色中心的水平偏移（px，正值 = 朝面向方向）
    offset_y : 特效中心距角色中心的垂直偏移（px，正值 = 向下）
    scale    : 縮放倍率（1.0 = 原尺寸）
    speed    : 每張動畫幀持續幾個 game tick
    """
    path:     str
    frame_w:  int
    frame_h:  int
    offset_x: int   = 0
    offset_y: int   = 0
    scale:    float = 1.0
    speed:    int   = 3


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
        """角色近戰 debug 框。cx/cy 為 Sprite 中心（物理位置投影），facing_right 時水平鏡像。"""
        if facing_right:
            left = int(cx) - self.ox - self.w
        else:
            left = int(cx) + self.ox
        return pygame.Rect(left, int(cy) + self.oy, self.w, self.h)

    def to_entity_screen_rect(self, ex: float, ey: float) -> pygame.Rect:
        """投射物 entity debug 框。
        Rust entity 碰撞以 e.x 為中心左右對稱（不套 front），X 軸故居中。
        Y 軸：ey + oy，與 to_rust_params() 的 z_offset 推導一致。
        """
        return pygame.Rect(int(ex) - self.w // 2, int(ey) + self.oy, self.w, self.h)

    def screen_center(self, cx: float, cy: float, facing_right: bool) -> tuple[float, float]:
        """回傳角色 hit box 中心的螢幕座標，用於定位近戰 FX 特效。"""
        if facing_right:
            center_x = cx - self.ox - self.w + self.w // 2
        else:
            center_x = cx + self.ox + self.w // 2
        center_y = cy + self.oy + self.h // 2
        return center_x, center_y

    def entity_screen_center(self, ex: float, ey: float) -> tuple[float, float]:
        """回傳 entity hit box 中心的螢幕座標，用於定位投射物 FX 特效。"""
        return ex, ey + self.oy + self.h // 2

    def to_rust_params(self) -> tuple[int, int, int, int]:
        """回傳傳入 Rust set_char_config 所需的四個值（單位 game unit = px × 1000）：
        (front, half_w, half_h, z_offset)

        front    = -(ox + w//2) × 1000  框中心距角色中心的距離（朝面向方向為正）
        half_w   = (w // 2) × 1000      框半寬（X 軸）
        half_h   = (h // 2) × 1000      框半高（Z 軸）
        z_offset = -(oy + h//2) × 1000  框中心距角色 z 的偏移（screen-y 向下取反）
        """
        front    = -(self.ox + self.w // 2) * 1000
        half_w   = (self.w // 2) * 1000
        half_h   = (self.h // 2) * 1000
        z_offset = -(self.oy + self.h // 2) * 1000
        return front, half_w, half_h, z_offset


class BaseCharacter:
    """
    角色資源基類。
    負責從 Sprite Sheet 切幀、管理動畫播放，以及持有判定框定義。
    """

    def __init__(self, name: str):
        self.name = name
        self.faceset_path: str = ""
        self.animations: dict[int, list[pygame.Surface]] = {}
        self.loop_map:    dict[int, bool] = {}
        self.speed_map:   dict[int, int]  = {}

        self.hurt_boxes: dict[int, HitboxDef] = {}
        self.hit_boxes:  dict[int, HitboxDef | None] = {}
        self.stats: CharStats = CharStats()

        # 幀中心到角色視覺中心的偏移（純渲染用，不影響 hitbox 或物理）
        # anchor_x: 正值 = sprite 向左移（視覺中心在幀中心右方）
        # anchor_y: 正值 = sprite 向上移（視覺腳在幀中心下方）
        self.anchor_x: int = 0
        self.anchor_y: int = 0

        # 特效設定（None = 此動作無特效）
        self.atk_fx: FxDef | None = None           # ATTACK 狀態切換時在角色位置播放（近戰用）
        self.atk_proj_fx: FxDef | None = None      # ATTACK 投射物實體視覺（飛行中循環）
        self.skl_fx: FxDef | None = None           # SKILL 狀態切換時在角色位置播放（近戰/非投射物用）
        self.skl_proj_fx: FxDef | None = None      # SKILL 投射物實體視覺（飛行中循環）

    def load_sheet(self, path: str, frame_w: int, frame_h: int,
                   state_rows: list[tuple]) -> None:
        """
        載入 Sprite Sheet 並切幀存入 self.animations。

        state_rows 格式：[(state, row, num_frames, loop, speed), ...]
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

    def load_sheet_linear(self, path: str, frame_w: int, frame_h: int,
                          cols_per_row: int, state_frames: list[tuple]) -> None:
        """
        支援跨列動畫的切幀方法。
        state_frames: [(state, start_frame, num_frames, loop, speed), ...]
        start_frame: 線性幀索引（row * cols_per_row + col）
        """
        sheet = pygame.image.load(path).convert_alpha()
        for state, start_frame, num_frames, loop, speed in state_frames:
            frames: list[pygame.Surface] = []
            for i in range(num_frames):
                idx = start_frame + i
                col = idx % cols_per_row
                row = idx // cols_per_row
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

    def get_sprite(self, state: int, elapsed_frames: int, facing_right: bool = True) -> pygame.Surface:
        surf = self.get_sprite_rect(state, elapsed_frames)
        if surf is None:
            surf = self.get_sprite_rect(0, 0)
        assert surf is not None
        if facing_right:
            return pygame.transform.flip(surf, True, False)
        return surf

    def get_hurt_box(self, state: int) -> HitboxDef | None:
        return self.hurt_boxes.get(state) or self.hurt_boxes.get(0)

    def get_hit_box(self, state: int) -> HitboxDef | None:
        return self.hit_boxes.get(state)
