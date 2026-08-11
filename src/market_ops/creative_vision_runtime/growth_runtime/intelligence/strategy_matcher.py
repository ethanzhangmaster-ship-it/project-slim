"""E13.5.3 Strategy Matcher — 机会-策略匹配器.

将 GrowthOpportunity 与 StrategyMemory 中的策略进行多维度匹配评分。

匹配维度:
  - Opportunity Type Match (0.35): 机会类型 vs 策略触发条件
  - Signal Similarity (0.25): 当前信号 vs 策略触发信号
  - Product Match (0.20): 产品相似度
  - Audience Match (0.20): 受众匹配度

连接:
  GrowthOpportunity → StrategyMatcher → StrategyMemory.recommend() → Candidates
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .intelligence_models import GrowthOpportunity

if TYPE_CHECKING:
    from ..memory.strategy_models import GrowthStrategyPattern


class StrategyMatcher:
    """策略匹配器 — 多维度匹配机会与策略.

    用法:
        matcher = StrategyMatcher()
        candidates = matcher.match(opportunity, strategies)
    """

    # 匹配权重
    WEIGHT_OPPORTUNITY = 0.35
    WEIGHT_SIGNAL = 0.25
    WEIGHT_PRODUCT = 0.20
    WEIGHT_AUDIENCE = 0.20

    # 信号相似度映射: 信号名称 → 关键词
    SIGNAL_KEYWORDS: dict[str, list[str]] = {
        "creative_fatigue": ["fatigue", "ctr", "decay", "frequency", "creative"],
        "creative_refresh": ["refresh", "creative", "variant", "dna", "mutate"],
        "creative_scale": ["scale", "winner", "roas", "budget", "spend"],
        "roas_drop": ["roas", "drop", "decline", "recovery", "crash"],
        "budget_waste": ["budget", "waste", "idle", "redistribution", "optimization"],
        "audience_expansion": ["audience", "lookalike", "expand", "segment"],
        "monetization": ["payer", "ltv", "arppu", "monetization", "revenue"],
        "risk_mitigation": ["risk", "anomaly", "crash", "spike", "pause"],
    }

    def match(
        self,
        opportunity: GrowthOpportunity,
        strategies: list[GrowthStrategyPattern],
    ) -> list[dict[str, Any]]:
        """对每个策略计算多维度匹配度.

        Args:
            opportunity: 增长机会
            strategies: 候选策略列表

        Returns:
            list[dict]: 每个策略的匹配结果，包含 strategy 和各项得分
        """
        results: list[dict[str, Any]] = []
        for strategy in strategies:
            scores = self._compute_match_scores(opportunity, strategy)
            match_score = self._compute_total_match(scores)
            results.append({
                "strategy": strategy,
                "scores": scores,
                "match_score": round(match_score, 4),
            })
        return results

    def _compute_match_scores(
        self,
        opportunity: GrowthOpportunity,
        strategy: GrowthStrategyPattern,
    ) -> dict[str, float]:
        """计算各项匹配得分."""
        return {
            "opportunity": self._match_opportunity_type(opportunity, strategy),
            "signal": self._match_signals(opportunity, strategy),
            "product": self._match_product(opportunity, strategy),
            "audience": self._match_audience(opportunity, strategy),
        }

    def _compute_total_match(self, scores: dict[str, float]) -> float:
        """加权汇总匹配得分."""
        return (
            scores["opportunity"] * self.WEIGHT_OPPORTUNITY
            + scores["signal"] * self.WEIGHT_SIGNAL
            + scores["product"] * self.WEIGHT_PRODUCT
            + scores["audience"] * self.WEIGHT_AUDIENCE
        )

    # ═══════════════════════════════════════════════════════════
    # Dimension Matchers
    # ═══════════════════════════════════════════════════════════

    def _match_opportunity_type(
        self,
        opportunity: GrowthOpportunity,
        strategy: GrowthStrategyPattern,
    ) -> float:
        """机会类型匹配.

        匹配规则:
          - 完全匹配: 1.0
          - 相关类型映射: 0.5-0.8
          - 不匹配: 0.0
        """
        opp_type = opportunity.opportunity_type.value
        strat_type = strategy.trigger.opportunity_type

        # 完全匹配
        if opp_type == strat_type:
            return 1.0

        # 相关类型映射
        related_map: dict[str, list[str]] = {
            "creative_refresh": ["creative_fatigue", "creative_scale", "creative_mutate"],
            "creative_scale": ["creative_refresh", "budget_optimization", "budget_redistribution"],
            "creative_mutate": ["creative_refresh", "creative_scale"],
            "budget_optimization": ["budget_redistribution", "creative_scale"],
            "budget_redistribution": ["budget_optimization", "creative_scale"],
            "audience_expansion": ["audience_refine"],
            "audience_refine": ["audience_expansion"],
            "risk_mitigation": ["budget_optimization"],
        }

        if opp_type in related_map and strat_type in related_map[opp_type]:
            # 越接近的映射分越高
            idx = related_map[opp_type].index(strat_type)
            return round(0.8 - idx * 0.15, 2)

        return 0.0

    def _match_signals(
        self,
        opportunity: GrowthOpportunity,
        strategy: GrowthStrategyPattern,
    ) -> float:
        """信号相似度匹配.

        基于策略触发信号与当前机会信号的语义重叠度。
        """
        # 当前信号从 opportunity reason 中提取关键词
        current_signals = self._extract_signal_keywords(opportunity)
        strategy_signals = strategy.trigger.signal_types

        if not current_signals or not strategy_signals:
            return 0.0

        # 计算信号重叠度
        matched = 0
        for signal in current_signals:
            for ss in strategy_signals:
                if self._signal_overlap(signal, ss):
                    matched += 1
                    break

        overlap_ratio = matched / max(len(current_signals), len(strategy_signals))
        return round(min(overlap_ratio * 1.5, 1.0), 4)

    def _match_product(
        self,
        opportunity: GrowthOpportunity,
        strategy: GrowthStrategyPattern,
    ) -> float:
        """产品匹配.

        基于 product_id 的相似度。
        """
        opp_product = opportunity.product_id.lower() if opportunity.product_id else ""
        strat_product = strategy.trigger.product_category.lower() if strategy.trigger.product_category else ""

        if not opp_product or not strat_product:
            return 0.5  # 无产品信息时中性

        if opp_product == strat_product:
            return 1.0

        # 部分匹配: 字符串包含
        if opp_product in strat_product or strat_product in opp_product:
            return 0.8

        # 单词重叠
        opp_words = set(opp_product.replace("_", " ").split())
        strat_words = set(strat_product.replace("_", " ").split())
        if opp_words and strat_words:
            overlap = len(opp_words & strat_words) / len(opp_words | strat_words)
            return round(overlap * 0.7, 4)

        return 0.3

    def _match_audience(
        self,
        opportunity: GrowthOpportunity,
        strategy: GrowthStrategyPattern,
    ) -> float:
        """受众匹配.

        基于 audience_segment 的相似度。
        """
        strat_audience = strategy.trigger.audience_segment.lower() if strategy.trigger.audience_segment else ""

        if not strat_audience:
            return 0.5  # 无受众信息时中性

        # 从 opportunity metadata 中获取受众信息
        opp_audience = opportunity.metadata.get("audience_segment", "").lower() if opportunity.metadata else ""

        if not opp_audience:
            return 0.5

        if opp_audience == strat_audience:
            return 1.0

        # 部分匹配
        if opp_audience in strat_audience or strat_audience in opp_audience:
            return 0.8

        # 平台匹配 (iOS/Android)
        platforms = {"ios", "android"}
        opp_platforms = platforms & set(opp_audience.replace("_", " ").split())
        strat_platforms = platforms & set(strat_audience.replace("_", " ").split())

        if opp_platforms and strat_platforms and opp_platforms == strat_platforms:
            return 0.6

        return 0.3

    # ═══════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════

    def _extract_signal_keywords(self, opportunity: GrowthOpportunity) -> list[str]:
        """从机会中提取信号关键词."""
        keywords: list[str] = []

        # 从机会类型推断
        opp_type = opportunity.opportunity_type.value
        keywords.append(opp_type)

        # 从 reason 中提取
        reason = opportunity.reason.lower()
        for signal_name, signal_kw in self.SIGNAL_KEYWORDS.items():
            if any(kw in reason for kw in signal_kw):
                keywords.append(signal_name)

        return list(set(keywords))

    @staticmethod
    def _signal_overlap(signal_a: str, signal_b: str) -> bool:
        """检查两个信号是否重叠."""
        if signal_a == signal_b:
            return True
        if signal_a in signal_b or signal_b in signal_a:
            return True
        # 去除常见分隔符后比较
        a_clean = signal_a.replace("_", "").replace("-", "")
        b_clean = signal_b.replace("_", "").replace("-", "")
        return a_clean == b_clean or a_clean in b_clean or b_clean in a_clean