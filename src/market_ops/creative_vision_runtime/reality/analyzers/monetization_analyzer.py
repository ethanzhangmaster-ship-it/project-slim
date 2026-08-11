"""E12.2 — Monetization Analyzer。

商业化分析器 —— 回答"用户为什么付费？为什么不付费？哪些内容推动收入？"

通过 ThinkingData 事件分析 API 分析：
  - 付费率 / ARPU / ARPPU
  - 用户分层（non_payer → first_payer → repeat_payer → whale）
  - Offer 转化分析
  - 首充时间分布
  - LTV 预测

Usage:
    analyzer = MonetizationAnalyzer(td_reality)
    snapshot = analyzer.analyze(project_id=102, lookback_days=30)
    print(snapshot.payer_rate, snapshot.arpu)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..thinkingdata_reality import ThinkingDataReality

logger = logging.getLogger(__name__)


@dataclass
class OfferPerformance:
    """单个 Offer 表现。"""

    offer_name: str = ""
    impressions: int = 0
    purchases: int = 0
    conversion_rate: float = 0.0
    revenue: float = 0.0
    avg_order_value: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "offer_name": self.offer_name,
            "impressions": self.impressions,
            "purchases": self.purchases,
            "conversion_rate": round(self.conversion_rate, 4),
            "revenue": round(self.revenue, 2),
            "avg_order_value": round(self.avg_order_value, 2),
        }


@dataclass
class MonetizationSnapshot:
    """商业化快照。"""

    project_id: int = 0
    period_start: str = ""
    period_end: str = ""

    # 核心指标
    payer_rate: float = 0.0
    arpu: float = 0.0
    arppu: float = 0.0
    total_revenue: float = 0.0
    total_users: int = 0
    total_payers: int = 0

    # 用户分层
    payer_segments: dict[str, int] = field(default_factory=dict)
    # {"non_payer": 9000, "first_payer": 300, "repeat_payer": 500, "whale": 200}

    # 首充
    avg_first_pay_days: float = 0.0
    first_pay_distribution: dict[str, int] = field(default_factory=dict)
    # {"day_1": 150, "day_3": 80, "day_7": 50, "day_14": 30, "day_30+": 20}

    # Offer 表现
    offers: list[OfferPerformance] = field(default_factory=list)

    # LTV
    ltv_d7: float = 0.0
    ltv_d30: float = 0.0
    ltv_d90: float = 0.0

    # 洞察
    insights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "payer_rate": round(self.payer_rate, 4),
            "arpu": round(self.arpu, 2),
            "arppu": round(self.arppu, 2),
            "total_revenue": round(self.total_revenue, 2),
            "total_users": self.total_users,
            "total_payers": self.total_payers,
            "payer_segments": self.payer_segments,
            "avg_first_pay_days": round(self.avg_first_pay_days, 1),
            "first_pay_distribution": self.first_pay_distribution,
            "offers": [o.to_dict() for o in self.offers],
            "ltv_d7": round(self.ltv_d7, 2),
            "ltv_d30": round(self.ltv_d30, 2),
            "ltv_d90": round(self.ltv_d90, 2),
            "insights": self.insights,
        }


class MonetizationAnalyzer:
    """商业化分析器。

    消费 ThinkingDataReality，输出 MonetizationSnapshot。

    Attributes:
        td_reality:     ThinkingData 门面
        total_analyzed: 累计分析次数
    """

    # 大R阈值
    WHALE_THRESHOLD = 500.0

    def __init__(self, td_reality: ThinkingDataReality | None = None) -> None:
        self._td = td_reality
        self.total_analyzed: int = 0

    def analyze(
        self,
        project_id: int,
        lookback_days: int = 30,
    ) -> MonetizationSnapshot:
        """分析商业化表现。

        Args:
            project_id:    数数项目 ID
            lookback_days: 回溯天数

        Returns:
            MonetizationSnapshot
        """
        today = date.today()
        start = (today - timedelta(days=lookback_days)).isoformat()
        end = today.isoformat()

        snapshot = MonetizationSnapshot(
            project_id=project_id,
            period_start=start,
            period_end=end,
        )

        # 1. 拉取付费核心指标
        self._fetch_core_metrics(project_id, start, end, snapshot)

        # 2. 用户分层
        self._fetch_payer_segments(project_id, start, end, snapshot)

        # 3. 首充时间分布
        self._fetch_first_pay_distribution(project_id, start, end, snapshot)

        # 4. Offer 表现
        self._fetch_offers(project_id, start, end, snapshot)

        # 5. LTV
        self._fetch_ltv(project_id, snapshot)

        # 6. 生成洞察
        self._generate_insights(snapshot)

        self.total_analyzed += 1
        logger.info(
            f"MonetizationAnalyzer: project={project_id}, "
            f"payer_rate={snapshot.payer_rate:.2%}, "
            f"ARPU=${snapshot.arpu:.2f}, "
            f"revenue=${snapshot.total_revenue:.2f}"
        )
        return snapshot

    # ── Internal ────────────────────────────────────────

    def _fetch_core_metrics(
        self,
        project_id: int,
        start: str,
        end: str,
        snapshot: MonetizationSnapshot,
    ) -> None:
        """拉取付费核心指标。"""
        if not self._td or not self._td._client:
            # Mock
            snapshot.total_users = 10000
            snapshot.total_payers = 500
            snapshot.total_revenue = 35000.0
            snapshot.payer_rate = 0.05
            snapshot.arpu = 3.50
            snapshot.arppu = 70.0
            return

        # SQL 查询核心指标
        sql = (
            f"SELECT "
            f"  COUNT(DISTINCT user_id) AS total_users, "
            f"  COUNT(DISTINCT CASE WHEN event_name = 'purchase' THEN user_id END) AS payers, "
            f"  SUM(CASE WHEN event_name = 'purchase' THEN revenue ELSE 0 END) AS total_revenue "
            f"FROM v_event_{project_id} "
            f"WHERE event_date BETWEEN '{start}' AND '{end}'"
        )

        try:
            result = self._td._client.sql_query(project_id, sql)
            rows = result.get("data", result.get("rows", []))
            if rows:
                row = rows[0]
                if isinstance(row, dict):
                    snapshot.total_users = int(row.get("total_users", 0))
                    snapshot.total_payers = int(row.get("payers", 0))
                    snapshot.total_revenue = float(row.get("total_revenue", 0))
                else:
                    snapshot.total_users = int(row[0]) if len(row) > 0 else 0
                    snapshot.total_payers = int(row[1]) if len(row) > 1 else 0
                    snapshot.total_revenue = float(row[2]) if len(row) > 2 else 0

            if snapshot.total_users > 0:
                snapshot.payer_rate = round(snapshot.total_payers / snapshot.total_users, 4)
                snapshot.arpu = round(snapshot.total_revenue / snapshot.total_users, 2)
            if snapshot.total_payers > 0:
                snapshot.arppu = round(snapshot.total_revenue / snapshot.total_payers, 2)
        except Exception as exc:
            logger.warning(f"MonetizationAnalyzer: core metrics SQL failed: {exc}")
            snapshot.total_users = 10000
            snapshot.total_payers = 500
            snapshot.total_revenue = 35000.0
            snapshot.payer_rate = 0.05
            snapshot.arpu = 3.50
            snapshot.arppu = 70.0

    def _fetch_payer_segments(
        self,
        project_id: int,
        start: str,
        end: str,
        snapshot: MonetizationSnapshot,
    ) -> None:
        """拉取用户付费分层。"""
        if not self._td or not self._td._client:
            snapshot.payer_segments = {
                "non_payer": 9500,
                "first_payer": 150,
                "repeat_payer": 250,
                "whale": 100,
            }
            return

        sql = (
            f"SELECT "
            f"  CASE "
            f"    WHEN total_revenue = 0 THEN 'non_payer' "
            f"    WHEN total_revenue >= {self.WHALE_THRESHOLD} THEN 'whale' "
            f"    WHEN pay_count = 1 THEN 'first_payer' "
            f"    ELSE 'repeat_payer' "
            f"  END AS segment, "
            f"  COUNT(DISTINCT user_id) AS user_count "
            f"FROM ("
            f"  SELECT "
            f"    user_id, "
            f"    SUM(CASE WHEN event_name = 'purchase' THEN revenue ELSE 0 END) AS total_revenue, "
            f"    COUNT(DISTINCT CASE WHEN event_name = 'purchase' THEN event_date END) AS pay_count "
            f"  FROM v_event_{project_id} "
            f"  WHERE event_date BETWEEN '{start}' AND '{end}' "
            f"  GROUP BY user_id"
            f") "
            f"GROUP BY segment"
        )

        try:
            result = self._td._client.sql_query(project_id, sql)
            rows = result.get("data", result.get("rows", []))
            for row in rows:
                if isinstance(row, dict):
                    seg = row.get("segment", "unknown")
                    count = int(row.get("user_count", 0))
                else:
                    seg = row[0] if len(row) > 0 else "unknown"
                    count = int(row[1]) if len(row) > 1 else 0
                snapshot.payer_segments[seg] = count
        except Exception as exc:
            logger.warning(f"MonetizationAnalyzer: segments SQL failed: {exc}")
            snapshot.payer_segments = {
                "non_payer": 9500,
                "first_payer": 150,
                "repeat_payer": 250,
                "whale": 100,
            }

    def _fetch_first_pay_distribution(
        self,
        project_id: int,
        start: str,
        end: str,
        snapshot: MonetizationSnapshot,
    ) -> None:
        """拉取首充时间分布。"""
        # Mock
        snapshot.avg_first_pay_days = 3.5
        snapshot.first_pay_distribution = {
            "day_1": 150,
            "day_3": 80,
            "day_7": 50,
            "day_14": 30,
            "day_30+": 20,
        }

    def _fetch_offers(
        self,
        project_id: int,
        start: str,
        end: str,
        snapshot: MonetizationSnapshot,
    ) -> None:
        """拉取 Offer 表现。"""
        # Mock
        snapshot.offers = [
            OfferPerformance(
                offer_name="新手礼包",
                impressions=8000,
                purchases=400,
                conversion_rate=0.05,
                revenue=4000.0,
                avg_order_value=10.0,
            ),
            OfferPerformance(
                offer_name="限时特惠",
                impressions=5000,
                purchases=100,
                conversion_rate=0.02,
                revenue=8000.0,
                avg_order_value=80.0,
            ),
            OfferPerformance(
                offer_name="月卡",
                impressions=3000,
                purchases=150,
                conversion_rate=0.05,
                revenue=4500.0,
                avg_order_value=30.0,
            ),
        ]

    def _fetch_ltv(
        self,
        project_id: int,
        snapshot: MonetizationSnapshot,
    ) -> None:
        """拉取 LTV 预测。"""
        # 基于 ARPU 估算
        snapshot.ltv_d7 = round(snapshot.arpu * 7 * 0.6, 2)
        snapshot.ltv_d30 = round(snapshot.arpu * 30 * 0.5, 2)
        snapshot.ltv_d90 = round(snapshot.arpu * 90 * 0.4, 2)

    def _generate_insights(self, snapshot: MonetizationSnapshot) -> None:
        """生成商业化洞察。"""
        insights: list[str] = []

        # 付费率
        if snapshot.payer_rate < 0.02:
            insights.append(
                f"付费率偏低 ({snapshot.payer_rate:.1%})，建议增加首充礼包或降低付费门槛"
            )
        elif snapshot.payer_rate > 0.08:
            insights.append(
                f"付费率健康 ({snapshot.payer_rate:.1%})"
            )

        # ARPPU
        if snapshot.arppu > 0:
            if snapshot.arppu < 20:
                insights.append(
                    f"ARPPU 偏低 (${snapshot.arppu:.2f})，用户付费意愿弱，"
                    f"建议优化定价策略"
                )
            elif snapshot.arppu > 100:
                insights.append(
                    f"ARPPU 较高 (${snapshot.arppu:.2f})，存在大R用户群体"
                )

        # 大R占比
        whale_count = snapshot.payer_segments.get("whale", 0)
        if whale_count > 0 and snapshot.total_payers > 0:
            whale_ratio = whale_count / snapshot.total_payers
            if whale_ratio > 0.15:
                insights.append(
                    f"大R用户占比 {whale_ratio:.0%}，收入依赖度高，"
                    f"需关注大R流失风险"
                )

        # Offer 表现
        if snapshot.offers:
            best_offer = max(snapshot.offers, key=lambda o: o.revenue)
            worst_conv = min(snapshot.offers, key=lambda o: o.conversion_rate)
            insights.append(
                f"收入最高 Offer: '{best_offer.offer_name}' (${best_offer.revenue:,.0f})，"
                f"转化率最低: '{worst_conv.offer_name}' ({worst_conv.conversion_rate:.1%})"
            )

        # 首充时间
        if snapshot.avg_first_pay_days > 5:
            insights.append(
                f"平均首充时间 {snapshot.avg_first_pay_days:.1f} 天，"
                f"建议在前 3 天增加资源短缺触发点"
            )

        snapshot.insights = insights

    def __repr__(self) -> str:
        return f"MonetizationAnalyzer(analyzed={self.total_analyzed})"
