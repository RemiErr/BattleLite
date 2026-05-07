from __future__ import annotations
from dataclasses import dataclass, field
import pygame

# 與 Rust INPUT_* 常數對齊
INPUT_ATTACK: int = 1 << 5
INPUT_SKILL:  int = 1 << 6


@dataclass
class PhysicsStats:
    """
    角色物理常數（per-character）。
    對應 Rust PhysicsConfig，由 apply_char_config() 呼叫 set_physics_config() 傳入。
    Hurt box 從 hurt_boxes[STATE_IDLE] 推導，不在此持有。
    """
    gravity:        int =    400
    jump_impulse:   int =  9_000
    walk_speed_x:   int =  5_000
    walk_speed_y:   int =  3_000
    hitstop_frames: int =      4
    max_hp:         int = 100_000
    max_mp:         int =  50_000


@dataclass
class SfxDef:
    """音效定義，由 CharSfxConfig 持有。"""
    path:   str
    volume: float = 1.0


@dataclass
class CharSfxConfig:
    """
    角色完整音效表，集中宣告所有觸發音效。
    SfxManager 根據幀差事件查表播放。

    on_ability : state_id → 技能/攻擊啟動音
    on_hit     : state_id → 近戰命中音（命中時由攻擊方角色類型查表）
    on_proj    : state_id → 投射物發射音（entity 生成時）
    on_hurt    : 受擊音
    on_land    : 落地音
    on_dead    : 死亡音
    """
    on_ability: dict[int, SfxDef] = field(default_factory=dict)
    on_hit:     dict[int, SfxDef] = field(default_factory=dict)
    on_proj:    dict[int, SfxDef] = field(default_factory=dict)
    on_hurt:    SfxDef | None = None
    on_jump:    SfxDef | None = None
    on_land:    SfxDef | None = None
    on_dead:    SfxDef | None = None


@dataclass
class FxDef:
    """
    特效定義，由 AbilityDef 持有或傳給 FxManager 執行。

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
        """投射物 entity debug 框（X 軸居中）。"""
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
        """回傳傳入 Rust set_ability / set_physics_config 所需的四個值：
        (front, half_w, half_h, z_offset)，單位 game unit = px × 1000。

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


@dataclass
class AbilityDef:
    """
    單一技能槽完整設定。對應 Rust AbilityConfig。

    trigger_button : INPUT_ATTACK 或 INPUT_SKILL 位元遮罩
    state_id       : Python 定義的狀態 ID（Rust 通用執行）
    timer          : 技能持續 ticks（game 單位，非幀數）
    hit_frame_start / hit_frame_end : 近戰有效視窗（動畫幀索引，apply 時 × speed → ticks）
    spawn_frame    : entity 生成的動畫幀索引（-1 = 用 spawn_timer_raw）
    spawn_timer_raw: 生成時 Rust timer 倒數值（spawn_frame < 0 時使用）
    dash_frame     : 衝刺觸發幀（apply 時 × speed → ticks）
    hit_box        : 近戰/技能碰撞框（None = 無近戰）
    proj_fx        : 投射物實體視覺 FX（飛行中循環）
    fx             : 狀態進入時在角色位置播放的 FX
    """
    trigger_button:   int
    state_id:         int
    mp_cost:          int  = 0
    timer:            int  = 20
    dmg:              int  = 10_000
    depth:            int  = 25_000
    kb_vx:            int  = 8_000
    kb_vz:            int  = 4_000
    kb_timer:         int  = 30
    melee_enabled:    bool = True
    hit_frame_start:  int  = 0
    hit_frame_end:    int  = 999
    damage_absorb:    int  = 0
    hp_regen_per_tick:  int  = 0
    on_hit_hp_restore:  int  = 0
    projectile_vx:    int  = 0
    projectile_lifetime: int = 30
    spawn_frame:      int  = -1
    spawn_timer_raw:  int  = 10
    spawn_entity:     bool = False
    dash_vx:          int  = 0
    dash_frame:       int  = 0
    is_skill:         bool = False
    trigger_context:  int  = 0   # reserved; 0 = ANY
    hit_box:          HitboxDef | None = None
    proj_fx:          FxDef | None     = None
    fx:               FxDef | None     = None   # state-entry FX


class BaseCharacter:
    """
    角色資源基類。
    負責從 Sprite Sheet 切幀、管理動畫播放，以及持有判定框與技能設定。
    """

    def __init__(self, name: str):
        self.name = name
        self.faceset_path: str = ""
        self.animations: dict[int, list[pygame.Surface]] = {}
        self.loop_map:   dict[int, bool] = {}
        self.speed_map:  dict[int, int]  = {}

        self.hurt_boxes: dict[int, HitboxDef] = {}

        # 幀中心到角色視覺中心的偏移（純渲染用）
        self.anchor_x: int = 0
        self.anchor_y: int = 0

        # 物理、技能、音效設定（子類 __init__ 覆寫）
        self.physics:   PhysicsStats    = PhysicsStats()
        self.abilities: list[AbilityDef] = []
        self.sfx:       CharSfxConfig   = CharSfxConfig()

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
        """從 abilities 找出對應 state_id 的 hit_box，取代舊版 hit_boxes dict。"""
        for ab in self.abilities:
            if ab.state_id == state:
                return ab.hit_box
        return None

    def get_ability(self, state: int) -> AbilityDef | None:
        """取得對應 state_id 的 AbilityDef，供 main.py 渲染與 debug 使用。"""
        for ab in self.abilities:
            if ab.state_id == state:
                return ab
        return None
