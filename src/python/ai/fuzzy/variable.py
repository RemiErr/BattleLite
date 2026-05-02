from dataclasses import dataclass
from typing import Callable


@dataclass
class FuzzySet:
    name: str
    fn:   Callable[[float], float]

    def membership(self, value: float) -> float:
        return max(0.0, min(1.0, self.fn(value)))


class FuzzyVariable:
    """語言變數：持有多個 FuzzySet，提供查詢介面。"""

    def __init__(self, name: str, sets: list[FuzzySet]):
        self.name  = name
        self._sets = sets

    def evaluate(self, value: float) -> dict[str, float]:
        """回傳各集合的正規化隸屬度向量（總和 ≈ 1.0）。"""
        raw   = {s.name: s.membership(value) for s in self._sets}
        total = sum(raw.values()) or 1.0
        return {k: v / total for k, v in raw.items()}

    def dominant(self, value: float) -> str:
        """回傳隸屬度最高的集合名稱。"""
        m = self.evaluate(value)
        return max(m, key=m.get)

    def weighted(self, value: float, weights: dict[str, float]) -> float:
        """依隸屬度加權計算純量，用於動態 Action cost。"""
        m = self.evaluate(value)
        return sum(m[k] * weights.get(k, 1.0) for k in m)
