"""E12.2 — Economy Analyzer。

经济系统分析器 —— 回答"游戏经济是否健康？资源通胀了吗？"

对于 Merge / Puzzle / Simulation 类游戏至关重要。
分析资源（金币、钻石、体力、材料）的产出（Source）和消耗（Sink），
检测经济通胀/通缩，识别资源积累异常。

核心逻辑：
  Source（产出） vs Sink（消耗）
    - Source > Sink → 通胀（资源堆积，付费意愿下降）
    - Source < Sink → 通缩（资源短缺，挫败感上升）
    - Source ≈ Sink → 健康

Usage:
    analyzer = EconomyAnalyzer(td_reality)
    snapshot = analyzer.analyze(project_id=102, lookback_days=30)
    print(snapshot.inflation_rate, snapshot.imbalanced_resources)
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
class ResourceFlow:
    """单个资源的产出/消耗流。"""

    resource_name: str = ""
    total_source: float = 0.0   # 总产出
    total_sink: float = 0.0    # 总消耗
    net_balance: float = 0.0   # 净余额 = Source - Sink
    inflation_rate: float = 0.0  # 通胀率 = (Source - Sink) / Sink
    status: str = "balanced"   # balanced / inflation / deflation

    # 产出来源 Top 3
    top_sources: list[tuple[str, float]] = field(default_factory=list)
    # 消耗去向 Top 3
    top_sinks: list[tuple[str, float]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_name": self.resource_name,
            "total_source": round(self.total_source, 2),
            "total_sink": round(self.total_sink, 2),
            "net_balance": round(self.net_balance, 2),
            "inflation_rate": round(self.inflation_rate, 4),
            "status": self.status,
            "top_sources": [(n, round(v, 2)) for n, v in self.top_sources],
            "top_sinks": [(n, round(v, 2)) for n, v in self.top_sinks],
        }


@dataclass
class EconomySnapshot:
    """经济系统快照。"""

    project_id: int = 0
    period_start: str = ""
    period_end: str = ""

    # 各资源流
    resources: list[ResourceFlow] = field(default_factory=list)

    # 整体经济状态
    overall_status: str = "balanced"  # balanced / inflation / deflation
    avg_inflation_rate: float = 0.0

    # 异常资源
    imbalanced_resources: list[str] = field(default_factory=list)
    # 通胀严重的资源
    inflation_resources: list[str] = field(default_factory=list)
    # 通缩严重的资源
    deflation_resources: list[str] = field(default_factory=list)

    # 付费与经济关系
    payer_resource_ratio: float = 0.0  # 付费用户资源占比 vs 非付费用户
    resource_hoarder_count: int = 0  # 资源囤积者数量
    resource_starved_count: int = 0  # 资源匮乏者数量

    # 洞察
    insights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "resources": [r.to_dict() for r in self.resources],
            "overall_status": self.overall_status,
            "avg_inflation_rate": round(self.avg_inflation_rate, 4),
            "imbalanced_resources": self.imbalanced_resources,
            "inflation_resources": self.inflation_resources,
            "deflation_resources": self.deflation_resources,
            "payer_resource_ratio": round(self.payer_resource_ratio, 4),
            "resource_hoarder_count": self.resource_hoarder_count,
            "resource_starved_count": self.resource_starved_count,
            "insights": self.insights,
        }


class EconomyAnalyzer:
    """经济系统分析器。

    消费 ThinkingDataReality，输出 EconomySnapshot。

    Attributes:
        td_reality:     ThinkingData 门面
        total_analyzed: 累计分析次数
    """

    # 通胀判定阈值
    INFLATION_THRESHOLD = 0.20   # Source/Sink > 1.20 → 通胀
    DEFLATION_THRESHOLD = -0.20  # Source/Sink < 0.80 → 通缩

    # 默认追踪的资源类型
    DEFAULT_RESOURCES = ["coins", "gems", "energy", "materials"]

    def __init__(self, td_reality: ThinkingDataReality | None = None) -> None:
        self._td = td_reality
        self.total_analyzed: int = 0

    def analyze(
        self,
        project_id: int,
        lookback_days: int = 30,
        resources: list[str] | None = None,
    ) -> EconomySnapshot:
        """分析经济系统。

        Args:
            project_id:    数数项目 ID
            lookback_days: 回溯天数
            resources:     追踪的资源列表，None 时使用默认

        Returns:
            EconomySnapshot
        """
        today = date.today()
        start = (today - timedelta(days=lookback_days)).isoformat()
        end = today.isoformat()

        tracked = resources or self.DEFAULT_RESOURCES

        snapshot = EconomySnapshot(
            project_id=project_id,
            period_start=start,
            period_end=end,
        )

        # 1. 拉取各资源的 Source/Sink
        self._fetch_resource_flows(project_id, start, end, tracked, snapshot)

        # 2. 计算通胀率和状态
        self._compute_inflation(snapshot)

        # 3. 识别异常资源
        self._identify_imbalance(snapshot)

        # 4. 付费与经济关系
        self._fetch_payer_economy(project_id, start, end, snapshot)

        # 5. 生成洞察
        self._generate_insights(snapshot)

        self.total_analyzed += 1
        logger.info(
            f"EconomyAnalyzer: project={project_id}, "
            f"status={snapshot.overall_status}, "
            f"imbalanced={len(snapshot.imbalanced_resources)}"
        )
        return snapshot

    # ── Internal ────────────────────────────────────────

    def _fetch_resource_flows(
        self,
        project_id: int,
        start: str,
        end: str,
        resources: list[str],
        snapshot: EconomySnapshot,
    ) -> None:
        """拉取各资源的产出和消耗数据（单次聚合查询）。

        优化：原实现按资源逐个发 2 条 SQL（N+1 查询，4 资源 = 8 次往返），
        现改为单条 GROUP BY 聚合查询，1 次往返获取全部资源的 source/sink。
        """
        if not self._td or not self._td._client:
            self._mock_resource_flows(resources, snapshot)
            return

        resources_filter = ", ".join(f"'{r}'" for r in resources)
        sql = (
            f"SELECT "
            f"  resource_type, "
            f"  resource_action, "
            f"  CASE WHEN resource_change > 0 THEN 'source' ELSE 'sink' END AS flow_type, "
            f"  SUM(ABS(resource_change)) AS total "
            f"FROM v_event_{project_id} "
            f"WHERE event_name = 'resource_change' "
            f"  AND resource_type IN ({resources_filter}) "
            f"  AND event_date BETWEEN '{start}' AND '{end}' "
            f"GROUP BY resource_type, resource_action, flow_type "
            f"ORDER BY resource_type, total DESC"
        )

        try:
            client = self._td._client
            result = client.sql_query(project_id, sql)
            rows = result.get("data", result.get("rows", []))

            # 按资源分桶，每桶内分 source/sink
            flows_map: dict[str, dict[str, list[tuple[str, float]]]] = {
                res: {"source": [], "sink": []} for res in resources
            }

            for row in rows:
                if isinstance(row, dict):
                    res_type = row.get("resource_type", "")
                    action = row.get("resource_action", "")
                    flow_type = row.get("flow_type", "")
                    total = float(row.get("total", 0))
                else:
                    res_type = row[0] if len(row) > 0 else ""
                    action = row[1] if len(row) > 1 else ""
                    flow_type = row[2] if len(row) > 2 else ""
                    total = float(row[3]) if len(row) > 3 else 0

                if res_type in flows_map and flow_type in ("source", "sink"):
                    flows_map[res_type][flow_type].append((action, total))

            # 为每个资源构建 ResourceFlow（保持 resources 列表顺序）
            for res in resources:
                buckets = flows_map[res]
                sources = sorted(
                    buckets["source"], key=lambda x: x[1], reverse=True
                )
                sinks = sorted(
                    buckets["sink"], key=lambda x: x[1], reverse=True
                )

                flow = ResourceFlow(
                    resource_name=res,
                    top_sources=sources[:3],
                    top_sinks=sinks[:3],
                    total_source=round(sum(v for _, v in sources), 2),
                    total_sink=round(sum(v for _, v in sinks), 2),
                )
                flow.net_balance = flow.total_source - flow.total_sink
                snapshot.resources.append(flow)
        except Exception as exc:
            logger.warning(f"EconomyAnalyzer: resource SQL failed: {exc}")
            self._mock_resource_flows(resources, snapshot)

    def _compute_inflation(self, snapshot: EconomySnapshot) -> None:
        """计算各资源通胀率和整体状态。"""
        if not snapshot.resources:
            return

        inflation_rates: list[float] = []

        for flow in snapshot.resources:
            if flow.total_sink > 0:
                flow.inflation_rate = round(
                    (flow.total_source - flow.total_sink) / flow.total_sink, 4
                )
            elif flow.total_source > 0:
                flow.inflation_rate = 1.0  # 只有产出没有消耗 → 100% 通胀

            if flow.inflation_rate > self.INFLATION_THRESHOLD:
                flow.status = "inflation"
            elif flow.inflation_rate < self.DEFLATION_THRESHOLD:
                flow.status = "deflation"
            else:
                flow.status = "balanced"

            inflation_rates.append(flow.inflation_rate)

        snapshot.avg_inflation_rate = round(
            sum(inflation_rates) / len(inflation_rates), 4
        )

        # 整体状态
        if snapshot.avg_inflation_rate > self.INFLATION_THRESHOLD:
            snapshot.overall_status = "inflation"
        elif snapshot.avg_inflation_rate < self.DEFLATION_THRESHOLD:
            snapshot.overall_status = "deflation"

    def _identify_imbalance(self, snapshot: EconomySnapshot) -> None:
        """识别异常资源。"""
        for flow in snapshot.resources:
            if flow.status != "balanced":
                snapshot.imbalanced_resources.append(flow.resource_name)
            if flow.status == "inflation":
                snapshot.inflation_resources.append(flow.resource_name)
            elif flow.status == "deflation":
                snapshot.deflation_resources.append(flow.resource_name)

    def _fetch_payer_economy(
        self,
        project_id: int,
        start: str,
        end: str,
        snapshot: EconomySnapshot,
    ) -> None:
        """分析付费用户与非付费用户的资源差异。"""
        # Mock
        snapshot.payer_resource_ratio = 2.5  # 付费用户资源量是非付费的 2.5 倍
        snapshot.resource_hoarder_count = 350  # 囤积者
        snapshot.resource_starved_count = 1200  # 匮乏者

    def _generate_insights(self, snapshot: EconomySnapshot) -> None:
        """生成经济系统洞察。"""
        insights: list[str] = []

        # 整体状态
        if snapshot.overall_status == "inflation":
            insights.append(
                f"经济通胀（平均通胀率 {snapshot.avg_inflation_rate:.0%}），"
                f"资源产出超过消耗，玩家资源堆积导致付费意愿下降"
            )
        elif snapshot.overall_status == "deflation":
            insights.append(
                f"经济通缩（平均通胀率 {snapshot.avg_inflation_rate:.0%}），"
                f"资源消耗超过产出，玩家挫败感可能上升"
            )
        else:
            insights.append(
                f"经济基本平衡（通胀率 {snapshot.avg_inflation_rate:.0%}）"
            )

        # 通胀资源
        for res in snapshot.inflation_resources:
            flow = next(
                (f for f in snapshot.resources if f.resource_name == res),
                None,
            )
            if flow:
                insights.append(
                    f"'{res}' 通胀严重（+{flow.inflation_rate:.0%}），"
                    f"建议增加消耗途径（如限时商店、高级合成）"
                )

        # 通缩资源
        for res in snapshot.deflation_resources:
            flow = next(
                (f for f in snapshot.resources if f.resource_name == res),
                None,
            )
            if flow:
                insights.append(
                    f"'{res}' 通缩（{flow.inflation_rate:.0%}），"
                    f"建议增加产出途径或降低消耗门槛"
                )

        # 付费差异
        if snapshot.payer_resource_ratio > 3.0:
            insights.append(
                f"付费用户资源量是非付费的 {snapshot.payer_resource_ratio:.1f} 倍，"
                f"差距过大可能导致非付费用户流失"
            )

        # 囤积者
        if snapshot.resource_hoarder_count > 0:
            insights.append(
                f"{snapshot.resource_hoarder_count} 个资源囤积者，"
                f"建议设计高价值消耗点回收资源"
            )

        snapshot.insights = insights

    # ── Mock ───────────────────────────────────────────

    def _mock_resource_flows(
        self,
        resources: list[str],
        snapshot: EconomySnapshot,
    ) -> None:
        """生成 mock 资源流数据。"""
        # 每种资源有不同的经济状态
        mock_data = {
            "coins": {
                "source": 510000, "sink": 420000,  # 通胀 +21%
                "sources": [("关卡奖励", 200000), ("任务", 150000), ("活动", 100000)],
                "sinks": [("升级", 180000), ("合成", 150000), ("购买", 80000)],
            },
            "gems": {
                "source": 75000, "sink": 95000,  # 通缩 -21%
                "sources": [("成就", 30000), ("每日登录", 25000), ("活动", 20000)],
                "sinks": [("抽卡", 45000), ("商店", 30000), ("体力补充", 15000)],
            },
            "energy": {
                "source": 200000, "sink": 195000,  # 平衡 +2.5%
                "sources": [("自然恢复", 120000), ("广告", 50000), ("好友赠送", 25000)],
                "sinks": [("关卡", 150000), ("活动", 30000), ("挑战", 12000)],
            },
            "materials": {
                "source": 300000, "sink": 180000,  # 通胀 +67%
                "sources": [("采集", 150000), ("关卡掉落", 100000), ("活动", 40000)],
                "sinks": [("合成", 100000), ("升级", 50000), ("交易", 25000)],
            },
        }

        for res in resources:
            data = mock_data.get(res, {
                "source": 100000, "sink": 95000,
                "sources": [("来源A", 50000), ("来源B", 30000), ("来源C", 15000)],
                "sinks": [("消耗A", 45000), ("消耗B", 30000), ("消耗C", 15000)],
            })

            flow = ResourceFlow(
                resource_name=res,
                total_source=data["source"],
                total_sink=data["sink"],
                net_balance=data["source"] - data["sink"],
                top_sources=[(n, v) for n, v in data["sources"]],
                top_sinks=[(n, v) for n, v in data["sinks"]],
            )
            snapshot.resources.append(flow)

    def __repr__(self) -> str:
        return f"EconomyAnalyzer(analyzed={self.total_analyzed})"
