import pygame
from src.python.assets_manager.base_character import CharSfxConfig, SfxDef


class SfxManager:
    """
    集中管理所有角色音效。

    使用流程：
      1. register(char_type, cfg)  — 遊戲啟動時為每種角色登錄 CharSfxConfig
      2. set_volume(0.0~1.0)       — 依 Launcher 音量設定套用全局音量
      3. on_*(char_type, ...)      — main.py 偵測到幀差事件後呼叫

    事件方法：
      on_ability(char_type, state_id) — 技能/攻擊啟動
      on_hit    (char_type, state_id) — 近戰命中（攻擊方呼叫）
      on_proj   (char_type, state_id) — 投射物發射
      on_hurt   (char_type)           — 受擊
      on_land   (char_type)           — 落地
      on_dead   (char_type)           — 死亡
    """

    def __init__(self, volume: float = 1.0, enabled: bool = True) -> None:
        self._enabled = False
        if not enabled:
            return
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
                self._enabled = True
            except pygame.error as e:
                print(f"[SfxManager] 音訊裝置不可用，音效停用：{e}")
        else:
            self._enabled = True
        self._cache: dict[str, pygame.mixer.Sound] = {}
        self._cfgs:  dict[int, CharSfxConfig] = {}
        self._volume = max(0.0, min(1.0, volume))

    def register(self, char_type: int, cfg: CharSfxConfig) -> None:
        self._cfgs[char_type] = cfg

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, volume))

    def _play(self, sfx: SfxDef | None) -> None:
        if sfx is None or not self._enabled:
            return
        if sfx.path not in self._cache:
            try:
                self._cache[sfx.path] = pygame.mixer.Sound(sfx.path)
            except Exception as e:
                print(f"[SfxManager] 無法載入音效 {sfx.path}: {e}")
                return
        sound = self._cache[sfx.path]
        sound.set_volume(sfx.volume * self._volume)
        sound.play()

    def on_ability(self, char_type: int, state_id: int) -> None:
        cfg = self._cfgs.get(char_type)
        if cfg:
            self._play(cfg.on_ability.get(state_id))

    def on_hit(self, char_type: int, state_id: int) -> None:
        cfg = self._cfgs.get(char_type)
        if cfg:
            self._play(cfg.on_hit.get(state_id))

    def on_proj(self, char_type: int, state_id: int) -> None:
        cfg = self._cfgs.get(char_type)
        if cfg:
            self._play(cfg.on_proj.get(state_id))

    def on_jump(self, char_type: int) -> None:
        cfg = self._cfgs.get(char_type)
        if cfg:
            self._play(cfg.on_jump)

    def on_hurt(self, char_type: int) -> None:
        cfg = self._cfgs.get(char_type)
        if cfg:
            self._play(cfg.on_hurt)

    def on_land(self, char_type: int) -> None:
        cfg = self._cfgs.get(char_type)
        if cfg:
            self._play(cfg.on_land)

    def on_dead(self, char_type: int) -> None:
        cfg = self._cfgs.get(char_type)
        if cfg:
            self._play(cfg.on_dead)
