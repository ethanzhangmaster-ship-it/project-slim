"""E12.2 — Recommendation Engine。

根据 RealityInsight 生成面向 E11 的进化建议。

核心职责：
  - 将洞察类型映射为具体行动
  - 确定突变目标基因
  - 计算行动优先级

不执行任何动作，只输出建议。

Usage:
    re = RecommendationEngine()
    rec = re.recommend(insight)
    # rec = {"action": "MUTATE_HOOK", "target": "creative_001", "priority": 0.87, "genes": ["hook"]}
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import InsightType, RealityInsight
    from ..intelligence.models import CombinedInsight

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """推荐引擎。

    根据洞察类型和严重程度，生成面向 E11 的进化建议。

    Attributes:
        total_recommended: 累计推荐次数
    """

    # 洞察类型 → 推荐行动映射
    TYPE_ACTION_MAP: dict[str, str] = {
        "creative_fatigue": "MUTATE_CREATIVE",
        "performance_drop": "EVALUATE_AND_MUTATE",
        "winning_pattern": "SCALE_CREATIVE",
        "market_shift": "ADAPT_STRATEGY",
        "scale_opportunity": "INCREASE_BUDGET",
        "data_anomaly": "VERIFY_AND_MONITOR",
    }

    # 洞察类型 → 推荐突变基因映射
    TYPE_GENES_MAP: dict[str, list[str]] = {
        "creative_fatigue": ["hook", "visual"],
        "performance_drop": ["hook", "gameplay", "monetization"],
        "winning_pattern": ["hook", "visual", "audience"],
        "market_shift": ["audience", "context"],
        "scale_opportunity": ["audience"],
        "data_anomaly": [],
    }

    def __init__(self) -> None:
        self.total_recommended: int = 0

    # ── Public API ───────────────────────────────────────

    def recommend(
        self,
        insight: RealityInsight,
    ) -> dict[str, Any]:
        """为单个洞察生成推荐。

        Args:
            insight: RealityInsight

        Returns:
            {
                "action": str,       # 推荐行动
                "target": str,       # 目标对象
                "priority": float,   # 优先级
                "genes": [str],      # 推荐突变基因
                "confidence": float, # 置信度
                "reason": str,       # 推荐理由
            }
        """
        action = insight.recommended_action or self._default_action(insight.type)
        genes = self._recommend_genes(insight)
        priority = self._compute_priority(insight)

        self.total_recommended += 1

        return {
            "action": action,
            "target": insight.target,
            "priority": round(priority, 4),
            "genes": genes,
            "confidence": round(insight.confidence, 4),
            "reason": self._build_reason(insight),
        }

    def recommend_batch(
        self,
        insights: list[RealityInsight],
    ) -> list[dict[str, Any]]:
        """批量推荐，按优先级降序。"""
        recommendations = [self.recommend(i) for i in insights]
        recommendations.sort(key=lambda r: r["priority"], reverse=True)
        return recommendations

    def recommend_from_combined(
        self,
        combined: CombinedInsight,
    ) -> dict[str, Any]:
        """从融合结果生成推荐。"""
        return {
            "action": combined.recommended_action or self._default_action(
                combined.primary_type,
            ),
            "target": "ALL",
            "priority": round(combined.aggregated_priority, 4),
            "genes": self._recommend_genes_for_type(combined.primary_type),
            "confidence": round(combined.aggregated_confidence, 4),
            "reason": f"Combined insight: {combined.primary_type.value} "
                      f"({len(combined.insights)} sub-insights)",
        }

    def to_evolution_opportunities(
        self,
        recommendations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """将推荐转换为 E11 EvolutionOpportunity 格式。

        Args:
            recommendations: recommend() 或 recommend_batch() 的输出

        Returns:
            EvolutionOpportunity 格式的 dict 列表
        """
        opportunities = []
        for rec in recommendations:
            opportunities.append({
                "type": rec["action"],
                "score": rec["priority"],
                "evidence": [rec["reason"]],
                "metadata": {
                    "target": rec["target"],
                    "confidence": rec["confidence"],
                    "recommended_genes": rec["genes"],
                },
            })
        return opportunities

    # ── Internal ────────────────────────────────────────

    def _default_action(self, insight_type: InsightType) -> str:
        return self.TYPE_ACTION_MAP.get(insight_type.value, "MONITOR")

    def _recommend_genes(self, insight: RealityInsight) -> list[str]:
        """根据洞察类型推荐突变基因。"""
        return self._recommend_genes_for_type(insight.type)

    def _recommend_genes_for_type(self, insight_type: InsightType) -> list[str]:
        """根据洞察类型推荐突变基因。"""
        return self.TYPE_GENES_MAP.get(insight_type.value, [])

    def _compute_priority(self, insight: RealityInsight) -> float:
        """计算行动优先级。"""
        if insight.priority > 0:
            return insight.priority

        # 根据严重程度和置信度计算
        severity_weights = {
            "critical": 1.0,
            "high": 0.75,
            "medium": 0.5,
            "low": 0.25,
        }
        sev_weight = severity_weights.get(insight.severity.value, 0.3)

        return round(sev_weight * 0.6 + insight.confidence * 0.4, 4)

    def _build_reason(self, insight: RealityInsight) -> str:
        """构建推荐理由。"""
        if insight.evidence:
            return f"{insight.type.value}: {insight.evidence[0]}"
        return f"{insight.type.value} detected (confidence={insight.confidence:.2f})"

    def __repr__(self) -> str:
        return f"RecommendationEngine(recommended={self.total_recommended})"