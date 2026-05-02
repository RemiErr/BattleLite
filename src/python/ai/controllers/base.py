from abc import ABC, abstractmethod


class AIController(ABC):
    @abstractmethod
    def decide(self, ai_p, opp_p, entities: list) -> int:
        """每幀呼叫，回傳 u8 input bitmask。"""
        ...

    @abstractmethod
    def get_debug_info(self) -> dict:
        """回傳用於 Debug Overlay 顯示的資訊字典。"""
        ...
