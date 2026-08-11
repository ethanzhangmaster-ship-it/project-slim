"""E11 Phase 4.1 — Hook Analyzer（IAP 版）。

分析前 3 秒 Hook 是否吸引目标付费用户：
  - hook_type:         impossible_result / before_after / collection / reward_reveal / progression / rare_item
  - hook_strength:     0-100，Hook 综合吸引力
  - curiosity:         0-100，好奇心驱动
  - reward_expectation: 0-100，奖励预期
  - purchase_intent:   0-100，购买意图

IAP 关键：
  不是"用户点击了没有"，而是"用户有没有产生'我想试一下'的冲动"。
"""

from __future__ import annotations

from .models import HookFeatures, HookType


# Hook 类型 → IAP 质量映射
HOOK_IAP_QUALITY: dict[HookType, dict[str, float]] = {
    HookType.RARE_ITEM:      {"strength": 85, "curiosity": 70, "reward": 90, "purchase": 80},
    HookType.COLLECTION:     {"strength": 80, "curiosity": 50, "reward": 85, "purchase": 75},
    HookType.REWARD_REVEAL:  {"strength": 80, "curiosity": 75, "reward": 90, "purchase": 70},
    HookType.PROGRESSION:    {"strength": 70, "curiosity": 40, "reward": 70, "purchase": 65},
    HookType.BEFORE_AFTER:   {"strength": 65, "curiosity": 60, "reward": 60, "purchase": 50},
    HookType.IMPOSSIBLE_RESULT: {"strength": 60, "curiosity": 90, "reward": 30, "purchase": 20},
    HookType.CURIOSITY:      {"strength": 30, "curiosity": 90, "reward": 15, "purchase": 10},
    HookType.UNKNOWN:        {"strength": 20, "curiosity": 30, "reward": 20, "purchase": 15},
}


class HookAnalyzer:
    """Hook 分析器。

    从 CreativeEntity 中检测 Hook 类型和维度评分。
    """

    def analyze(self, entity) -> HookFeatures:
        analysis = getattr(entity, "analysis", None)
        identity = getattr(entity, "identity", None)

        name = getattr(identity, "name", "").lower() if identity else ""
        hook_type_str = getattr(analysis, "hook_type", "") if analysis else ""

        # Hook 类型
        hook_type = self._detect_hook_type(hook_type_str, name)

        # 读取基础映射
        profile = HOOK_IAP_QUALITY.get(hook_type, HOOK_IAP_QUALITY[HookType.UNKNOWN])

        # 从名称增强
        strength = profile["strength"]
        curiosity = profile["curiosity"]
        reward_expectation = profile["reward"]
        purchase_intent = profile["purchase"]

        if "rare" in name or "legendary" in name:
            reward_expectation = max(reward_expectation, 85)
            purchase_intent = max(purchase_intent, 75)
        if "collect" in name:
            reward_expectation = max(reward_expectation, 80)
        if "unlock" in name:
            strength = max(strength, 75)
            reward_expectation = max(reward_expectation, 75)
        if "omg" in name or "impossible" in name or "wow" in name:
            curiosity = max(curiosity, 90)

        return HookFeatures(
            hook_type=hook_type,
            hook_strength=strength,
            curiosity=curiosity,
            reward_expectation=reward_expectation,
            purchase_intent=purchase_intent,
        )

    def analyze_batch(self, entities: list) -> list[HookFeatures]:
        return [self.analyze(e) for e in entities]

    def _detect_hook_type(self, hook_type_str: str, name: str) -> HookType:
        if hook_type_str:
            # 兼容旧格式
            mapping = {
                "COLLECTION": HookType.COLLECTION,
                "PROGRESSION": HookType.PROGRESSION,
                "CURIOSITY": HookType.CURIOSITY,
                "UNLOCK": HookType.REWARD_REVEAL,
                "MERGE_RESULT": HookType.REWARD_REVEAL,
                "TRANSFORMATION": HookType.BEFORE_AFTER,
                "RARE_ITEM": HookType.RARE_ITEM,
                "REWARD_REVEAL": HookType.REWARD_REVEAL,
                "BEFORE_AFTER": HookType.BEFORE_AFTER,
                "IMPOSSIBLE_RESULT": HookType.IMPOSSIBLE_RESULT,
            }
            if hook_type_str in mapping:
                return mapping[hook_type_str]
            try:
                return HookType(hook_type_str.lower())
            except ValueError:
                pass

        # 从名称推断
        if "rare" in name or "legendary" in name:
            return HookType.RARE_ITEM
        if "collect" in name:
            return HookType.COLLECTION
        if "reward" in name or "reveal" in name or "unlock" in name:
            return HookType.REWARD_REVEAL
        if "progress" in name or "level" in name:
            return HookType.PROGRESSION
        if "before" in name or "after" in name or "transform" in name:
            return HookType.BEFORE_AFTER
        if "omg" in name or "impossible" in name or "wow" in name:
            return HookType.IMPOSSIBLE_RESULT
        if "merge" in name:
            return HookType.REWARD_REVEAL  # Merge 结果展示 = 奖励揭示

        return HookType.UNKNOWN