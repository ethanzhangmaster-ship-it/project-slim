"""E12.7.2 — Hypothesis Generator。

增长假设生成器 —— 从根因生成可验证的增长假设。

职责:
  1. 接收 RootCause 分析结果
  2. 生成 GrowthHypothesis
  3. 映射到具体执行模块和动作
  4. 估算预期影响
"""

from __future__ import annotations

from typing import Any

from .models import (
    GrowthHypothesis,
    HypothesisStatus,
    RootCause,
)


# 根因 → 动作映射
_CAUSE_ACTION_MAP: dict[str, dict[str, Any]] = {
    "creative_fatigue": {
        "actions": [
            "generate_new_hook_variants",
            "mutate_creative_dna_freshness",
            "refresh_top_performing_creatives",
        ],
        "target_module": "E11_CreativeEvolution",
        "base_impact": 0.60,
    },
    "creative_diversity_low": {
        "actions": [
            "expand_dna_combinations",
            "explore_new_audience_segments",
            "generate_cross_product_inspirations",
        ],
        "target_module": "E11_CreativeEvolution",
        "base_impact": 0.50,
    },
    "winner_scarcity": {
        "actions": [
            "increase_experiment_volume",
            "test_new_creative_directions",
            "broaden_creative_hypothesis",
        ],
        "target_module": "E12_ExperimentEngine",
        "base_impact": 0.45,
    },
    "roas_decline": {
        "actions": [
            "audit_creative_performance",
            "adjust_budget_allocation",
            "optimize_targeting",
        ],
        "target_module": "E12.6.2_ResourceController",
        "base_impact": 0.55,
    },
    "roas_critical": {
        "actions": [
            "pause_underperforming_campaigns",
            "reduce_budget_immediately",
            "emergency_creative_refresh",
        ],
        "target_module": "E12.6.1_MetaDecision",
        "base_impact": 0.80,
    },
    "ctr_decline": {
        "actions": [
            "test_new_hook_strategies",
            "optimize_first_3_seconds",
            "generate_alternative_hooks",
        ],
        "target_module": "E11_CreativeEvolution",
        "base_impact": 0.50,
    },
    "cpi_inflation": {
        "actions": [
            "explore_new_audience_segments",
            "optimize_creative_for_lower_cpi",
            "adjust_bidding_strategy",
        ],
        "target_module": "E12.6.2_ResourceController",
        "base_impact": 0.40,
    },
    "market_decline": {
        "actions": [
            "evaluate_product_lifecycle",
            "consider_sunset_or_pivot",
            "reduce_budget_gradually",
        ],
        "target_module": "E12.6.5_PortfolioOptimizer",
        "base_impact": 0.35,
    },
    "high_competition": {
        "actions": [
            "differentiate_creative_strategy",
            "find_niche_audiences",
            "optimize_ltv_focus",
        ],
        "target_module": "E11_CreativeEvolution",
        "base_impact": 0.35,
    },
    "combined_fatigue_roas": {
        "actions": [
            "immediate_creative_refresh",
            "budget_reallocation_to_winners",
            "launch_emergency_experiment",
        ],
        "target_module": "E12.6.1_MetaDecision",
        "base_impact": 0.75,
    },
}


class HypothesisGenerator:
    """增长假设生成器。

    从根因分析生成可验证的增长假设。
    """

    def __init__(self) -> None:
        self._action_map = dict(_CAUSE_ACTION_MAP)
        self._hypotheses: list[GrowthHypothesis] = []

    def generate(
        self,
        root_cause: RootCause,
        product_id: str = "",
    ) -> GrowthHypothesis | None:
        """从根因生成增长假设。

        Args:
            root_cause: 根因分析结果
            product_id: 产品 ID

        Returns:
            GrowthHypothesis 或 None
        """
        mapping = self._action_map.get(root_cause.category)
        if not mapping:
            return None

        expected_impact = self._estimate_impact(
            root_cause.confidence,
            mapping["base_impact"],
        )

        hypothesis = GrowthHypothesis(
            problem=f"[{root_cause.category}] {root_cause.description}",
            root_cause=root_cause.description,
            root_cause_category=root_cause.category,
            confidence=root_cause.confidence,
            expected_impact=round(expected_impact, 4),
            recommended_actions=list(mapping["actions"]),
            target_module=mapping["target_module"],
            rationale=(
                f"Detected {root_cause.category} with confidence "
                f"{root_cause.confidence:.2f}. "
                f"Evidence: {', '.join(root_cause.evidence[:3])}. "
                f"Suggested fix: {root_cause.suggested_fix}"
            ),
            status=HypothesisStatus.PROPOSED,
            metadata={"product_id": product_id},
        )

        self._hypotheses.append(hypothesis)
        return hypothesis

    def generate_from_causes(
        self,
        causes: list[RootCause],
        product_id: str = "",
    ) -> list[GrowthHypothesis]:
        """从多个根因生成假设。

        Args:
            causes:     根因列表
            product_id: 产品 ID

        Returns:
            假设列表
        """
        hypotheses: list[GrowthHypothesis] = []
        for cause in causes:
            h = self.generate(cause, product_id)
            if h:
                hypotheses.append(h)
        return hypotheses

    def generate_from_observation(
        self,
        causes: list[RootCause],
        product_id: str,
    ) -> list[GrowthHypothesis]:
        """从观察结果生成假设。

        Args:
            causes:     根因列表
            product_id: 产品 ID

        Returns:
            假设列表
        """
        return self.generate_from_causes(causes, product_id)

    def _estimate_impact(
        self, confidence: float, base_impact: float
    ) -> float:
        """估算预期影响。

        公式: base_impact × confidence × 0.85 (折扣因子)

        Args:
            confidence:  根因置信度
            base_impact: 基础影响

        Returns:
            预期影响 [0, 1]
        """
        return min(1.0, base_impact * confidence * 0.85)

    def get_top_hypothesis(
        self, hypotheses: list[GrowthHypothesis]
    ) -> GrowthHypothesis | None:
        """获取最优假设（按风险调整后影响）。"""
        if not hypotheses:
            return None
        return max(hypotheses, key=lambda h: h.risk_adjusted_impact)

    def get_actionable_hypotheses(
        self, hypotheses: list[GrowthHypothesis]
    ) -> list[GrowthHypothesis]:
        """获取可执行的假设。"""
        return [h for h in hypotheses if h.is_actionable]

    def add_mapping(
        self, category: str, mapping: dict[str, Any]
    ) -> None:
        """添加自定义类别的动作映射。"""
        self._action_map[category] = mapping

    def get_history(self, limit: int = 100) -> list[GrowthHypothesis]:
        """获取假设历史。"""
        return self._hypotheses[-limit:]

    def clear_history(self) -> None:
        """清除历史。"""
        self._hypotheses.clear()

    @property
    def mapping_count(self) -> int:
        return len(self._action_map)

    def __repr__(self) -> str:
        return f"HypothesisGenerator(mappings={self.mapping_count})"