from dataclasses import dataclass


@dataclass
class CharAIProfile:
    """角色 AI 知識的單一來源，lv2 與 lv3 共同引用。"""
    preferred_range:    int    # 偏好戰鬥距離（Rust 單位）
    skill_mp_threshold: int    # 放技能所需 MP
    aggression:         float  # 0.0 保守 ～ 1.0 積極
