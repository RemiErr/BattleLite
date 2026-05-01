import random
from dataclasses import dataclass
from src.python.ai.controllers.base import AIController
from src.python.ai.world_state import build_fsm_world_state
from src.python.game_constants import (
    INPUT_RIGHT, INPUT_LEFT, INPUT_JUMP, INPUT_ATTACK, INPUT_SKILL)


@dataclass
class FSMDifficultyParams:
    reaction_delay:   int   = 6
    attack_range:     int   = 80_000
    skill_range:      int   = 160_000
    flee_dist:        int   = 120_000
    low_hp_threshold: int   = 300
    skill_mp:         int   = 20_000
    combo_max:        int   = 3
    retreat_frames:   int   = 30
    wait_frames:      int   = 15
    jump_prob:        float = 0.02


# lv1 建議難度參數
FSM_PARAMS_LV1 = FSMDifficultyParams(reaction_delay=8, jump_prob=0.03)


class FSMAIController(AIController):
    def __init__(self, params: FSMDifficultyParams, rng: random.Random):
        self.params = params
        self.rng    = rng
        self._state           = "APPROACH"
        self._timer           = 0
        self._attack_count    = 0
        self._reaction_delay  = 0

    def decide(self, ai_p, opp_p, entities: list) -> int:
        ws = build_fsm_world_state(ai_p, opp_p)
        self._transition(ws)
        return self._state_to_input(self._state, ai_p, opp_p)

    # ── 狀態機內部 ────────────────────────────────────────────────────────

    def _transition(self, ws: dict):
        if self._reaction_delay > 0:
            self._reaction_delay -= 1
            if self._state in ("RETREAT", "WAIT", "SKILL"):
                self._timer -= 1
            return

        new_state = self._evaluate_transition(ws)
        if new_state != self._state:
            self._enter_state(new_state)
            self._reaction_delay = self.params.reaction_delay
        else:
            if self._state in ("RETREAT", "WAIT", "SKILL"):
                self._timer -= 1
            if self._state == "ATTACK":
                self._attack_count += 1

    def _evaluate_transition(self, ws: dict) -> str:
        p   = self.params
        s   = self._state
        dist      = ws["dist"]
        self_hp   = ws["self_hp"]
        self_mp   = ws["self_mp"]

        if s == "APPROACH":
            if self_mp >= p.skill_mp and dist <= p.skill_range:
                return "SKILL"
            if self_hp < p.low_hp_threshold and dist < p.flee_dist:
                return "RETREAT"
            if dist <= p.attack_range:
                return "ATTACK"

        elif s == "ATTACK":
            if self_mp >= p.skill_mp:
                return "SKILL"
            if self._attack_count >= p.combo_max:
                return "WAIT"
            if dist > p.attack_range:
                return "APPROACH"

        elif s == "RETREAT":
            if self._timer <= 0:
                return "APPROACH"

        elif s == "SKILL":
            if self._timer <= 0:
                return "WAIT"

        elif s == "WAIT":
            if self._timer <= 0:
                return "APPROACH"

        return s

    def _enter_state(self, state: str):
        self._state = state
        if state == "RETREAT":
            self._timer = self.params.retreat_frames
        elif state == "WAIT":
            self._timer = self.params.wait_frames
        elif state == "SKILL":
            self._timer = self.params.wait_frames
        elif state == "ATTACK":
            self._attack_count = 0

    # ── 輸入遮罩生成 ──────────────────────────────────────────────────────

    def _state_to_input(self, state: str, ai_p, opp_p) -> int:
        move_toward = INPUT_RIGHT if opp_p.x > ai_p.x else INPUT_LEFT
        move_away   = INPUT_LEFT  if opp_p.x > ai_p.x else INPUT_RIGHT

        if state == "APPROACH":
            mask = move_toward
            if self.rng.random() < self.params.jump_prob and ai_p.z == 0:
                mask |= INPUT_JUMP
            return mask
        if state == "ATTACK":
            return INPUT_ATTACK
        if state == "RETREAT":
            return move_away
        if state == "SKILL":
            return INPUT_SKILL
        return 0  # WAIT
