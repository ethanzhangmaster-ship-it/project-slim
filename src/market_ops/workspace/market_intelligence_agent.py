"""Market Intelligence Agent — 海外休闲游戏市场情报代理.

封装 market_intelligence 管道模块（TrendDetector / CompetitorTracker /
CreativeSignalMiner / CategoryHeatmapEngine / OpportunityGenerator），提供
统一的 agent 接口，供 workspace API 与跨 agent 协同调用。

设计原则（继承纪律红线）:
  - 复用现有 market_intelligence 管道模块，不重复实现算法
  - 不需要外部 API（使用现有管道模块的本地数据）
  - 参数走配置（MarketIntelligenceConfig），禁止硬编码
  - 数据持久化到 data/market_intelligence/
  - 线程安全（单例模式 + Lock）

数据流:
  管道模块(Trend/Competitor/Creative/Heatmap/Opportunity)
    → MarketIntelligenceAgent
    → MarketAnalysisResult / MarketReport
"""
from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════


@dataclass
class MarketAnalysisResult:
    """综合市场分析结果 — 趋势 + 竞品 + 创意信号 + 机会."""

    analysis_id: str
    trends: list[dict[str, Any]]            # TrendSignal.to_dict()
    competitors: list[dict[str, Any]]       # CompetitorProfile.to_dict()
    creative_signals: list[dict[str, Any]]  # CreativeSignal.to_dict()
    heatmap: dict[str, Any]                 # CategoryHeatmap.to_dict()
    opportunities: list[dict[str, Any]]     # CreativeOpportunity.to_dict()
    summary: str                            # 综合摘要
    top_opportunity: str                    # 最高分机会名称
    exploding_trend_count: int              # 爆发趋势数量
    rising_trend_count: int                 # 上升趋势数量
    top_threat: str                         # 最大竞品威胁名称
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "trends": self.trends,
            "competitors": self.competitors,
            "creative_signals": self.creative_signals,
            "heatmap": self.heatmap,
            "opportunities": self.opportunities,
            "summary": self.summary,
            "top_opportunity": self.top_opportunity,
            "exploding_trend_count": self.exploding_trend_count,
            "rising_trend_count": self.rising_trend_count,
            "top_threat": self.top_threat,
            "created_at": self.created_at,
        }


@dataclass
class MarketReport:
    """市场报告 — 结构化的市场情报输出."""

    report_id: str
    period: str                              # 报告周期 (e.g. "2026-W32")
    executive_summary: str                   # 执行摘要
    market_overview: dict[str, Any]          # 市场总览 (热度/品类)
    trend_highlights: list[dict[str, Any]]   # 趋势亮点
    competitive_landscape: dict[str, Any]    # 竞争格局
    creative_insights: list[dict[str, Any]]  # 创意洞察
    opportunity_pipeline: list[dict[str, Any]]  # 机会管线
    recommendations: list[str]               # 行动建议
    risk_alerts: list[str]                   # 风险预警
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "period": self.period,
            "executive_summary": self.executive_summary,
            "market_overview": self.market_overview,
            "trend_highlights": self.trend_highlights,
            "competitive_landscape": self.competitive_landscape,
            "creative_insights": self.creative_insights,
            "opportunity_pipeline": self.opportunity_pipeline,
            "recommendations": self.recommendations,
            "risk_alerts": self.risk_alerts,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# 配置（禁止硬编码，参数走配置）
# ═══════════════════════════════════════════════════════════════


@dataclass
class MarketIntelligenceConfig:
    """市场情报配置."""

    top_trends_limit: int = 10               # 趋势检测返回数量
    top_competitors_limit: int = 10          # 竞品追踪返回数量
    top_signals_limit: int = 20              # 创意信号返回数量
    top_opportunities_limit: int = 10        # 机会返回数量
    trending_signal_min_growth: float = 30.0  # 上升趋势最小增长率
    top_threats_limit: int = 5               # 头部威胁竞品数量


# ═══════════════════════════════════════════════════════════════
# Market Intelligence Agent
# ═══════════════════════════════════════════════════════════════


