import random
from src.python.ai.controllers.base import AIController


class _NullAI(AIController):
    """佔位用，Task 34+ 實作各等級後替換。"""
    def decide(self, ai_p, opp_p, entities: list) -> int:
        return 0


def make_ai(char_type: int, level: int, seed: int) -> AIController:
    """
    char_type: 0=Knight 1=Mage 2=Archer 3=Paladin 4=Wizard
    level:     1=FSM  2=Pattern  3=GOAP
    seed:      用於 lv1 seeded RNG
    """
    # Task 34 起逐步替換為真實實作
    return _NullAI()
