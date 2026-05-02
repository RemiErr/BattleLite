from src.python.ai.controllers.base      import AIController
from src.python.ai.characters.profile    import CharAIProfile
from src.python.ai.goap.action           import GOAPAction
from src.python.ai.goap.planner          import plan
from src.python.ai.goap.world_state      import (
    build_goap_world_state, should_replan, MAX_PLAN_AGE)
from src.python.game_constants import (
    INPUT_RIGHT, INPUT_LEFT, INPUT_UP, INPUT_DOWN)

GOAL_WIN     = {"opp_hp": ("<=", 0)}
GOAL_SURVIVE = {"in_range": False}
GOAL_RECOVER = {"in_range": False}


def _select_goal(ws: dict, profile: CharAIProfile) -> dict:
    if ws["self_hp_dom"] == "low":
        return GOAL_SURVIVE
    if ws["self_mp_dom"] == "low" and profile.aggression < 0.6:
        return GOAL_RECOVER
    return GOAL_WIN


def _resolve_direction(action: GOAPAction, ai_p, opp_p) -> int:
    if action.direction == "toward":
        x = INPUT_RIGHT if opp_p.x > ai_p.x else INPUT_LEFT
        y = INPUT_DOWN  if opp_p.y > ai_p.y else INPUT_UP
        return x | y
    if action.direction == "away":
        x = INPUT_LEFT  if opp_p.x > ai_p.x else INPUT_RIGHT
        y = INPUT_UP    if opp_p.y > ai_p.y else INPUT_DOWN
        return x | y
    return action.input_mask


class GOAPAIController(AIController):
    def __init__(self, profile: CharAIProfile, actions: list[GOAPAction],
                 fallback: AIController, max_plan_age: int = MAX_PLAN_AGE):
        self.profile      = profile
        self.actions      = actions
        self.fallback     = fallback
        self.max_plan_age = max_plan_age

        self._plan:       list[GOAPAction] = []
        self._plan_step:  int = 0
        self._step_timer: int = 0
        self._plan_age:   int = 0
        self._prev_ws:    dict = {}
        self._replan_count: int = 0   # debug 用

    def decide(self, ai_p, opp_p, entities: list) -> int:
        ws = build_goap_world_state(ai_p, opp_p)

        needs_replan = (
            not self._plan
            or self._plan_age >= self.max_plan_age
            or (self._plan_age >= 5 and should_replan(self._prev_ws, ws))
        )

        if needs_replan:
            goal = _select_goal(ws, self.profile)
            self._plan      = plan(ws, goal, self.actions)
            self._plan_step = 0
            self._step_timer = 0
            self._plan_age  = 0
            self._replan_count += 1

        self._prev_ws  = ws
        self._plan_age += 1

        if not self._plan:
            return self.fallback.decide(ai_p, opp_p, entities)

        return self._execute(ai_p, opp_p)

    def _execute(self, ai_p, opp_p) -> int:
        action = self._plan[self._plan_step]
        mask   = _resolve_direction(action, ai_p, opp_p)

        self._step_timer += 1
        if self._step_timer >= action.duration_frames:
            self._step_timer = 0
            self._plan_step += 1
            if self._plan_step >= len(self._plan):
                self._plan = []

        return mask