class MarketIntelligenceAgent:
    """Market Intelligence Agent — 海外休闲游戏市场情报代理.

    封装 market_intelligence 管道模块，提供统一的 agent 接口。

    gpt-researcher 集成:
      - research_market() 使用 Plan-and-Solve 架构做深度市场研究
      - 研究引擎可注入 (set_research_engine), 默认 lazy-load
      - gpt-researcher 不可用时优雅降级

    用法:
        agent = MarketIntelligenceAgent(data_dir="data")
        analysis = agent.analyze_market()
        trends = agent.detect_trends()
        competitors = agent.track_competitors()
        signals = agent.mine_creative_signals()
        heatmap = agent.get_category_heatmap()
        opportunities = agent.generate_opportunities()
        report = agent.get_market_report()
        stats = agent.get_stats()
        # gpt-researcher 深度研究
        research = agent.research_market("2026 休闲合并类游戏市场趋势")
    """

    def __init__(
        self,
        data_dir: str = "data",
        config: MarketIntelligenceConfig | None = None,
        research_engine=None,
    ) -> None:
        self.data_dir = data_dir
        self.config = config or MarketIntelligenceConfig()
        self._lock = threading.Lock()
        self._research_engine = research_engine

        # 复用现有 market_intelligence 管道模块
        from src.market_ops.market_intelligence import (
            CategoryHeatmapEngine,
            CompetitorTracker,
            CreativeSignalMiner,
            OpportunityGenerator,
            TrendDetector,
        )
        self._trend_detector = TrendDetector()
        self._competitor_tracker = CompetitorTracker()
        self._signal_miner = CreativeSignalMiner()
        self._heatmap_engine = CategoryHeatmapEngine()
        self._opportunity_generator = OpportunityGenerator()

    # ── gpt-researcher 集成 ─────────────────────────────────

    def set_research_engine(self, engine) -> None:
        """注入市场研究引擎 (gpt-researcher 封装)."""
        self._research_engine = engine

    def has_research_engine(self) -> bool:
        return self._research_engine is not None

    def _get_research_engine(self):
        """Lazy-load MarketResearchEngine, 不可用时返回 None."""
        if self._research_engine is not None:
            return self._research_engine
        try:
            from .research_engine import get_market_research_engine
            engine = get_market_research_engine()
            status = engine.check_status()
            if status["status"] == "ready":
                self._research_engine = engine
                return engine
        except Exception as exc:
            logger.debug("市场研究引擎不可用: %s", exc)
        return None

    def research_market(
        self,
        query: str,
        report_type: str | None = None,
    ) -> dict[str, Any]:
        """深度市场研究 — 使用 gpt-researcher 的 Plan-and-Solve 架构.

        将查询拆解为子问题 → 并行抓取多来源 → 聚合为带引用报告.

        Args:
            query: 研究查询 (如 "2026 休闲合并类游戏市场趋势和竞品分析")
            report_type: 报告类型 (research_report / summary_report)

        Returns:
            研究结果 dict (ResearchReport.to_dict()), 不可用时返回降级信息
        """
        engine = self._get_research_engine()
        if engine is None:
            return {
                "query": query,
                "content": "",
                "error": "gpt-researcher 不可用, 请安装并配置 LLM 和检索器",
                "success": False,
                "sources": [],
                "sub_queries": [],
            }

        report = engine.research(query, report_type=report_type)

        # 持久化研究结果
        self._persist_research(report.to_dict())

        return report.to_dict()

    def research_competitors(
        self,
        competitor_names: list[str],
        genre: str = "casual",
    ) -> list[dict[str, Any]]:
        """批量研究竞品 — 对每个竞品执行深度研究.

        Args:
            competitor_names: 竞品名称列表
            genre: 游戏品类

        Returns:
            研究结果列表
        """
        engine = self._get_research_engine()
        if engine is None:
            return [{
                "query": name,
                "content": "",
                "error": "gpt-researcher 不可用",
                "success": False,
            } for name in competitor_names]

        queries = [
            f"{name} {genre} game market performance, user acquisition strategy, monetization 2026"
            for name in competitor_names
        ]
        reports = engine.research_batch(queries)
        results = []
        for name, report in zip(competitor_names, reports):
            data = report.to_dict()
            data["competitor_name"] = name
            self._persist_research(data)
            results.append(data)

        return results

    # ── 核心方法 ─────────────────────────────────────────────

    def analyze_market(self) -> MarketAnalysisResult:
        """综合市场分析 — 趋势 + 竞品 + 创意信号 + 机会.

        Returns:
            MarketAnalysisResult 实例
        """
        with self._lock:
            trends = self._trend_detector.detect_from_mock_data()
            competitors = self._competitor_tracker.scan()
            signals = self._signal_miner.mine()
            heatmap = self._heatmap_engine.generate()
            opportunities = self._opportunity_generator.generate()

        exploding_count = sum(
            1 for t in trends if t.direction.value == "exploding"
        )
        rising_count = sum(
            1 for t in trends if t.direction.value == "rising"
        )

        top_opp = opportunities[0] if opportunities else None
        top_threat = max(competitors, key=lambda c: c.threat_level) if competitors else None

        summary = (
            f"检测到 {len(trends)} 个市场趋势"
            f"（{exploding_count} 个爆发、{rising_count} 个上升），"
            f"追踪 {len(competitors)} 个竞品，"
            f"挖掘 {len(signals)} 个创意信号，"
            f"生成 {len(opportunities)} 个机会。"
        )

        result = MarketAnalysisResult(
            analysis_id=f"mkt_{uuid.uuid4().hex[:12]}",
            trends=[t.to_dict() for t in trends],
            competitors=[c.to_dict() for c in competitors],
            creative_signals=[s.to_dict() for s in signals],
            heatmap=heatmap.to_dict(),
            opportunities=[o.to_dict() for o in opportunities],
            summary=summary,
            top_opportunity=top_opp.name if top_opp else "",
            exploding_trend_count=exploding_count,
            rising_trend_count=rising_count,
            top_threat=top_threat.name if top_threat else "",
            created_at=_now_iso(),
        )

        self._persist_analysis(result)
        logger.info(
            "Market analyzed: %d trends, %d competitors, %d signals, %d opportunities",
            len(trends), len(competitors), len(signals), len(opportunities),
        )
        return result

    def detect_trends(self) -> list[dict[str, Any]]:
        """趋势检测 — 从多源信号检测市场趋势.

        Returns:
            趋势信号列表 (TrendSignal.to_dict())
        """
        with self._lock:
            trends = self._trend_detector.get_top_trends(
                n=self.config.top_trends_limit
            )
        logger.info("Trends detected: %d", len(trends))
        return [t.to_dict() for t in trends]

    def track_competitors(self) -> list[dict[str, Any]]:
        """竞品追踪 — 扫描竞品游戏并分析威胁等级.

        Returns:
            竞品档案列表 (CompetitorProfile.to_dict())
        """
        with self._lock:
            competitors = self._competitor_tracker.get_top_threats(
                n=self.config.top_competitors_limit
            )
        logger.info("Competitors tracked: %d", len(competitors))
        return [c.to_dict() for c in competitors]

    def mine_creative_signals(self) -> list[dict[str, Any]]:
        """创意信号挖掘 — 从广告数据中挖掘创意信号.

        Returns:
            创意信号列表 (CreativeSignal.to_dict())
        """
        with self._lock:
            signals = self._signal_miner.mine()
        # 截取限定数量
        signals = signals[: self.config.top_signals_limit]
        logger.info("Creative signals mined: %d", len(signals))
        return [s.to_dict() for s in signals]

    def get_category_heatmap(self) -> dict[str, Any]:
        """品类热度图 — 跨品类市场热度可视化.

        Returns:
            CategoryHeatmap.to_dict()
        """
        with self._lock:
            heatmap = self._heatmap_engine.generate()
        logger.info(
            "Heatmap generated: %d cells, %d hot categories",
            len(heatmap.cells), len(heatmap.hot_categories),
        )
        return heatmap.to_dict()

    def generate_opportunities(self) -> list[dict[str, Any]]:
        """机会生成 — 综合管道信号生成创意机会.

        Returns:
            创意机会列表 (CreativeOpportunity.to_dict())
        """
        with self._lock:
            opportunities = self._opportunity_generator.get_top_opportunities(
                n=self.config.top_opportunities_limit
            )
        logger.info("Opportunities generated: %d", len(opportunities))
        return [o.to_dict() for o in opportunities]

    def get_market_report(self) -> MarketReport:
        """市场报告 — 结构化的市场情报输出.

        Returns:
            MarketReport 实例
        """
        with self._lock:
            trends = self._trend_detector.detect_from_mock_data()
            competitors = self._competitor_tracker.scan()
            signals = self._signal_miner.mine()
            heatmap = self._heatmap_engine.generate()
            opportunities = self._opportunity_generator.generate()

        # 执行摘要
        exploding = [t for t in trends if t.direction.value == "exploding"]
        top_opp = opportunities[0] if opportunities else None
        top_threat = max(competitors, key=lambda c: c.threat_level) if competitors else None

        summary_parts = [
            f"本期监测 {len(trends)} 个趋势（{len(exploding)} 个爆发），"
            f"{len(competitors)} 个竞品，{len(signals)} 个创意信号，"
            f"{len(opportunities)} 个机会。",
        ]
        if top_opp:
            summary_parts.append(
                f"最高分机会：{top_opp.name}（{top_opp.score:.1f} 分）。"
            )
        if top_threat:
            summary_parts.append(
                f"最大威胁竞品：{top_threat.name}"
                f"（威胁度 {top_threat.threat_level:.0f}）。"
            )
        executive_summary = "".join(summary_parts)

        # 市场总览
        market_overview = {
            "total_trends": len(trends),
            "total_competitors": len(competitors),
            "total_signals": len(signals),
            "total_opportunities": len(opportunities),
            "hot_categories": heatmap.hot_categories,
            "cold_categories": heatmap.cold_categories,
            "top_opportunity_categories": [
                o.category for o in opportunities[:5]
            ],
        }

        # 趋势亮点 (取 velocity_score 最高的 5 个)
        trend_highlights = [
            t.to_dict() for t in sorted(
                trends, key=lambda t: t.velocity_score, reverse=True
            )[:5]
        ]

        # 竞争格局
        competitive_landscape = {
            "tier_1_count": sum(1 for c in competitors if c.tier.value == "tier_1"),
            "tier_2_count": sum(1 for c in competitors if c.tier.value == "tier_2"),
            "tier_3_count": sum(1 for c in competitors if c.tier.value == "tier_3"),
            "top_threats": [c.to_dict() for c in sorted(
                competitors, key=lambda c: c.threat_level, reverse=True
            )[:3]],
            "rising_competitors": [c.to_dict() for c in sorted(
                competitors, key=lambda c: c.growth_30d, reverse=True
            )[:3]],
            "genome_patterns": self._competitor_tracker.extract_genome_patterns(),
        }

        # 创意洞察 (取增长最快的 5 个信号)
        creative_insights = [
            s.to_dict() for s in sorted(
                signals, key=lambda s: s.growth_30d, reverse=True
            )[:5]
        ]

        # 机会管线
        opportunity_pipeline = [o.to_dict() for o in opportunities[:5]]

        # 行动建议
        recommendations = self._build_recommendations(
            trends, competitors, signals, heatmap, opportunities
        )

        # 风险预警
        risk_alerts = self._build_risk_alerts(trends, competitors, heatmap)

        report = MarketReport(
            report_id=f"mkt_report_{uuid.uuid4().hex[:12]}",
            period=datetime.now(timezone.utc).strftime("%Y-W%W"),
            executive_summary=executive_summary,
            market_overview=market_overview,
            trend_highlights=trend_highlights,
            competitive_landscape=competitive_landscape,
            creative_insights=creative_insights,
            opportunity_pipeline=opportunity_pipeline,
            recommendations=recommendations,
            risk_alerts=risk_alerts,
            created_at=_now_iso(),
        )

        self._persist_report(report)
        logger.info("Market report generated: %s", report.report_id)
        return report

    def get_stats(self) -> dict[str, Any]:
        """统计信息 — 市场情报数据汇总.

        Returns:
            统计信息字典
        """
        analyses = self.list_analyses(limit=1000)
        reports = self.list_reports(limit=1000)

        # 管道模块实时统计
        with self._lock:
            trends = self._trend_detector.detect_from_mock_data()
            competitors = self._competitor_tracker.scan()
            signals = self._signal_miner.mine()
            heatmap = self._heatmap_engine.generate()
            opportunities = self._opportunity_generator.generate()

        # 趋势方向分布
        trend_direction_dist: dict[str, int] = {}
        for t in trends:
            d = t.direction.value
            trend_direction_dist[d] = trend_direction_dist.get(d, 0) + 1

        # 竞品等级分布
        competitor_tier_dist: dict[str, int] = {}
        for c in competitors:
            t = c.tier.value
            competitor_tier_dist[t] = competitor_tier_dist.get(t, 0) + 1

        # 创意信号维度分布
        signal_dimension_dist: dict[str, int] = {}
        for s in signals:
            d = s.dimension
            signal_dimension_dist[d] = signal_dimension_dist.get(d, 0) + 1

        return {
            "total_analyses": len(analyses),
            "total_reports": len(reports),
            "pipeline_stats": {
                "trend_count": len(trends),
                "competitor_count": len(competitors),
                "creative_signal_count": len(signals),
                "heatmap_cell_count": len(heatmap.cells),
                "opportunity_count": len(opportunities),
            },
            "trend_direction_distribution": trend_direction_dist,
            "competitor_tier_distribution": competitor_tier_dist,
            "signal_dimension_distribution": signal_dimension_dist,
            "hot_categories": heatmap.hot_categories,
            "top_opportunity_score": (
                opportunities[0].score if opportunities else 0.0
            ),
            "recent_analyses": analyses[:5],
            "recent_reports": reports[:5],
        }

    # ── 查询方法 ─────────────────────────────────────────────

    def list_analyses(self, limit: int = 50) -> list[dict[str, Any]]:
        """列出历史综合分析记录."""
        path = Path(self.data_dir) / "market_intelligence" / "analyses.jsonl"
        return _read_jsonl(path, limit)

    def list_reports(self, limit: int = 50) -> list[dict[str, Any]]:
        """列出历史市场报告."""
        path = Path(self.data_dir) / "market_intelligence" / "reports.jsonl"
        return _read_jsonl(path, limit)

    def list_researches(self, limit: int = 50) -> list[dict[str, Any]]:
        """列出历史 gpt-researcher 研究记录."""
        path = Path(self.data_dir) / "market_intelligence" / "researches.jsonl"
        return _read_jsonl(path, limit)

    def get_report(self, report_id: str) -> dict[str, Any] | None:
        """按 ID 查询市场报告."""
        for r in self.list_reports(limit=500):
            if r.get("report_id") == report_id:
                return r
        return None

    # ── 内部方法 ─────────────────────────────────────────────

    def _build_recommendations(
        self, trends: list, competitors: list, signals: list,
        heatmap: Any, opportunities: list,
    ) -> list[str]:
        """基于管道信号构建行动建议."""
        recs: list[str] = []

        # 趋势建议
        exploding = [t for t in trends if t.direction.value == "exploding"]
        if exploding:
            top_exploding = max(exploding, key=lambda t: t.velocity_score)
            recs.append(
                f"优先布局爆发趋势：{top_exploding.category}/"
                f"{top_exploding.subcategory}（增速 {top_exploding.growth_pct:.0f}%）"
            )

        # 竞品建议
        rising_comps = sorted(
            competitors, key=lambda c: c.growth_30d, reverse=True
        )[:2]
        for comp in rising_comps:
            if comp.opportunities:
                recs.append(
                    f"针对 {comp.name} 的弱点：{comp.opportunities[0]}"
                )

        # 创意信号建议
        hot_hooks = [s for s in signals
                     if s.dimension == "hook" and s.ctr_prediction == "high"]
        if hot_hooks:
            best_hook = max(hot_hooks, key=lambda s: s.prevalence)
            recs.append(
                f"采用高 CTR 钩子：{best_hook.value}"
                f"（ prevalence {best_hook.prevalence:.0f}%）"
            )

        # 热度图建议
        if heatmap.top_opportunities:
            top_cell = heatmap.top_opportunities[0]
            if top_cell.recommended_hybrids:
                recs.append(
                    f"探索品类混合：{top_cell.recommended_hybrids[0]}"
                    f"（机会缺口 {top_cell.opportunity_gap:.0f}）"
                )

        # 机会建议
        if opportunities:
            top_opp = opportunities[0]
            recs.append(
                f"首推机会：{top_opp.name}（综合评分 {top_opp.score:.1f}）"
            )

        if not recs:
            recs.append("暂无显著机会，建议持续监测市场信号")

        return recs

    def _build_risk_alerts(
        self, trends: list, competitors: list, heatmap: Any,
    ) -> list[str]:
        """基于管道信号构建风险预警."""
        alerts: list[str] = []

        # 高威胁竞品
        high_threats = [c for c in competitors if c.threat_level >= 80]
        for comp in high_threats:
            alerts.append(
                f"高威胁竞品：{comp.name}（威胁度 {comp.threat_level:.0f}，"
                f"增速 {comp.growth_30d:.0f}%）"
            )

        # 下降趋势
        falling = [t for t in trends if t.direction.value == "falling"]
        for trend in falling:
            alerts.append(
                f"市场下行趋势：{trend.category}/{trend.subcategory}"
                f"（增速 {trend.growth_pct:.0f}%）"
            )

        # 冷门品类
        for cat in heatmap.cold_categories:
            alerts.append(f"冷门品类：{cat}，建议暂缓投入")

        if not alerts:
            alerts.append("暂无显著风险信号")

        return alerts

    # ── 持久化 ─────────────────────────────────────────────

    def _persist_analysis(self, result: MarketAnalysisResult) -> None:
        path = Path(self.data_dir) / "market_intelligence" / "analyses.jsonl"
        _append_jsonl(path, result.to_dict())

    def _persist_report(self, report: MarketReport) -> None:
        path = Path(self.data_dir) / "market_intelligence" / "reports.jsonl"
        _append_jsonl(path, report.to_dict())

    def _persist_research(self, data: dict[str, Any]) -> None:
        path = Path(self.data_dir) / "market_intelligence" / "researches.jsonl"
        _append_jsonl(path, data)


