"""E11 Phase 2 — Revenue Calculator。

计算素材的 ROAS / CPI / ARPU / LTV 等指标。

核心公式：
  CPI       = spend / installs
  ARPU      = total_revenue / installs
  LTV D30   = ARPU
  ROAS_D1   = (IAP D1 + AD D1) / spend
  ROAS_D7   = (IAP D7 + AD D7) / spend
  ROAS_D30  = (IAP D30 + AD D30) / spend
  Profit    = total_revenue - spend
  Payback   = CPI / ARPU * 30 (天)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from market_ops.creative_repository import CreativeEntity


@dataclass
class RevenueMetrics:
    """收入指标计算结果。

    所有指标均为计算属性，不存储原始数据。

    Usage:
        metrics = RevenueMetrics(
            cpi=2.5,
            arpu=6.0,
            ltv_d30=6.0,
            roas_d1=0.16,
            roas_d7=0.6,
            roas_d30=2.4,
            payback_days=12.5,
            profit=7000.0,
            is_profitable=True,
        )
    """

    cpi: float = 0.0          # Cost Per Install
    arpu: float = 0.0         # Average Revenue Per User
    ltv_d30: float = 0.0      # Lifetime Value (D30)
    roas_d1: float = 0.0      # Return On Ad Spend (D1)
    roas_d7: float = 0.0      # Return On Ad Spend (D7)
    roas_d30: float = 0.0     # Return On Ad Spend (D30)
    payback_days: float = 0.0 # 回本天数
    profit: float = 0.0       # 利润
    is_profitable: bool = False

    @property
    def roas_d30_pct(self) -> str:
        """ROAS D30 百分比格式。"""
        return f"{self.roas_d30:.2%}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "cpi": self.cpi,
            "arpu": self.arpu,
            "ltv_d30": self.ltv_d30,
            "roas_d1": self.roas_d1,
            "roas_d7": self.roas_d7,
            "roas_d30": self.roas_d30,
            "payback_days": self.payback_days,
            "profit": self.profit,
            "is_profitable": self.is_profitable,
        }


class RevenueCalculator:
    """收入指标计算器。

    从 CreativeEntity 中提取 acquisition 和 revenue 数据，
    计算 CPI、ARPU、ROAS、LTV、Profit、Payback 等指标。

    Usage:
        calc = RevenueCalculator()
        metrics = calc.calculate(entity)
        print(f"ROAS: {metrics.roas_d30_pct}")
    """

    def calculate(self, entity: CreativeEntity) -> RevenueMetrics:
        """计算单个 CreativeEntity 的收入指标。

        Args:
            entity: CreativeEntity（需包含 acquisition 和 revenue 数据）

        Returns:
            RevenueMetrics 计算结果
        """
        acq = entity.performance.acquisition
        rev = entity.performance.revenue

        spend = acq.spend
        installs = acq.installs
        total_rev = rev.total_revenue

        cpi = self._calc_cpi(spend, installs)
        arpu = self._calc_arpu(total_rev, installs)
        ltv_d30 = arpu
        roas_d1 = self._calc_roas(rev.iap_d1 + rev.ad_d1, spend)
        roas_d7 = self._calc_roas(rev.iap_d7 + rev.ad_d7, spend)
        roas_d30 = self._calc_roas(total_rev, spend)
        profit = self._calc_profit(total_rev, spend)
        payback = self._calc_payback_days(cpi, arpu)

        return RevenueMetrics(
            cpi=cpi,
            arpu=arpu,
            ltv_d30=ltv_d30,
            roas_d1=roas_d1,
            roas_d7=roas_d7,
            roas_d30=roas_d30,
            payback_days=payback,
            profit=profit,
            is_profitable=profit > 0,
        )

    def calculate_batch(
        self,
        entities: list[CreativeEntity],
    ) -> dict[str, RevenueMetrics]:
        """批量计算多个 CreativeEntity 的收入指标。

        Args:
            entities: CreativeEntity 列表

        Returns:
            {creative_asset_id: RevenueMetrics} 字典
        """
        return {
            entity.creative_asset_id: self.calculate(entity)
            for entity in entities
        }

    def calculate_summary(
        self,
        entities: list[CreativeEntity],
    ) -> dict[str, Any]:
        """计算汇总统计。

        Args:
            entities: CreativeEntity 列表

        Returns:
            summary 字典，包含 total_spend, total_revenue, overall_roas 等
        """
        total_spend = 0.0
        total_revenue = 0.0
        total_installs = 0
        total_profit = 0.0
        profitable_count = 0

        for entity in entities:
            acq = entity.performance.acquisition
            rev = entity.performance.revenue

            spend = acq.spend
            revenue = rev.total_revenue

            total_spend += spend
            total_revenue += revenue
            total_installs += acq.installs
            total_profit += revenue - spend

            if revenue > spend:
                profitable_count += 1

        overall_roas = (
            round(total_revenue / total_spend, 4) if total_spend > 0 else 0.0
        )

        return {
            "total_creatives": len(entities),
            "total_spend": total_spend,
            "total_revenue": total_revenue,
            "total_installs": total_installs,
            "total_profit": total_profit,
            "overall_roas": overall_roas,
            "profitable_count": profitable_count,
        }

    # ── Static helpers ───────────────────────────────────

    @staticmethod
    def _calc_cpi(spend: float, installs: int) -> float:
        if installs <= 0:
            return 0.0
        return round(spend / installs, 2)

    @staticmethod
    def _calc_arpu(revenue: float, installs: int) -> float:
        if installs <= 0:
            return 0.0
        return round(revenue / installs, 2)

    @staticmethod
    def _calc_ltv(revenue: float, installs: int) -> float:
        return RevenueCalculator._calc_arpu(revenue, installs)

    @staticmethod
    def _calc_roas(revenue: float, spend: float) -> float:
        if spend <= 0:
            return 0.0
        return round(revenue / spend, 4)

    @staticmethod
    def _calc_profit(revenue: float, spend: float) -> float:
        return round(revenue - spend, 2)

    @staticmethod
    def _calc_payback_days(cpi: float, arpu: float) -> float:
        if arpu <= 0:
            return 0.0
        return round(cpi / arpu * 30, 2)

    def __repr__(self) -> str:
        return "RevenueCalculator()"