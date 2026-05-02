import random

from src.python.ai.controllers.base    import AIController
from src.python.ai.controllers.fsm_ai  import FSMAIController, FSM_PARAMS_LV1
from src.python.ai.controllers.pattern_ai import PatternAIController
from src.python.ai.controllers.goap_ai import GOAPAIController
from src.python.ai.characters.knight_ai  import (
    KNIGHT_PROFILE,  KNIGHT_PATTERNS,  KNIGHT_GOAP_ACTIONS)
from src.python.ai.characters.mage_ai    import (
    MAGE_PROFILE,    MAGE_PATTERNS,    MAGE_GOAP_ACTIONS)
from src.python.ai.characters.archer_ai  import (
    ARCHER_PROFILE,  ARCHER_PATTERNS,  ARCHER_GOAP_ACTIONS)
from src.python.ai.characters.paladin_ai import (
    PALADIN_PROFILE, PALADIN_PATTERNS, PALADIN_GOAP_ACTIONS)
from src.python.ai.characters.wizard_ai  import (
    WIZARD_PROFILE,  WIZARD_PATTERNS,  WIZARD_GOAP_ACTIONS)

_CHAR_DATA = {
    0: (KNIGHT_PROFILE,  KNIGHT_PATTERNS,  KNIGHT_GOAP_ACTIONS),
    1: (MAGE_PROFILE,    MAGE_PATTERNS,    MAGE_GOAP_ACTIONS),
    2: (ARCHER_PROFILE,  ARCHER_PATTERNS,  ARCHER_GOAP_ACTIONS),
    3: (PALADIN_PROFILE, PALADIN_PATTERNS, PALADIN_GOAP_ACTIONS),
    4: (WIZARD_PROFILE,  WIZARD_PATTERNS,  WIZARD_GOAP_ACTIONS),
}


def make_ai(char_type: int, level: int, seed: int) -> AIController:
    """
    char_type: 0=Knight 1=Mage 2=Archer 3=Paladin 4=Wizard
    level:     1=FSM  2=Pattern  3=GOAP
    seed:      用於 lv1 seeded RNG
    """
    rng = random.Random(seed)
    fsm = FSMAIController(FSM_PARAMS_LV1, rng)

    if level == 1:
        return fsm

    profile, patterns, goap_actions = _CHAR_DATA.get(char_type, _CHAR_DATA[0])

    if level == 2:
        return PatternAIController(profile, patterns, fallback=fsm)

    if level == 3:
        return GOAPAIController(profile, goap_actions, fallback=fsm)

    return fsm
