"""E11 Phase 4.1 — Monetization Analyzer（IAP 专用）。

分析广告有没有展示"购买理由"：
  - purchase_trigger: rarity / power / customization / collection / progression
  - iap_visibility:   0-100，IAP 元素展示程度
  - value_perception: 0-100，用户对价值的感知
  - urgency:          0-100，紧迫感

不是"好不好玩"，而是"为什么用户愿意付钱"。
"""

from __future__ import annotations

from .models import MonetizationFeatures, PurchaseTrigger, HookType


# Hook → 购买触发映射
HOOK_TRIGGER_MAP: dict[HookType, dict[str, float]] = {
    HookType.RARE_ITEM: {
        "rarity": 90, "power": 40, "customization": 30,
        "collection": 70, "progression": 30,
    },
    HookType.COLLECTION: {
        "rarity": 70, "power": 30, "customization": 40,
        "collection": 90, "progression": 50,
    },
    HookType.REWARD_REVEAL: {
        "rarity": 80, "power": 50, "customization": 30,
        "collection": 60, "progression": 40,
    },
    HookType.PROGRESSION: {
        "rarity": 40, "power": 60, "customization": 30,
        "collection": 50, "progression": 85,
    },
    HookType.BEFORE_AFTER: {
        "rarity": 50, "power": 70, "customization": 60,
        "collection": 40, "progression": 60,
    },
    HookType.IMPOSSIBLE_RESULT: {
        "rarity": 30, "power": 60, "customization": 20,
        "collection": 20, "progression": 20,
    },
    HookType.CURIOSITY: {
        "rarity": 10, "power": 20, "customization": 10,
        "collection": 10, "progression": 10,
    },
    HookType.UNKNOWN: {
        "rarity": 20, "power": 20, "customization": 20,
        "collection": 20, "progression": 20,
    },
}


class MonetizationAnalyzer:
    """变现分析器。

    分析素材展示的 IAP 价值和购买触发。
    """

    def analyze(self, entity, hook_features=None) -> MonetizationFeatures:
        """分析单个 CreativeEntity 的变现展示。

        Args:
            entity: CreativeEntity 实例
            hook_features: 可选的 HookFeatures（避免重复分析）
        """
        analysis = getattr(entity, "analysis", None)
        identity = getattr(entity, "identity", None)
        name = getattr(identity, "name", "").lower() if identity else ""

        # 获取 Hook 类型
        if hook_features is not None:
            hook_type = hook_features.hook_type
        else:
            hook_type_str = getattr(analysis, "hook_type", "") if analysis else ""
            hook_type = self._detect_hook_type(hook_type_str, name)

        # Purchase Trigger
        purchase_trigger = self._analyze_purchase_trigger(hook_type, name)

        # IAP Visibility
        iap_visibility = self._analyze_iap_visibility(entity, hook_type, name)

        # Value Perception
        value_perception = self._analyze_value_perception(hook_type, name, purchase_trigger)

        # Urgency
        urgency = self._analyze_urgency(entity, name)

        return MonetizationFeatures(
            purchase_trigger=purchase_trigger,
            iap_visibility=iap_visibility,
            value_perception=value_perception,
            urgency=urgency,
        )

    def analyze_batch(
        self, entities: list, hook_features_list: list | None = None,
    ) -> list[MonetizationFeatures]:
        results = []
        for i, entity in enumerate(entities):
            hf = hook_features_list[i] if hook_features_list else None
            results.append(self.analyze(entity, hook_features=hf))
        return results

    # ── Purchase Trigger ─────────────────────────────────

    def _analyze_purchase_trigger(self, hook_type: HookType, name: str) -> PurchaseTrigger:
        profile = HOOK_TRIGGER_MAP.get(hook_type, HOOK_TRIGGER_MAP[HookType.UNKNOWN])

        rarity = profile["rarity"]
        power = profile["power"]
        customization = profile["customization"]
        collection = profile["collection"]
        progression = profile["progression"]

        # 从名称增强
        if "rare" in name or "legendary" in name:
            rarity = max(rarity, 90)
        if "collect" in name:
            collection = max(collection, 85)
        if "power" in name or "strong" in name:
            power = max(power, 80)
        if "customize" in name or "decorate" in name or "design" in name:
            customization = max(customization, 80)
        if "progress" in name or "level" in name:
            progression = max(progression, 80)

        return PurchaseTrigger(
            rarity=rarity, power=power, customization=customization,
            collection=collection, progression=progression,
        )

    # ── IAP Visibility ───────────────────────────────────

    def _analyze_iap_visibility(self, entity, hook_type: HookType, name: str) -> float:
        """分析 IAP 元素的展示程度。"""
        analysis = getattr(entity, "analysis", None)
        reward_type = getattr(analysis, "reward_type", "") if analysis else ""

        # 有 reward_type 且不是 UNKNOWN 时，IAP 可见度高
        if reward_type and reward_type.upper() != "UNKNOWN":
            return 80

        # 从 Hook 推断
        if hook_type in (HookType.RARE_ITEM, HookType.COLLECTION, HookType.REWARD_REVEAL):
            return 75
        if hook_type == HookType.PROGRESSION:
            return 60
        if hook_type in (HookType.CURIOSITY, HookType.IMPOSSIBLE_RESULT):
            return 15

        return 30

    # ── Value Perception ────────────────────────────────

    def _analyze_value_perception(
        self, hook_type: HookType, name: str, trigger: PurchaseTrigger,
    ) -> float:
        """分析用户对价值的感知。"""
        # 基于购买触发强度
        base = trigger.trigger_strength * 0.6

        # 稀有度 + 收藏价值 = 高感知价值
        rarity_bonus = (trigger.rarity + trigger.collection) / 2 * 0.3

        # 从名称推断
        name_bonus = 0
        if "exclusive" in name or "limited" in name:
            name_bonus = 20
        if "rare" in name or "legendary" in name:
            name_bonus = max(name_bonus, 15)

        return min(base + rarity_bonus + name_bonus, 100)

    # ── Urgency ──────────────────────────────────────────

    def _analyze_urgency(self, entity, name: str) -> float:
        """分析紧迫感。"""
        urgency = 0

        if "limited" in name or "exclusive" in name:
            urgency = 80
        if "event" in name or "special" in name:
            urgency = max(urgency, 70)
        if "now" in name or "today" in name:
            urgency = max(urgency, 60)

        return urgency

    def _detect_hook_type(self, hook_type_str: str, name: str) -> HookType:
        if hook_type_str:
            try:
                return HookType(hook_type_str.lower())
            except ValueError:
                pass
        if "rare" in name or "legendary" in name:
            return HookType.RARE_ITEM
        if "collect" in name:
            return HookType.COLLECTION
        if "reward" in name or "reveal" in name:
            return HookType.REWARD_REVEAL
        if "progress" in name:
            return HookType.PROGRESSION
        return HookType.UNKNOWN