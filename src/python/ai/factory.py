import random

from src.python.ai.controllers.base import AIController
from src.python.ai.controllers.fsm_ai import FSMAIController, FSM_PARAMS_LV1
from src.python.ai.controllers.pattern_ai import PatternAIController
from src.python.ai.characters.knight_ai  import KNIGHT_PROFILE,  KNIGHT_PATTERNS
from src.python.ai.characters.mage_ai    import MAGE_PROFILE,    MAGE_PATTERNS
from src.python.ai.characters.archer_ai  import ARCHER_PROFILE,  ARCHER_PATTERNS
from src.python.ai.characters.paladin_ai import PALADIN_PROFILE, PALADIN_PATTERNS
from src.python.ai.characters.wizard_ai  import WIZARD_PROFILE,  WIZARD_PATTERNS

_CHAR_PROFILES = {
    0: (KNIGHT_PROFILE,  KNIGHT_PATTERNS),
    1: (MAGE_PROFILE,    MAGE_PATTERNS),
    2: (ARCHER_PROFILE,  ARCHER_PATTERNS),
    3: (PALADIN_PROFILE, PALADIN_PATTERNS),
    4: (WIZARD_PROFILE,  WIZARD_PATTERNS),
}


def make_ai(char_type: int, level: int, seed: int) -> AIController:
    """
    char_type: 0=Knight 1=Mage 2=Archer 3=Paladin 4=Wizard
    level:     1=FSM  2=Pattern  3=GOAP（Task36）
    seed:      用於 lv1 seeded RNG
    """
    rng = random.Random(seed)
    fsm = FSMAIController(FSM_PARAMS_LV1, rng)

    if level == 1:
        return fsm

    if level == 2:
        profile, patterns = _CHAR_PROFILES.get(char_type, _CHAR_PROFILES[0])
        return PatternAIController(profile, patterns, fallback=fsm)

    # Task 36 實作後於此擴充
    return fsm
