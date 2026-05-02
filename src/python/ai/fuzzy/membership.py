from typing import Callable


def triangular(a: float, b: float, c: float) -> Callable[[float], float]:
    """三角形：a 為 0，b 為峰值 1.0，c 為 0。"""
    def fn(x: float) -> float:
        if x <= a or x >= c:
            return 0.0
        if x <= b:
            return (x - a) / (b - a)
        return (c - x) / (c - b)
    return fn


def trapezoidal(a: float, b: float, c: float, d: float) -> Callable[[float], float]:
    """梯形：a→b 線性升，b→c 平台為 1.0，c→d 線性降。"""
    def fn(x: float) -> float:
        if x <= a or x >= d:
            return 0.0
        if x <= b:
            return (x - a) / (b - a) if b > a else 1.0
        if x <= c:
            return 1.0
        return (d - x) / (d - c) if d > c else 1.0
    return fn
