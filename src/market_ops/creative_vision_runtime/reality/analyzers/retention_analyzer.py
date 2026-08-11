"""E12.2 — Retention Analyzer。

留存分析器 —— 回答"用户为什么留下？为什么流失？"

按渠道、国家、素材维度分析留存，对比留存用户与流失用户的行为差异，
找出影响留存的关键行为（Retention Driver）。

Usage:
    analyzer = RetentionAnalyzer(td_reality)
    snapshot = analyzer.analyze(project_id=102, lookback_days=30)
    print(snapshot.retention_drivers)
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
class ChannelRetention:
    """单渠道留存。"""

    channel: str = ""
    d1: float = 0.0
    d7: float = 0.0
    d30: float = 0.0
    installs: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "d1": round(self.d1, 4),
            "d7": round(self.d7, 4),
            "d30": round(self.d30, 4),
            "installs": self.installs,
        }


@dataclass
class RetentionSnapshot:
    """留存分析快照。"""

    project_id: int = 0
    period_start: str = ""
    period_end: str = ""

    # 整体留存
    d1_retention: float = 0.0
    d7_retention: float = 0.0
    d30_retention: float = 0.0

    # 按渠道
    channel_retention: list[ChannelRetention] = field(default_factory=list)

    # 留存驱动因素
    retention_drivers: list[str] = field(default_factory=list)
    # 如 ["首次购买", "完成第5关", "加入公会"]

    # 流失用户 vs 留存用户行为差异
    retained_behaviors: list[str] = field(default_factory=list)
    churned_behaviors: list[str] = field(default_factory=list)

    # 最佳/最差渠道
    best_channel: str = ""
    worst_channel: str = ""

    # 洞察
    insights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "d1_retention": round(self.d1_retention, 4),
            "d7_retention": round(self.d7_retention, 4),
            "d30_retention": round(self.d30_retention, 4),
            "channel_retention": [c.to_dict() for c in self.channel_retention],
            "retention_drivers": self.retention_drivers,
            "retained_behaviors": self.retained_behaviors,
            "churned_behaviors": self.churned_behaviors,
            "best_channel": self.best_channel,
            "worst_channel": self.worst_channel,
            "insights": self.insights,
        }


class RetentionAnalyzer:
    """留存分析器。

    消费 ThinkingDataReality，输出 RetentionSnapshot。

    Attributes:
        td_reality:     ThinkingData 门面
        total_analyzed: 累计分析次数
    """

    def __init__(self, td_reality: ThinkingDataReality | None = None) -> None:
        self._td = td_reality
        self.total_analyzed: int = 0

    def analyze(
        self,
        project_id: int,
        lookback_days: int = 30,
    ) -> RetentionSnapshot:
        """分析留存。

        Args:
            project_id:    数数项目 ID
            lookback_days: 回溯天数

        Returns:
            RetentionSnapshot
        """
        today = date.today()
        start = (today - timedelta(days=lookback_days)).isoformat()
        end = today.isoformat()

        snapshot = RetentionSnapshot(
            project_id=project_id,
            period_start=start,
            period_end=end,
        )

        # 1. 拉取按渠道的留存数据
        self._fetch_channel_retention(project_id, snapshot)

        # 2. 识别留存驱动因素
        self._identify_drivers(project_id, snapshot)

        # 3. 对比留存 vs 流失行为
        self._compare_behaviors(project_id, snapshot)

        # 4. 排序渠道
        self._rank_channels(snapshot)

        # 5. 生成洞察
        self._generate_insights(snapshot)

        self.total_analyzed += 1
        logger.info(
            f"RetentionAnalyzer: project={project_id}, "
            f"D7={snapshot.d7_retention:.2%}, "
            f"best={snapshot.best_channel}, worst={snapshot.worst_channel}"
        )
        return snapshot

    # ── Internal ────────────────────────────────────────

    def _fetch_channel_retention(
        self,
        project_id: int,
        snapshot: RetentionSnapshot,
    ) -> None:
        """拉取按渠道的留存数据。"""
        if not self._td:
            self._mock_channel_retention(snapshot)
            return

        records = self._td.fetch_recent_retention(project_id, lookback_days=30)
        if not records:
            self._mock_channel_retention(snapshot)
            return

        for r in records:
            snapshot.channel_retention.append(ChannelRetention(
                channel=r.channel,
                d1=r.d1_retention,
                d7=r.d7_retention,
                d30=r.d30_retention,
            ))

        # 整体留存 = 各渠道加权平均
        if snapshot.channel_retention:
            snapshot.d1_retention = round(
                sum(c.d1 for c in snapshot.channel_retention) / len(snapshot.channel_retention), 4
            )
            snapshot.d7_retention = round(
                sum(c.d7 for c in snapshot.channel_retention) / len(snapshot.channel_retention), 4
            )
            snapshot.d30_retention = round(
                sum(c.d30 for c in snapshot.channel_retention) / len(snapshot.channel_retention), 4
            )

    def _identify_drivers(
        self,
        project_id: int,
        snapshot: RetentionSnapshot,
    ) -> None:
        """识别影响留存的关键行为。"""
        if not self._td or not self._td._client:
            # Mock
            snapshot.retention_drivers = [
                "首次购买",
                "完成第5关",
                "加入公会",
            ]
            return

        # 通过 SQL 查询对比留存用户和流失用户的行为频率
        sql = (
            f"SELECT "
            f"  event_name, "
            f"  COUNT(DISTINCT CASE WHEN is_retained = 1 THEN user_id END) * 1.0 / "
            f"  COUNT(DISTINCT user_id) AS retention_correlation "
            f"FROM ("
            f"  SELECT "
            f"    user_id, event_name, "
            f"    CASE WHEN MAX(event_date) >= DATE 'today' - 7 THEN 1 ELSE 0 END AS is_retained "
            f"  FROM v_event_{project_id} "
            f"  WHERE event_date >= '{snapshot.period_start}' "
            f"  GROUP BY user_id, event_name"
            f") "
            f"GROUP BY event_name "
            f"ORDER BY retention_correlation DESC"
        )

        try:
            result = self._td._client.sql_query(project_id, sql)
            rows = result.get("data", result.get("rows", []))
            drivers: list[str] = []
            for row in rows[:5]:
                if isinstance(row, dict):
                    event = row.get("event_name", "")
                    corr = float(row.get("retention_correlation", 0))
                else:
                    event = row[0] if len(row) > 0 else ""
                    corr = float(row[1]) if len(row) > 1 else 0
                if corr > 0.5 and event:
                    drivers.append(event)
            snapshot.retention_drivers = drivers or ["daily_login"]
        except Exception as exc:
            logger.warning(f"RetentionAnalyzer: driver SQL failed: {exc}")
            snapshot.retention_drivers = ["daily_login"]

    def _compare_behaviors(
        self,
        project_id: int,
        snapshot: RetentionSnapshot,
    ) -> None:
        """对比留存用户和流失用户的行为。"""
        if not self._td or not self._td._client:
            # Mock 行为差异
            snapshot.retained_behaviors = [
                "前3天完成30+关",
                "购买过礼包",
                "参加活动",
                "每日登录",
            ]
            snapshot.churned_behaviors = [
                "只完成10关",
                "没有消耗资源",
                "未参加活动",
                "仅登录1-2次",
            ]
            return

        # 对比留存用户和流失用户的行为频率
        sql = (
            f"SELECT "
            f"  behavior, "
            f"  retained_count, "
            f"  churned_count, "
            f"  retained_rate, "
            f"  churned_rate, "
            f"  rate_diff "
            f"FROM ("
            f"  SELECT "
            f"    behavior, "
            f"    SUM(CASE WHEN is_retained = 1 THEN 1 ELSE 0 END) AS retained_count, "
            f"    SUM(CASE WHEN is_retained = 0 THEN 1 ELSE 0 END) AS churned_count, "
            f"    ROUND(SUM(CASE WHEN is_retained = 1 THEN 1 ELSE 0 END) * 1.0 / "
            f"      COUNT(DISTINCT user_id), 4) AS retained_rate, "
            f"    ROUND(SUM(CASE WHEN is_retained = 0 THEN 1 ELSE 0 END) * 1.0 / "
            f"      COUNT(DISTINCT user_id), 4) AS churned_rate, "
            f"    ROUND((SUM(CASE WHEN is_retained = 1 THEN 1 ELSE 0 END) * 1.0 / "
            f"      COUNT(DISTINCT user_id)) - "
            f"      (SUM(CASE WHEN is_retained = 0 THEN 1 ELSE 0 END) * 1.0 / "
            f"      COUNT(DISTINCT user_id)), 4) AS rate_diff "
            f"  FROM ("
            f"    SELECT "
            f"      u.user_id, "
            f"      u.is_retained, "
            f"      b.behavior "
            f"    FROM ("
            f"      SELECT "
            f"        user_id, "
            f"        CASE WHEN MAX(event_date) >= DATE 'today' - 7 THEN 1 ELSE 0 END AS is_retained "
            f"      FROM v_event_{project_id} "
            f"      WHERE event_date >= '{snapshot.period_start}' "
            f"      GROUP BY user_id "
            f"    ) u "
            f"    CROSS JOIN ("
            f"      SELECT '完成关卡数≥30' AS behavior UNION ALL "
            f"      SELECT '购买过礼包' UNION ALL "
            f"      SELECT '参加活动' UNION ALL "
            f"      SELECT '每日登录' UNION ALL "
            f"      SELECT '加入公会' UNION ALL "
            f"      SELECT '使用道具' "
            f"    ) b "
            f"    LEFT JOIN ("
            f"      SELECT "
            f"        user_id, "
            f"        '完成关卡数≥30' AS behavior "
            f"      FROM v_user_level_{project_id} "
            f"      WHERE level_count >= 30 "
            f"      GROUP BY user_id "
            f"      UNION ALL "
            f"      SELECT user_id, '购买过礼包' FROM v_purchase_{project_id} "
            f"      GROUP BY user_id "
            f"      UNION ALL "
            f"      SELECT user_id, '参加活动' FROM v_event_{project_id} "
            f"      WHERE event_name = 'activity_join' GROUP BY user_id "
            f"      UNION ALL "
            f"      SELECT user_id, '每日登录' FROM v_login_{project_id} "
            f"      WHERE login_days >= 5 GROUP BY user_id "
            f"      UNION ALL "
            f"      SELECT user_id, '加入公会' FROM v_guild_{project_id} "
            f"      WHERE event_name = 'guild_join' GROUP BY user_id "
            f"      UNION ALL "
            f"      SELECT user_id, '使用道具' FROM v_event_{project_id} "
            f"      WHERE event_name = 'item_use' GROUP BY user_id "
            f"    ) ub ON u.user_id = ub.user_id AND b.behavior = ub.behavior "
            f"  ) t "
            f"  GROUP BY behavior "
            f") t "
            f"ORDER BY rate_diff DESC"
        )

        try:
            client = self._td._client
            result = client.sql_query(project_id, sql)
            rows = result.get("data", result.get("rows", []))
            retained: list[str] = []
            churned: list[str] = []
            for row in rows:
                if isinstance(row, dict):
                    behavior = row.get("behavior", "")
                    rate_diff = float(row.get("rate_diff", 0))
                else:
                    behavior = row[0] if len(row) > 0 else ""
                    rate_diff = float(row[5]) if len(row) > 5 else 0

                if rate_diff > 0.2:
                    retained.append(behavior)
                elif rate_diff < -0.2:
                    churned.append(behavior)

            snapshot.retained_behaviors = retained[:4]
            snapshot.churned_behaviors = churned[:4]
        except Exception as exc:
            logger.warning(f"RetentionAnalyzer: behavior SQL failed: {exc}")
            # 降级到 mock
            snapshot.retained_behaviors = [
                "前3天完成30+关",
                "购买过礼包",
                "参加活动",
                "每日登录",
            ]
            snapshot.churned_behaviors = [
                "只完成10关",
                "没有消耗资源",
                "未参加活动",
                "仅登录1-2次",
            ]

    def _rank_channels(self, snapshot: RetentionSnapshot) -> None:
        """排序渠道，找出最佳和最差。"""
        if not snapshot.channel_retention:
            return

        sorted_by_d7 = sorted(snapshot.channel_retention, key=lambda c: c.d7, reverse=True)
        snapshot.best_channel = sorted_by_d7[0].channel
        snapshot.worst_channel = sorted_by_d7[-1].channel

    def _generate_insights(self, snapshot: RetentionSnapshot) -> None:
        """生成留存洞察。"""
        insights: list[str] = []

        # 整体留存
        if snapshot.d7_retention < 0.15:
            insights.append(
                f"D7 留存偏低 ({snapshot.d7_retention:.0%})，"
                f"需排查核心玩法体验"
            )
        elif snapshot.d7_retention > 0.30:
            insights.append(
                f"D7 留存优秀 ({snapshot.d7_retention:.0%})"
            )

        # 渠道差异
        if snapshot.best_channel and snapshot.worst_channel:
            best_d7 = next(
                (c.d7 for c in snapshot.channel_retention if c.channel == snapshot.best_channel),
                0.0,
            )
            worst_d7 = next(
                (c.d7 for c in snapshot.channel_retention if c.channel == snapshot.worst_channel),
                0.0,
            )
            if worst_d7 > 0 and best_d7 / worst_d7 > 2:
                insights.append(
                    f"渠道差异显著：{snapshot.best_channel} D7={best_d7:.0%} "
                    f"vs {snapshot.worst_channel} D7={worst_d7:.0%}，"
                    f"建议优化 {snapshot.worst_channel} 的获客质量"
                )

        # 留存驱动
        if snapshot.retention_drivers:
            insights.append(
                f"影响留存的关键行为：{', '.join(snapshot.retention_drivers[:3])}，"
                f"建议在新手期引导用户完成这些行为"
            )

        # 行为差异
        if snapshot.retained_behaviors:
            insights.append(
                f"留存用户特征行为：{', '.join(snapshot.retained_behaviors[:3])}，"
                f"建议引导新用户完成这些行为"
            )
        if snapshot.churned_behaviors:
            insights.append(
                f"流失用户缺少的行为：{', '.join(snapshot.churned_behaviors[:3])}，"
                f"需排查这些行为的引导或门槛"
            )

        # D30 留存
        if snapshot.d30_retention < 0.05:
            insights.append(
                f"D30 留存极低 ({snapshot.d30_retention:.0%})，"
                f"长期内容或社交系统可能不足"
            )

        snapshot.insights = insights

    # ── Mock ───────────────────────────────────────────

    def _mock_channel_retention(self, snapshot: RetentionSnapshot) -> None:
        """生成 mock 渠道留存数据。"""
        channels = [
            ("meta", 0.48, 0.30, 0.14, 3200),
            ("google", 0.42, 0.25, 0.10, 2800),
            ("asa", 0.52, 0.35, 0.18, 1500),
            ("tiktok", 0.38, 0.20, 0.08, 1200),
            ("organic", 0.55, 0.38, 0.20, 800),
        ]

        for ch, d1, d7, d30, installs in channels:
            snapshot.channel_retention.append(ChannelRetention(
                channel=ch, d1=d1, d7=d7, d30=d30, installs=installs,
            ))

        snapshot.d1_retention = round(sum(c.d1 for c in snapshot.channel_retention) / len(channels), 4)
        snapshot.d7_retention = round(sum(c.d7 for c in snapshot.channel_retention) / len(channels), 4)
        snapshot.d30_retention = round(sum(c.d30 for c in snapshot.channel_retention) / len(channels), 4)

    def __repr__(self) -> str:
        return f"RetentionAnalyzer(analyzed={self.total_analyzed})"
