from src.python.ai.controllers.base      import AIController
from src.python.ai.characters.profile    import CharAIProfile
from src.python.ai.goap.action           import GOAPAction
from src.python.ai.goap.planner          import plan
from src.python.ai.goap.world_state      import (
    build_goap_world_state, should_replan, MAX_PLAN_AGE)
from src.python.game_constants import (
    INPUT_RIGHT, INPUT_LEFT, INPUT_UP, INPUT_DOWN,
    INPUT_ATTACK, INPUT_SKILL)

GOAL_WIN    = {"opp_hp": ("<=", 0)}
GOAL_SURVIVE = {"in_danger": False}


def _select_goal(ws: dict, profile: CharAIProfile) -> tuple[dict, str]:
    """
    回傳 (goal, mode)。
    mode 決定 cost_fn 的激進程度，注入 ws["mode"] 後由 plan() 讀取。

    優先級（高→低）：
      5. 雙方殘血              → 孤注一擲 (gamble)
      4. 自身殘血              → 逃跑 (conservative)
      MID + 對手血少於我       → 把握機會進攻 (aggressive)
      MID + 平手或對手佔優     → 撤退迂迴 (conservative)  ← 阻止無腦攻擊
      HIGH + 對手血 < 我       → 激進追殺 (aggressive)
      HIGH + 平手              → 攻防平衡 (balanced)
      HIGH + 對手血 > 我       → 偏保守攻擊 (conservative)
    """
    self_dom = ws["self_hp_dom"]
    opp_dom  = ws["opp_hp_dom"]
    adv      = ws["hp_adv"]

    # 規則 5：雙方殘血 → 孤注一擲
    if self_dom == "low" and opp_dom == "low":
        return GOAL_WIN, "gamble"

    # 規則 4：自身殘血 → 逃跑
    if self_dom == "low":
        return GOAL_SURVIVE, "conservative"

    # MID 血量：謹慎決策，只有佔優才主動進攻
    if self_dom == "mid":
        if adv == "ahead":
            return GOAL_WIN, "aggressive"     # 對手血少 → 把握機會
        return GOAL_SURVIVE, "conservative"   # 平手或劣勢 → 撤退迂迴

    # HIGH 血量：完整的 1-3 規則
    if adv == "ahead":
        return GOAL_WIN, "aggressive"
    if adv == "behind":
        return GOAL_WIN, "conservative"
    return GOAL_WIN, "balanced"


def _resolve_direction(action: GOAPAction, ai_p, opp_p) -> int:
    if action.direction == "toward":
        x = INPUT_RIGHT if opp_p.x > ai_p.x else INPUT_LEFT
        y = INPUT_DOWN  if opp_p.y > ai_p.y else INPUT_UP
        return x | y
    if action.direction == "away":
        x = INPUT_LEFT  if opp_p.x > ai_p.x else INPUT_RIGHT
        y = INPUT_UP    if opp_p.y > ai_p.y else INPUT_DOWN
        return x | y
    if action.direction == "away_x_toward_y":
        # 遠程角色 Y 對位：X 遠離對手（保持遠距射程），Y 靠近對手（對齊深度）
        x = INPUT_LEFT  if opp_p.x > ai_p.x else INPUT_RIGHT
        y = INPUT_DOWN  if opp_p.y > ai_p.y else INPUT_UP
        return x | y
    # 攻擊 / 技能：加入面向對手的 X + Y 方向，防止背對或 Y 軸錯位
    if action.input_mask & (INPUT_ATTACK | INPUT_SKILL):
        x_face   = INPUT_RIGHT if opp_p.x > ai_p.x else INPUT_LEFT
        y_toward = INPUT_DOWN  if opp_p.y > ai_p.y else INPUT_UP
        return action.input_mask | x_face | y_toward
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
        ws = build_goap_world_state(ai_p, opp_p, self.profile.attack_range)

        needs_replan = (
            not self._plan
            or self._plan_age >= self.max_plan_age
            or (self._plan_age >= 5 and should_replan(self._prev_ws, ws))
        )

        if needs_replan:
            goal, mode = _select_goal(ws, self.profile)
            ws["mode"] = mode
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
            else:
                # 下一步先決條件未達成（靠近後仍未入射程等）→ 立即重新規劃
                next_ws = build_goap_world_state(ai_p, opp_p, self.profile.attack_range)
                if not self._plan[self._plan_step].is_applicable(next_ws):
                    self._plan = []

        return mask
