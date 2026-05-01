from abc import ABC, abstractmethod


class AIController(ABC):
    @abstractmethod
    def decide(self, ai_p, opp_p, entities: list) -> int:
        """每幀呼叫，回傳 u8 input bitmask。"""
        ...
