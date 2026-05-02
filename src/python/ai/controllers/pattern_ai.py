from dataclasses import dataclass
from typing import Callable

from src.python.ai.controllers.base import AIController
from src.python.ai.characters.profile import CharAIProfile
from src.python.ai.world_state import build_pattern_world_state
from src.python.game_constants import (
    INPUT_RIGHT, INPUT_LEFT, INPUT_DOWN, INPUT_UP, INPUT_ATTACK, INPUT_SKILL)

# ── 相對方向符號 ──────────────────────────────────────────────────────────────
# 用高位 bit（不與 INPUT_* bit 0-6 衝突），可與其他輸入組合：J | AWAY。
# 執行時依對手 X 位置解析成 INPUT_RIGHT 或 INPUT_LEFT。
TOWARD = 1 << 7   # 朝對手方向（X 軸）
AWAY   = 1 << 8   # 遠離對手方向（X 軸）

_INPUT_MASK = 0x7F  # bit 0-6：標準輸入位元


def _resolve_mask(mask: int, ai_p, opp_p) -> int:
    """將 TOWARD/AWAY 符號解析為實際方向，保留其餘輸入 bit。"""
    result = mask & _INPUT_MASK
    if mask & TOWARD:
        result |= INPUT_RIGHT if opp_p.x > ai_p.x else INPUT_LEFT
        result |= INPUT_DOWN  if opp_p.y > ai_p.y else INPUT_UP
    if mask & AWAY:
        result |= INPUT_LEFT  if opp_p.x > ai_p.x else INPUT_RIGHT
        result |= INPUT_UP    if opp_p.y > ai_p.y else INPUT_DOWN
    if result & (INPUT_ATTACK | INPUT_SKILL):
        result |= INPUT_RIGHT if opp_p.x > ai_p.x else INPUT_LEFT
        result |= INPUT_DOWN  if opp_p.y > ai_p.y else INPUT_UP
    return result


@dataclass
class Pattern:
    name:            str
    condition:       Callable[[dict], bool]
    action_sequence: list[int]   # 可含 TOWARD / AWAY，亦可與 INPUT_* 組合
    step_duration:   list[int]
    priority:        int
    cooldown_frames: int = 0

    def __post_init__(self):
        assert len(self.action_sequence) == len(self.step_duration), (
            f"Pattern '{self.name}': action_sequence 與 step_duration 長度不符"
        )


class PatternAIController(AIController):
    def __init__(self, profile: CharAIProfile, patterns: list[Pattern],
                 fallback: AIController):
        self.profile  = profile
        self.patterns = sorted(patterns, key=lambda p: -p.priority)
        self.fallback = fallback

        self._active:     Pattern | None = None
        self._step:       int = 0
        self._step_timer: int = 0
        self._cooldowns:  dict[str, int] = {}
        self._ai_p  = None
        self._opp_p = None

    def decide(self, ai_p, opp_p, entities: list) -> int:
        self._ai_p  = ai_p
        self._opp_p = opp_p
        ws = build_pattern_world_state(ai_p, opp_p)
        self._tick_cooldowns()

        if self._active and self._step < len(self._active.action_sequence):
            return self._advance_step()

        for pattern in self.patterns:
            if self._cooldowns.get(pattern.name, 0) > 0:
                continue
            if pattern.condition(ws):
                self._activate(pattern)
                return self._advance_step()

        return self.fallback.decide(ai_p, opp_p, entities)

    def _activate(self, pattern: Pattern):
        self._active = pattern
        self._step = 0
        self._step_timer = pattern.step_duration[0]

    def _advance_step(self) -> int:
        raw  = self._active.action_sequence[self._step]
        mask = _resolve_mask(raw, self._ai_p, self._opp_p)
        self._step_timer -= 1
        if self._step_timer <= 0:
            self._step += 1
            if self._step >= len(self._active.action_sequence):
                self._cooldowns[self._active.name] = self._active.cooldown_frames
                self._active = None
            else:
                self._step_timer = self._active.step_duration[self._step]
        return mask

    def _tick_cooldowns(self):
        self._cooldowns = {k: max(0, v - 1) for k, v in self._cooldowns.items()}
