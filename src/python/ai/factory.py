import random
from src.python.ai.controllers.base import AIController
from src.python.ai.controllers.fsm_ai import FSMAIController, FSM_PARAMS_LV1


def make_ai(char_type: int, level: int, seed: int) -> AIController:
    """
    char_type: 0=Knight 1=Mage 2=Archer 3=Paladin 4=Wizard
    level:     1=FSM  2=Pattern（Task35）  3=GOAP（Task36）
    seed:      用於 lv1 seeded RNG
    """
    rng = random.Random(seed)
    fsm = FSMAIController(FSM_PARAMS_LV1, rng)

    if level == 1:
        return fsm

    # Task 35/36 實作後於此擴充
    return fsm
