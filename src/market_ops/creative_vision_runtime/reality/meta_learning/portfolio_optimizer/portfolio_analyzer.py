"""E12.6.5 — Portfolio Analyzer。

收集多产品状态，生成产品组合快照。

职责:
  1. 汇总各产品关键指标
  2. 计算组合级别风险、增长、多样性评分
  3. 输出 PortfolioSnapshot
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import PortfolioSnapshot, _now


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class PortfolioAnalyzer:
    """产品组合分析器。

    收集多产品状态，计算组合级别的聚合指标。
    """

    def __init__(self) -> None:
        self._product_states: dict[str, dict[str, Any]] = {}

    def add_product_state(
        self, product_id: str, state: dict[str, Any]
    ) -> None:
        """添加产品状态。

        Args:
            product_id: 产品 ID
            state:      产品状态字典，可包含:
                        spend, revenue, roas, risk_score,
                        growth_score, diversity_score, etc.
        """
        self._product_states[product_id] = state

    def add_product_states(
        self, states: dict[str, dict[str, Any]]
    ) -> None:
        """批量添加产品状态。"""
        self._product_states.update(states)

    def analyze(self) -> PortfolioSnapshot:
        """分析产品组合，生成快照。

        Returns:
            PortfolioSnapshot
        """
        products = list(self._product_states.keys())
        if not products:
            return PortfolioSnapshot(products=[])

        total_spend = 0.0
        total_revenue = 0.0
        risk_scores: list[float] = []
        growth_scores: list[float] = []
        diversity_scores: list[float] = []

        for pid, state in self._product_states.items():
            total_spend += state.get("spend", 0.0)
            total_revenue += state.get("revenue", 0.0)
            risk_scores.append(state.get("risk_score", 0.0))
            growth_scores.append(state.get("growth_score", 0.0))
            diversity_scores.append(state.get("diversity_score", 0.0))

        # 总 ROAS
        total_roas = total_revenue / total_spend if total_spend > 0 else 0.0

        # 组合风险 = 平均风险
        avg_risk = _safe_mean(risk_scores)

        # 组合增长 = 平均增长
        avg_growth = _safe_mean(growth_scores)

        # 组合多样性 = 平均多样性
        avg_diversity = _safe_mean(diversity_scores)

        return PortfolioSnapshot(
            timestamp=_now_utc(),
            products=products,
            total_spend=round(total_spend, 2),
            total_revenue=round(total_revenue, 2),
            total_roas=round(total_roas, 4),
            risk_score=round(avg_risk, 4),
            growth_score=round(avg_growth, 4),
            diversity_score=round(avg_diversity, 4),
        )

    def get_product_state(self, product_id: str) -> dict[str, Any] | None:
        """获取单个产品状态。"""
        return self._product_states.get(product_id)

    def get_all_product_ids(self) -> list[str]:
        """获取所有产品 ID。"""
        return list(self._product_states.keys())

    def clear(self) -> None:
        """清除所有产品状态。"""
        self._product_states.clear()

    @property
    def product_count(self) -> int:
        return len(self._product_states)

    def __repr__(self) -> str:
        return f"PortfolioAnalyzer(products={self.product_count})"


def _safe_mean(values: list[float]) -> float:
    """安全计算平均值。"""
    if not values:
        return 0.0
    return sum(values) / len(values)