# ═══════════════════════════════════════════════════════════════
# 单例管理（线程安全）
# ═══════════════════════════════════════════════════════════════


_instance_lock = threading.Lock()
_instance: MarketIntelligenceAgent | None = None


def get_market_intelligence_agent(
    data_dir: str = "data",
    config: MarketIntelligenceConfig | None = None,
) -> MarketIntelligenceAgent:
    """获取 MarketIntelligenceAgent 单例（线程安全）.

    Args:
        data_dir: 数据目录
        config: 配置实例

    Returns:
        MarketIntelligenceAgent 单例
    """
    global _instance
    if _instance is not None and config is None:
        return _instance
    with _instance_lock:
        if _instance is None or config is not None:
            _instance = MarketIntelligenceAgent(
                data_dir=data_dir, config=config
            )
        return _instance


def reset_market_intelligence_agent() -> None:
    """重置单例（主要用于测试）."""
    global _instance
    with _instance_lock:
        _instance = None


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """追加写入 JSONL 文件 (带轮转保护)."""
    from .jsonl_rotator import get_default_rotator
    rotator = get_default_rotator(
        data_dir=str(path.parent.parent) if path.parent.parent else "data"
    )
    rotator.maybe_rotate(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path, limit: int = 50) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    lines = [l for l in text.splitlines() if l.strip()]
    for line in lines[-limit:]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    records.reverse()
    return records
