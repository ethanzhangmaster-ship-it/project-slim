"""E12.2 — User Value Analyzer。

用户价值分析器 —— 回答"用户对产品的价值是多少？价值结构健康吗？谁在上升谁在下降？"

与 MonetizationAnalyzer 互补：商业化分析器聚焦纯付费维度（付费率/ARPU/LTV/首充），
本分析器采用多维度综合价值视角，衡量用户对产品的整体贡献。

核心逻辑：
  综合价值评分（value_score）= 加权融合四维度
    - revenue（付费价值）       权重 0.40
    - engagement（活跃价值）    权重 0.30
    - social（社交价值）         权重 0.15
    - content（内容贡献价值）    权重 0.15

  价值分层（segment）
    - high_value    value_score ≥ HIGH_VALUE_THRESHOLD
    - mid_value     MID_VALUE_THRESHOLD ≤ score < HIGH_VALUE_THRESHOLD
    - low_value     LOW_VALUE_THRESHOLD ≤ score < MID_VALUE_THRESHOLD
    - churn_risk    score < LOW_VALUE_THRESHOLD

  价值集中度
    - 帕累托比 Pareto Ratio：Top 20% 用户贡献的价值占比
    - 集中度指数 Concentration Index：0(完全平均) ~ 1(完全集中)
    - 结构评价 value_structure：
        top_heavy    集中度 ≥ TOP_HEAVY_THRESHOLD（头重脚轻，依赖少数大R）
        bottom_heavy 集中度 ≤ BOTTOM_HEAVY_THRESHOLD（价值过于分散）
        healthy      其他

  价值演进
    - rising_stars          本期价值评分较上期上升 ≥ RISING_THRESHOLD
    - declining_users       本期价值评分较上期下降 ≥ DECLINING_THRESHOLD
    - new_high_value        新晋高价值用户（上期非高价值，本期高价值）
    - churned_high_value    流失高价值用户（上期高价值，本期非高价值）

Usage:
    analyzer = UserValueAnalyzer(td_reality)
    snapshot = analyzer.analyze(project_id=102, lookback_days=30)
    print(snapshot.high_value_users, snapshot.pareto_ratio)
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
class UserSegment:
    """单个用户价值分层的统计。

    Attributes:
        segment_name:      分层名称（high_value / mid_value / low_value / churn_risk）
        user_count:        该层用户数
        user_share:        占总用户比例
        avg_value_score:   平均价值评分
        avg_revenue:       平均付费金额
        avg_active_days:   平均活跃天数
        avg_sessions:      平均会话数
    """

    segment_name: str = ""
    user_count: int = 0
    user_share: float = 0.0
    avg_value_score: float = 0.0
    avg_revenue: float = 0.0
    avg_active_days: float = 0.0
    avg_sessions: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_name": self.segment_name,
            "user_count": self.user_count,
            "user_share": round(self.user_share, 4),
            "avg_value_score": round(self.avg_value_score, 2),
            "avg_revenue": round(self.avg_revenue, 2),
            "avg_active_days": round(self.avg_active_days, 2),
            "avg_sessions": round(self.avg_sessions, 2),
        }


@dataclass
class ValueContribution:
    """单个价值维度的贡献统计。

    Attributes:
        dimension:          维度名（revenue / engagement / social / content）
        total_contribution: 该维度总贡献值
        share:              占总价值比例
        top_users:          该维度高贡献用户数
    """

    dimension: str = ""
    total_contribution: float = 0.0
    share: float = 0.0
    top_users: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "total_contribution": round(self.total_contribution, 2),
            "share": round(self.share, 4),
            "top_users": self.top_users,
        }


@dataclass
class UserValueSnapshot:
    """用户价值分析快照。

    Attributes:
        project_id:          数数项目 ID
        period_start:        分析周期开始
        period_end:          分析周期结束
        total_users:         总用户数
        avg_value_score:     全体用户平均价值评分
        segments:            各价值分层统计
        high_value_users:    高价值用户数
        mid_value_users:     中价值用户数
        low_value_users:     低价值用户数
        churn_risk_users:    流失风险用户数
        value_composition:   价值构成（多维度贡献）
        rising_stars:        价值上升用户数
        declining_users:     价值下降用户数
        new_high_value:      新晋高价值用户数
        churned_high_value:  流失高价值用户数
        pareto_ratio:        帕累托比（Top 20% 用户贡献价值占比）
        concentration_index: 集中度指数（0~1）
        value_structure:     价值结构评价（healthy / top_heavy / bottom_heavy / fragmented）
        insights:            洞察列表
    """

    project_id: int = 0
    period_start: str = ""
    period_end: str = ""

    total_users: int = 0
    avg_value_score: float = 0.0

    # 价值分层
    segments: list[UserSegment] = field(default_factory=list)
    high_value_users: int = 0
    mid_value_users: int = 0
    low_value_users: int = 0
    churn_risk_users: int = 0

    # 价值构成（多维度）
    value_composition: list[ValueContribution] = field(default_factory=list)

    # 价值演进
    rising_stars: int = 0
    declining_users: int = 0
    new_high_value: int = 0
    churned_high_value: int = 0

    # 价值集中度
    pareto_ratio: float = 0.0
    concentration_index: float = 0.0
    value_structure: str = "healthy"

    # 洞察
    insights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "total_users": self.total_users,
            "avg_value_score": round(self.avg_value_score, 2),
            "segments": [s.to_dict() for s in self.segments],
            "high_value_users": self.high_value_users,
            "mid_value_users": self.mid_value_users,
            "low_value_users": self.low_value_users,
            "churn_risk_users": self.churn_risk_users,
            "value_composition": [c.to_dict() for c in self.value_composition],
            "rising_stars": self.rising_stars,
            "declining_users": self.declining_users,
            "new_high_value": self.new_high_value,
            "churned_high_value": self.churned_high_value,
            "pareto_ratio": round(self.pareto_ratio, 4),
            "concentration_index": round(self.concentration_index, 4),
            "value_structure": self.value_structure,
            "insights": self.insights,
        }


class UserValueAnalyzer:
    """用户价值分析器。

    消费 ThinkingDataReality，输出 UserValueSnapshot。

    Attributes:
        td_reality:     ThinkingData 门面
        total_analyzed: 累计分析次数
    """

    # 价值评分维度权重
    WEIGHT_REVENUE = 0.40
    WEIGHT_ENGAGEMENT = 0.30
    WEIGHT_SOCIAL = 0.15
    WEIGHT_CONTENT = 0.15

    # 价值分层阈值（综合价值评分 0~100）
    HIGH_VALUE_THRESHOLD = 70.0
    MID_VALUE_THRESHOLD = 40.0
    LOW_VALUE_THRESHOLD = 15.0

    # 价值演进阈值（评分变化幅度）
    RISING_THRESHOLD = 10.0    # 上升 ≥ 10 分 → rising_star
    DECLINING_THRESHOLD = 10.0  # 下降 ≥ 10 分 → declining

    # 价值集中度阈值
    TOP_HEAVY_THRESHOLD = 0.85      # Top 20% 用户贡献 ≥ 85% 价值 → top_heavy
    BOTTOM_HEAVY_THRESHOLD = 0.50   # Top 20% 用户贡献 ≤ 50% 价值 → bottom_heavy

    def __init__(self, td_reality: ThinkingDataReality | None = None) -> None:
        self._td = td_reality
        self.total_analyzed: int = 0

    def analyze(
        self,
        project_id: int,
        lookback_days: int = 30,
    ) -> UserValueSnapshot:
        """分析用户价值。

        Args:
            project_id:    数数项目 ID
            lookback_days: 回溯天数

        Returns:
            UserValueSnapshot
        """
        today = date.today()
        start = (today - timedelta(days=lookback_days)).isoformat()
        end = today.isoformat()

        snapshot = UserValueSnapshot(
            project_id=project_id,
            period_start=start,
            period_end=end,
        )

        # 1. 拉取用户价值评分与分层
        self._fetch_user_segments(project_id, start, end, snapshot)

        # 2. 价值构成（多维度贡献）
        self._fetch_value_composition(project_id, start, end, snapshot)

        # 3. 价值演进
        self._fetch_value_evolution(project_id, start, end, snapshot)

        # 4. 价值集中度
        self._compute_concentration(snapshot)

        # 5. 评价价值结构
        self._evaluate_value_structure(snapshot)

        # 6. 生成洞察
        self._generate_insights(snapshot)

        self.total_analyzed += 1
        logger.info(
            f"UserValueAnalyzer: project={project_id}, "
            f"total_users={snapshot.total_users}, "
            f"high_value={snapshot.high_value_users}, "
            f"structure={snapshot.value_structure}, "
            f"pareto={snapshot.pareto_ratio:.2%}"
        )
        return snapshot

    # ── Internal ────────────────────────────────────────

    def _fetch_user_segments(
        self,
        project_id: int,
        start: str,
        end: str,
        snapshot: UserValueSnapshot,
    ) -> None:
        """拉取用户价值评分并分层（SQL 层 GROUP BY + CASE WHEN 聚合）。"""
        if not self._td or not self._td._client:
            self._mock_user_segments(snapshot)
            return

        # 在 SQL 层完成加权评分计算 + 分层聚合，仅返回 4 行
        sql = (
            f"SELECT "
            f"  CASE "
            f"    WHEN value_score >= {self.HIGH_VALUE_THRESHOLD} THEN 'high_value' "
            f"    WHEN value_score >= {self.MID_VALUE_THRESHOLD} THEN 'mid_value' "
            f"    WHEN value_score >= {self.LOW_VALUE_THRESHOLD} THEN 'low_value' "
            f"    ELSE 'churn_risk' "
            f"  END AS segment, "
            f"  COUNT(*) AS user_count, "
            f"  ROUND(AVG(value_score), 2) AS avg_score, "
            f"  ROUND(AVG(total_revenue), 2) AS avg_revenue, "
            f"  ROUND(AVG(active_days), 2) AS avg_active_days, "
            f"  ROUND(AVG(sessions), 2) AS avg_sessions "
            f"FROM ( "
            f"  SELECT "
            f"    user_id, "
            f"    {self.WEIGHT_REVENUE} * revenue_score "
            f"      + {self.WEIGHT_ENGAGEMENT} * engagement_score "
            f"      + {self.WEIGHT_SOCIAL} * social_score "
            f"      + {self.WEIGHT_CONTENT} * content_score AS value_score, "
            f"    total_revenue, active_days, sessions "
            f"  FROM v_user_value_{project_id} "
            f"  WHERE period_end = '{end}' "
            f") t "
            f"GROUP BY segment "
            f"ORDER BY "
            f"  CASE segment "
            f"    WHEN 'high_value' THEN 1 "
            f"    WHEN 'mid_value' THEN 2 "
            f"    WHEN 'low_value' THEN 3 "
            f"    ELSE 4 "
            f"  END"
        )

        try:
            client = self._td._client
            result = client.sql_query(project_id, sql)
            rows = result.get("data", result.get("rows", []))
            self._build_segments_from_sql(rows, snapshot)
        except Exception as exc:
            logger.warning(f"UserValueAnalyzer: segments SQL failed: {exc}")
            self._mock_user_segments(snapshot)

    def _fetch_value_composition(
        self,
        project_id: int,
        start: str,
        end: str,
        snapshot: UserValueSnapshot,
    ) -> None:
        """拉取各价值维度的贡献。"""
        if not self._td or not self._td._client:
            self._mock_value_composition(snapshot)
            return

        sql = (
            f"SELECT "
            f"  'revenue' AS dim, SUM(revenue_score) AS total, "
            f"  COUNT(CASE WHEN revenue_score >= 70 THEN 1 END) AS top "
            f"FROM v_user_value_{project_id} WHERE period_end = '{end}' "
            f"UNION ALL "
            f"SELECT 'engagement', SUM(engagement_score), "
            f"  COUNT(CASE WHEN engagement_score >= 70 THEN 1 END) "
            f"FROM v_user_value_{project_id} WHERE period_end = '{end}' "
            f"UNION ALL "
            f"SELECT 'social', SUM(social_score), "
            f"  COUNT(CASE WHEN social_score >= 70 THEN 1 END) "
            f"FROM v_user_value_{project_id} WHERE period_end = '{end}' "
            f"UNION ALL "
            f"SELECT 'content', SUM(content_score), "
            f"  COUNT(CASE WHEN content_score >= 70 THEN 1 END) "
            f"FROM v_user_value_{project_id} WHERE period_end = '{end}'"
        )

        try:
            client = self._td._client
            result = client.sql_query(project_id, sql)
            rows = result.get("data", result.get("rows", []))

            contributions: list[ValueContribution] = []
            grand_total = 0.0
            for row in rows:
                if isinstance(row, dict):
                    dim = row.get("dim", "")
                    total = float(row.get("total", 0))
                    top = int(row.get("top", 0))
                else:
                    dim = row[0] if len(row) > 0 else ""
                    total = float(row[1]) if len(row) > 1 else 0
                    top = int(row[2]) if len(row) > 2 else 0
                contributions.append(
                    ValueContribution(
                        dimension=dim,
                        total_contribution=total,
                        top_users=top,
                    )
                )
                grand_total += total

            for c in contributions:
                c.share = (
                    round(c.total_contribution / grand_total, 4)
                    if grand_total > 0
                    else 0.0
                )
            snapshot.value_composition = contributions
        except Exception as exc:
            logger.warning(f"UserValueAnalyzer: composition SQL failed: {exc}")
            self._mock_value_composition(snapshot)

    def _fetch_value_evolution(
        self,
        project_id: int,
        start: str,
        end: str,
        snapshot: UserValueSnapshot,
    ) -> None:
        """拉取用户价值演进（对比上期）。"""
        if not self._td or not self._td._client:
            self._mock_value_evolution(snapshot)
            return

        # 对比本期与上期价值评分变化
        sql = (
            f"SELECT "
            f"  SUM(CASE WHEN curr - prev >= {self.RISING_THRESHOLD} THEN 1 ELSE 0 END) AS rising, "
            f"  SUM(CASE WHEN prev - curr >= {self.DECLINING_THRESHOLD} THEN 1 ELSE 0 END) AS declining, "
            f"  SUM(CASE WHEN prev < {self.HIGH_VALUE_THRESHOLD} "
            f"    AND curr >= {self.HIGH_VALUE_THRESHOLD} THEN 1 ELSE 0 END) AS new_high, "
            f"  SUM(CASE WHEN prev >= {self.HIGH_VALUE_THRESHOLD} "
            f"    AND curr < {self.HIGH_VALUE_THRESHOLD} THEN 1 ELSE 0 END) AS churned_high "
            f"FROM ( "
            f"  SELECT user_id, "
            f"    revenue_score + engagement_score + social_score + content_score AS curr, "
            f"    LAG(revenue_score + engagement_score + social_score + content_score) "
            f"      OVER (PARTITION BY user_id ORDER BY period_end) AS prev "
            f"  FROM v_user_value_{project_id} "
            f") t WHERE prev IS NOT NULL"
        )

        try:
            client = self._td._client
            result = client.sql_query(project_id, sql)
            rows = result.get("data", result.get("rows", []))
            if rows:
                row = rows[0]
                if isinstance(row, dict):
                    snapshot.rising_stars = int(row.get("rising", 0))
                    snapshot.declining_users = int(row.get("declining", 0))
                    snapshot.new_high_value = int(row.get("new_high", 0))
                    snapshot.churned_high_value = int(row.get("churned_high", 0))
                else:
                    snapshot.rising_stars = int(row[0]) if len(row) > 0 else 0
                    snapshot.declining_users = int(row[1]) if len(row) > 1 else 0
                    snapshot.new_high_value = int(row[2]) if len(row) > 2 else 0
                    snapshot.churned_high_value = int(row[3]) if len(row) > 3 else 0
        except Exception as exc:
            logger.warning(f"UserValueAnalyzer: evolution SQL failed: {exc}")
            self._mock_value_evolution(snapshot)

    def _compute_concentration(self, snapshot: UserValueSnapshot) -> None:
        """计算价值集中度。

        帕累托比：Top 20% 用户贡献的价值占总价值的比例。
        集中度指数：基于分层加权计算的简化基尼系数（0~1）。
        """
        if not snapshot.segments or snapshot.total_users == 0:
            return

        # 基于分层贡献近似计算帕累托比
        # 高价值用户通常占约 20%（mock 中 1200/10000 = 12%，需结合 mid 高端）
        high = next(
            (s for s in snapshot.segments if s.segment_name == "high_value"),
            None,
        )
        mid = next(
            (s for s in snapshot.segments if s.segment_name == "mid_value"),
            None,
        )

        high_value_total = (
            high.avg_value_score * high.user_count if high else 0
        )
        grand_total = sum(
            s.avg_value_score * s.user_count for s in snapshot.segments
        )

        if grand_total <= 0:
            return

        # Top 20% 用户价值占比：高价值用户全部 + 中价值用户的部分
        top20_count = int(snapshot.total_users * 0.20)
        if high and high.user_count >= top20_count:
            # Top 20% 全部落在高价值层
            snapshot.pareto_ratio = round(
                (high.avg_value_score * top20_count) / grand_total, 4
            )
        else:
            # Top 20% = 高价值全部 + 中价值补足
            high_share = high_value_total / grand_total if high_value_total else 0
            remaining = top20_count - (high.user_count if high else 0)
            mid_contribution = 0.0
            if mid and mid.user_count > 0 and remaining > 0:
                mid_contribution = (
                    mid.avg_value_score * min(remaining, mid.user_count)
                ) / grand_total
            snapshot.pareto_ratio = round(high_share + mid_contribution, 4)

        # 集中度指数：简化基尼系数
        # 用各层价值占比与用户占比的差异累加
        snapshot.concentration_index = round(
            self._simplified_gini(snapshot.segments, grand_total), 4
        )

    def _evaluate_value_structure(self, snapshot: UserValueSnapshot) -> None:
        """评价价值结构。"""
        if snapshot.total_users == 0:
            return

        # top_heavy:    Top 20% 贡献 ≥ 85%
        # bottom_heavy: Top 20% 贡献 ≤ 50%（价值过于分散）
        # fragmented:   高价值用户占比 < 5% 且低价值 + 流失风险占比 > 70%
        high_share = snapshot.high_value_users / snapshot.total_users
        low_churn_share = (
            snapshot.low_value_users + snapshot.churn_risk_users
        ) / snapshot.total_users

        if snapshot.pareto_ratio >= self.TOP_HEAVY_THRESHOLD:
            snapshot.value_structure = "top_heavy"
        elif snapshot.pareto_ratio <= self.BOTTOM_HEAVY_THRESHOLD:
            snapshot.value_structure = "bottom_heavy"
        elif high_share < 0.05 and low_churn_share > 0.70:
            snapshot.value_structure = "fragmented"
        else:
            snapshot.value_structure = "healthy"

    def _generate_insights(self, snapshot: UserValueSnapshot) -> None:
        """生成用户价值洞察。"""
        insights: list[str] = []

        # 价值结构
        if snapshot.value_structure == "top_heavy":
            insights.append(
                f"价值结构头重脚轻（Top 20% 用户贡献 {snapshot.pareto_ratio:.0%} 价值），"
                f"过度依赖少数高价值用户，建议扩大中价值用户基本盘"
            )
        elif snapshot.value_structure == "bottom_heavy":
            insights.append(
                f"价值过于分散（Top 20% 用户仅贡献 {snapshot.pareto_ratio:.0%}），"
                f"缺乏高价值用户拉动，建议设计高价值转化路径"
            )
        elif snapshot.value_structure == "fragmented":
            insights.append(
                f"高价值用户稀少（{snapshot.high_value_users} 人），"
                f"低价值/流失风险用户占比过高，建议加强留存与价值提升"
            )
        else:
            insights.append(
                f"价值结构健康（Top 20% 贡献 {snapshot.pareto_ratio:.0%}，"
                f"高价值用户 {snapshot.high_value_users} 人）"
            )

        # 价值构成
        if snapshot.value_composition:
            # 找出占比最高和最低的维度
            sorted_dims = sorted(
                snapshot.value_composition, key=lambda c: c.share, reverse=True
            )
            top_dim = sorted_dims[0]
            bottom_dim = sorted_dims[-1]
            insights.append(
                f"价值主要由 '{top_dim.dimension}' 贡献（占比 {top_dim.share:.0%}），"
                f"'{bottom_dim.dimension}' 贡献最低（占比 {bottom_dim.share:.0%}）"
            )

            # 单维度依赖告警
            if top_dim.share > 0.70:
                insights.append(
                    f"价值过度依赖 '{top_dim.dimension}' 维度（{top_dim.share:.0%}），"
                    f"建议多元化价值来源以降低风险"
                )

        # 价值演进
        if snapshot.rising_stars > 0:
            insights.append(
                f"{snapshot.rising_stars} 个用户价值上升（潜力用户），"
                f"建议重点培育向高价值转化"
            )
        if snapshot.declining_users > 0:
            insights.append(
                f"{snapshot.declining_users} 个用户价值下降，"
                f"建议触发召回或价值挽回策略"
            )
        if snapshot.new_high_value > 0:
            insights.append(
                f"{snapshot.new_high_value} 个新晋高价值用户，"
                f"建议加强关怀以稳固其价值层级"
            )
        if snapshot.churned_high_value > 0:
            insights.append(
                f"{snapshot.churned_high_value} 个高价值用户流失，"
                f"建议优先召回（高价值流失成本高）"
            )

        # 流失风险
        if snapshot.churn_risk_users > 0:
            churn_risk_share = (
                snapshot.churn_risk_users / snapshot.total_users
                if snapshot.total_users > 0
                else 0
            )
            if churn_risk_share > 0.30:
                insights.append(
                    f"流失风险用户占比 {churn_risk_share:.0%}"
                    f"（{snapshot.churn_risk_users} 人），"
                    f"比例过高，建议立即启动留存策略"
                )

        snapshot.insights = insights

    # ── Helpers ────────────────────────────────────────

    def _compute_value_score(
        self,
        revenue_score: float,
        engagement_score: float,
        social_score: float,
        content_score: float,
    ) -> float:
        """计算综合价值评分（0~100）。

        各维度评分均为 0~100，按权重加权融合。
        """
        score = (
            self.WEIGHT_REVENUE * revenue_score
            + self.WEIGHT_ENGAGEMENT * engagement_score
            + self.WEIGHT_SOCIAL * social_score
            + self.WEIGHT_CONTENT * content_score
        )
        return round(score, 2)

    def _segment_name(self, score: float) -> str:
        """根据价值评分判定分层。"""
        if score >= self.HIGH_VALUE_THRESHOLD:
            return "high_value"
        if score >= self.MID_VALUE_THRESHOLD:
            return "mid_value"
        if score >= self.LOW_VALUE_THRESHOLD:
            return "low_value"
        return "churn_risk"

    def _build_segments_from_sql(
        self,
        rows: list[dict[str, Any] | list[Any]],
        snapshot: UserValueSnapshot,
    ) -> None:
        """从 SQL 聚合结果直接构建 UserSegment 列表。

        SQL 已返回 4 行聚合数据（每行一个分段），无需逐行分桶。
        处理缺失分段（某段无用户时补空 UserSegment）。
        """
        order = ["high_value", "mid_value", "low_value", "churn_risk"]

        # 解析 SQL 结果 → {segment_name: row_data}
        row_map: dict[str, dict[str, Any]] = {}
        for row in rows:
            if isinstance(row, dict):
                seg = row.get("segment", "")
                row_map[seg] = row
            else:
                seg = row[0] if len(row) > 0 else ""
                row_map[seg] = {
                    "segment": seg,
                    "user_count": int(row[1]) if len(row) > 1 else 0,
                    "avg_score": float(row[2]) if len(row) > 2 else 0.0,
                    "avg_revenue": float(row[3]) if len(row) > 3 else 0.0,
                    "avg_active_days": float(row[4]) if len(row) > 4 else 0.0,
                    "avg_sessions": float(row[5]) if len(row) > 5 else 0.0,
                }

        total_users = 0
        total_weighted_score = 0.0

        for name in order:
            row = row_map.get(name)
            if row:
                count = int(row.get("user_count", 0))
                avg_score = float(row.get("avg_score", 0.0))
                avg_revenue = float(row.get("avg_revenue", 0.0))
                avg_days = float(row.get("avg_active_days", 0.0))
                avg_sessions = float(row.get("avg_sessions", 0.0))
            else:
                count = 0
                avg_score = 0.0
                avg_revenue = 0.0
                avg_days = 0.0
                avg_sessions = 0.0

            total_users += count
            total_weighted_score += avg_score * count

            seg = UserSegment(
                segment_name=name,
                user_count=count,
                user_share=0.0,  # 后续统一计算
                avg_value_score=avg_score,
                avg_revenue=avg_revenue,
                avg_active_days=avg_days,
                avg_sessions=avg_sessions,
            )
            snapshot.segments.append(seg)

            # 设置各分层计数器
            if name == "high_value":
                snapshot.high_value_users = count
            elif name == "mid_value":
                snapshot.mid_value_users = count
            elif name == "low_value":
                snapshot.low_value_users = count
            elif name == "churn_risk":
                snapshot.churn_risk_users = count

        # 统一计算 user_share 和整体 avg_value_score
        snapshot.total_users = total_users
        if total_users > 0:
            for seg in snapshot.segments:
                seg.user_share = round(seg.user_count / total_users, 4)
            snapshot.avg_value_score = round(
                total_weighted_score / total_users, 2
            )

    def _simplified_gini(
        self,
        segments: list[UserSegment],
        grand_total: float,
    ) -> float:
        """简化基尼系数计算。

        基于分层（而非个体）的近似：
          按价值评分升序排列各层，累加 (累积用户占比 - 累积价值占比) 的绝对差。
        """
        if not segments or grand_total <= 0:
            return 0.0

        sorted_segs = sorted(segments, key=lambda s: s.avg_value_score)
        total_users = sum(s.user_count for s in sorted_segs)
        if total_users == 0:
            return 0.0

        cum_user = 0.0
        cum_value = 0.0
        area = 0.0
        for seg in sorted_segs:
            user_share = seg.user_count / total_users
            value_share = (
                seg.avg_value_score * seg.user_count / grand_total
            )
            cum_user += user_share
            cum_value += value_share
            area += abs(cum_user - cum_value)

        # 归一化到 0~1
        return round(area / len(sorted_segs), 4)

    # ── Mock ───────────────────────────────────────────

    def _mock_user_segments(self, snapshot: UserValueSnapshot) -> None:
        """生成 mock 用户价值分层数据。

        10000 用户分布：
          - high_value   1800 人（18%）  价值评分 95  （核心付费+活跃用户）
          - mid_value    2200 人（22%）  价值评分 45  （稳定活跃用户）
          - low_value    4000 人（40%）  价值评分 18  （轻度用户）
          - churn_risk   2000 人（20%）  价值评分 5   （流失风险用户）
        平均价值评分 ≈ 35.2
        帕累托比 ≈ 0.51（Top 20% 贡献约 51% 价值）→ healthy 结构
        """
        mock_segments = [
            ("high_value", 1800, 95.0, 200.0, 27.0, 220.0),
            ("mid_value", 2200, 45.0, 30.0, 16.0, 110.0),
            ("low_value", 4000, 18.0, 2.0, 8.0, 40.0),
            ("churn_risk", 2000, 5.0, 0.0, 2.0, 6.0),
        ]

        total = sum(s[1] for s in mock_segments)
        snapshot.total_users = total
        total_score = 0.0

        for name, count, avg_score, avg_rev, avg_days, avg_sessions in mock_segments:
            seg = UserSegment(
                segment_name=name,
                user_count=count,
                user_share=round(count / total, 4),
                avg_value_score=avg_score,
                avg_revenue=avg_rev,
                avg_active_days=avg_days,
                avg_sessions=avg_sessions,
            )
            snapshot.segments.append(seg)
            total_score += avg_score * count

            if name == "high_value":
                snapshot.high_value_users = count
            elif name == "mid_value":
                snapshot.mid_value_users = count
            elif name == "low_value":
                snapshot.low_value_users = count
            elif name == "churn_risk":
                snapshot.churn_risk_users = count

        snapshot.avg_value_score = round(total_score / total, 2)

    def _mock_value_composition(self, snapshot: UserValueSnapshot) -> None:
        """生成 mock 价值构成数据。

        四维度贡献占比：
          - revenue     55%（付费仍是主要价值来源）
          - engagement  30%（活跃价值次之）
          - social      8%（社交贡献较低）
          - content     7%（内容贡献最低）
        """
        mock_dims = [
            ("revenue", 520000.0, 1200),
            ("engagement", 285000.0, 3800),
            ("social", 75000.0, 800),
            ("content", 68000.0, 600),
        ]
        grand_total = sum(d[1] for d in mock_dims)

        for dim, total, top_users in mock_dims:
            snapshot.value_composition.append(
                ValueContribution(
                    dimension=dim,
                    total_contribution=total,
                    share=round(total / grand_total, 4),
                    top_users=top_users,
                )
            )

    def _mock_value_evolution(self, snapshot: UserValueSnapshot) -> None:
        """生成 mock 价值演进数据。"""
        snapshot.rising_stars = 450          # 价值上升用户
        snapshot.declining_users = 280       # 价值下降用户
        snapshot.new_high_value = 85         # 新晋高价值
        snapshot.churned_high_value = 42     # 流失高价值

    def __repr__(self) -> str:
        return f"UserValueAnalyzer(analyzed={self.total_analyzed})"
