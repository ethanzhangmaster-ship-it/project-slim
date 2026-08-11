"""周期报告生成器 — 日报/周报/月报统一框架.

支持:
  - 三种周期: 日报 (daily) / 周报 (weekly) / 月报 (monthly)
  - 六种类型: executive / growth / monetization / ua / creative / portfolio
  - 指标聚合 + 环比趋势分析
  - Markdown 输出 + JSON 持久化
  - 本地化生成, 不依赖外部 API

设计原则:
  - 报告生成完全本地化（不调用外部 API）
  - 指标数据使用默认值或可注入（不依赖真实数据源）
  - 持久化到 data/reports/{period}/YYYY-MM-DD.{report_type}.{ext}
  - 代码注释用中文
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════════════════════════

class ReportPeriod:
    """报告周期常量。"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

    @classmethod
    def all(cls) -> list[str]:
        return [cls.DAILY, cls.WEEKLY, cls.MONTHLY]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls.all()


class ReportType:
    """报告类型常量。"""
    EXECUTIVE = "executive"        # 高管摘要
    GROWTH = "growth"              # 增长报告
    MONETIZATION = "monetization"  # 变现报告
    UA = "ua"                      # 用户获取
    CREATIVE = "creative"          # 创意素材
    PORTFOLIO = "portfolio"        # 组合报告

    @classmethod
    def all(cls) -> list[str]:
        return [
            cls.EXECUTIVE, cls.GROWTH, cls.MONETIZATION,
            cls.UA, cls.CREATIVE, cls.PORTFOLIO,
        ]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls.all()


# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════

@dataclass
class ReportMetrics:
    """报告指标汇总.

    所有数值字段使用默认值, 允许调用方注入真实数据。
    """
    period: str                          # daily / weekly / monthly
    start_date: str                       # YYYY-MM-DD
    end_date: str                         # YYYY-MM-DD
    # 核心指标
    total_revenue: float = 0.0
    total_spend: float = 0.0
    total_installs: int = 0
    avg_dau: int = 0
    avg_arpdau: float = 0.0
    overall_roas: float = 0.0
    # 趋势 (环比变化 %)
    revenue_trend: float = 0.0
    spend_trend: float = 0.0
    installs_trend: float = 0.0
    dau_trend: float = 0.0
    # Top performers
    top_games: list[dict] = field(default_factory=list)
    top_creatives: list[dict] = field(default_factory=list)
    # 异常和告警
    anomalies: list[dict] = field(default_factory=list)
    alerts: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PeriodReport:
    """周期报告对象。"""
    report_id: str
    report_type: str               # ReportType
    period: str                    # ReportPeriod
    start_date: str
    end_date: str
    metrics: ReportMetrics
    sections: list[dict]           # [{title, content, data}]
    summary: str
    recommendations: list[str]
    generated_at: str
    file_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "report_type": self.report_type,
            "period": self.period,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "metrics": self.metrics.to_dict(),
            "sections": self.sections,
            "summary": self.summary,
            "recommendations": self.recommendations,
            "generated_at": self.generated_at,
            "file_path": self.file_path,
        }


# ═══════════════════════════════════════════════════════════════
# 生成器
# ═══════════════════════════════════════════════════════════════

class PeriodReportGenerator:
    """周期报告生成器.

    支持:
      - 日报/周报/月报
      - 多种报告类型 (executive/growth/monetization/ua/creative/portfolio)
      - 指标聚合 + 环比趋势分析
      - Markdown 输出
      - 持久化到 data/reports/{period}/
    """

    # 默认指标基线 (用于本地化生成, 不依赖外部数据源)
    _DEFAULT_BASELINE = {
        "daily": {
            "revenue": 11120.0,
            "spend": 1280.0,
            "installs": 4200,
            "dau": 36066,
        },
        "weekly": {
            "revenue": 77840.0,
            "spend": 8960.0,
            "installs": 29400,
            "dau": 35500,
        },
        "monthly": {
            "revenue": 334000.0,
            "spend": 38400.0,
            "installs": 126000,
            "dau": 35200,
        },
    }

    def __init__(self, data_dir: str = ""):
        """初始化生成器.

        Args:
            data_dir: 数据根目录 (空则使用项目 data/)
        """
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            # 默认: 项目根 / data
            self.data_dir = Path(__file__).resolve().parents[4] / "data"
        # 报告根目录: data/reports/
        self.reports_root = self.data_dir / "reports"
        self.reports_root.mkdir(parents=True, exist_ok=True)
        # 缓存已加载的报告 (report_id -> PeriodReport)
        self._cache: dict[str, PeriodReport] = {}

    # ── 公共 API ────────────────────────────────────────────

    def generate_report(
        self,
        report_type: str,
        period: str,
        end_date: str | None = None,
        game_ids: list[str] | None = None,
    ) -> PeriodReport:
        """生成报告.

        Args:
            report_type: ReportType 值
            period: ReportPeriod 值
            end_date: 报告截止日期 (None 则用今天)
            game_ids: 指定游戏 (None 则全部)

        Returns:
            PeriodReport 对象
        """
        # 参数校验
        if not ReportType.is_valid(report_type):
            raise ValueError(f"无效的 report_type: {report_type}")
        if not ReportPeriod.is_valid(period):
            raise ValueError(f"无效的 period: {period}")

        # 计算时间窗口
        end_dt = self._parse_date(end_date) if end_date else date.today()
        start_dt = self._calc_start_date(end_dt, period)
        start_str = start_dt.isoformat()
        end_str = end_dt.isoformat()

        # 计算指标
        metrics = self.calculate_metrics(start_str, end_str, game_ids)
        metrics.period = period

        # 生成各章节 (按报告类型选择)
        sections = self._build_sections(report_type, metrics)
        summary = self.generate_executive_summary(metrics) if report_type == ReportType.EXECUTIVE else self._build_summary(report_type, metrics)
        recommendations = self._build_recommendations(report_type, metrics)

        # 报告 ID
        report_id = self._make_report_id(report_type, period, end_str)
        generated_at = datetime.now().isoformat(timespec="seconds")

        report = PeriodReport(
            report_id=report_id,
            report_type=report_type,
            period=period,
            start_date=start_str,
            end_date=end_str,
            metrics=metrics,
            sections=sections,
            summary=summary,
            recommendations=recommendations,
            generated_at=generated_at,
            file_path="",
        )

        # 持久化 (先计算路径, 再写入, 保证 file_path 字段持久化)
        file_path = self._compute_md_path(report)
        report.file_path = str(file_path)
        self._persist_report(report)

        # 缓存
        self._cache[report.report_id] = report
        return report

    def generate_executive_summary(self, metrics: ReportMetrics) -> str:
        """生成高管摘要。"""
        trend_emoji = self._trend_emoji(metrics.revenue_trend)
        lines = [
            f"## 高管摘要 ({metrics.period})",
            "",
            f"**报告周期**: {metrics.start_date} ~ {metrics.end_date}",
            "",
            f"**核心指标**:",
            f"- 总收入: **${metrics.total_revenue:,.2f}** ({trend_emoji} {metrics.revenue_trend:+.1f}%)",
            f"- 总花费: ${metrics.total_spend:,.2f} ({self._trend_emoji(metrics.spend_trend)} {metrics.spend_trend:+.1f}%)",
            f"- 总安装: {metrics.total_installs:,} ({self._trend_emoji(metrics.installs_trend)} {metrics.installs_trend:+.1f}%)",
            f"- 平均 DAU: {metrics.avg_dau:,} ({self._trend_emoji(metrics.dau_trend)} {metrics.dau_trend:+.1f}%)",
            f"- 整体 ROAS: **{metrics.overall_roas:.1f}%**",
            f"- ARPDAU: ${metrics.avg_arpdau:.4f}",
        ]
        if metrics.alerts:
            lines.append("")
            lines.append(f"**告警**: {len(metrics.alerts)} 条")
        if metrics.anomalies:
            lines.append(f"**异常**: {len(metrics.anomalies)} 条")
        return "\n".join(lines)

    def generate_growth_section(self, metrics: ReportMetrics) -> dict:
        """生成增长章节。"""
        return {
            "title": "增长分析",
            "content": (
                f"## 增长分析\n\n"
                f"- 总安装: {metrics.total_installs:,} (环比 {metrics.installs_trend:+.1f}%)\n"
                f"- 平均 DAU: {metrics.avg_dau:,} (环比 {metrics.dau_trend:+.1f}%)\n"
                f"- 收入增长: {metrics.revenue_trend:+.1f}%\n"
                f"- 花费变化: {metrics.spend_trend:+.1f}%\n"
                f"- ARPDAU: ${metrics.avg_arpdau:.4f}\n"
                f"- 整体 ROAS: {metrics.overall_roas:.1f}%\n"
            ),
            "data": {
                "installs_trend": metrics.installs_trend,
                "dau_trend": metrics.dau_trend,
                "revenue_trend": metrics.revenue_trend,
                "spend_trend": metrics.spend_trend,
                "arpdau": metrics.avg_arpdau,
                "roas": metrics.overall_roas,
            },
        }

    def generate_monetization_section(self, metrics: ReportMetrics) -> dict:
        """生成变现章节。"""
        return {
            "title": "变现分析",
            "content": (
                f"## 变现分析\n\n"
                f"- 总收入: ${metrics.total_revenue:,.2f} (环比 {metrics.revenue_trend:+.1f}%)\n"
                f"- 总花费: ${metrics.total_spend:,.2f} (环比 {metrics.spend_trend:+.1f}%)\n"
                f"- ARPDAU: ${metrics.avg_arpdau:.4f}\n"
                f"- 整体 ROAS: {metrics.overall_roas:.1f}%\n"
                f"- 净利润: ${metrics.total_revenue - metrics.total_spend:,.2f}\n"
            ),
            "data": {
                "total_revenue": metrics.total_revenue,
                "total_spend": metrics.total_spend,
                "net_profit": metrics.total_revenue - metrics.total_spend,
                "arpdau": metrics.avg_arpdau,
                "roas": metrics.overall_roas,
                "revenue_trend": metrics.revenue_trend,
            },
        }

    def generate_ua_section(self, metrics: ReportMetrics) -> dict:
        """生成 UA 章节。"""
        cpi = (metrics.total_spend / metrics.total_installs) if metrics.total_installs > 0 else 0.0
        return {
            "title": "用户获取 (UA)",
            "content": (
                f"## 用户获取 (UA)\n\n"
                f"- 总安装: {metrics.total_installs:,} (环比 {metrics.installs_trend:+.1f}%)\n"
                f"- 总花费: ${metrics.total_spend:,.2f}\n"
                f"- 平均 CPI: ${cpi:.2f}\n"
                f"- 平均 DAU: {metrics.avg_dau:,}\n"
            ),
            "data": {
                "total_installs": metrics.total_installs,
                "total_spend": metrics.total_spend,
                "cpi": cpi,
                "avg_dau": metrics.avg_dau,
                "installs_trend": metrics.installs_trend,
            },
        }

    def generate_creative_section(self, metrics: ReportMetrics) -> dict:
        """生成创意章节。"""
        top_lines = []
        for i, c in enumerate(metrics.top_creatives[:5], 1):
            name = c.get("name", "unknown")
            ctr = c.get("ctr", 0.0)
            spend = c.get("spend", 0.0)
            top_lines.append(f"| {i} | {name} | {ctr:.2f}% | ${spend:,.2f} |")
        top_table = (
            "| # | 素材 | CTR | 花费 |\n|---|---|---|---|\n"
            + "\n".join(top_lines)
        ) if top_lines else "_暂无 Top 素材_"
        return {
            "title": "创意素材",
            "content": (
                f"## 创意素材\n\n"
                f"{top_table}\n"
            ),
            "data": {
                "top_creatives": metrics.top_creatives[:5],
                "total_creatives": len(metrics.top_creatives),
            },
        }

    def generate_portfolio_section(self, metrics: ReportMetrics) -> dict:
        """生成组合章节。"""
        top_lines = []
        for i, g in enumerate(metrics.top_games[:5], 1):
            name = g.get("name", "unknown")
            revenue = g.get("revenue", 0.0)
            share = g.get("revenue_share", 0.0)
            top_lines.append(f"| {i} | {name} | ${revenue:,.2f} | {share:.1f}% |")
        top_table = (
            "| # | 游戏 | 收入 | 占比 |\n|---|---|---|---|\n"
            + "\n".join(top_lines)
        ) if top_lines else "_暂无 Top 游戏_"
        return {
            "title": "组合俯瞰",
            "content": (
                f"## 组合俯瞰\n\n"
                f"- 总收入: ${metrics.total_revenue:,.2f}\n"
                f"- 总花费: ${metrics.total_spend:,.2f}\n"
                f"- 整体 ROAS: {metrics.overall_roas:.1f}%\n\n"
                f"### Top 游戏\n\n"
                f"{top_table}\n"
            ),
            "data": {
                "top_games": metrics.top_games[:5],
                "total_revenue": metrics.total_revenue,
                "total_spend": metrics.total_spend,
                "roas": metrics.overall_roas,
            },
        }

    def calculate_metrics(
        self,
        start_date: str,
        end_date: str,
        game_ids: list[str] | None = None,
    ) -> ReportMetrics:
        """计算指标汇总.

        本地化实现: 使用基线默认值 + 简单环比扰动, 不调用外部数据源。
        调用方可通过覆写此方法或直接修改返回的 ReportMetrics 来注入真实数据。
        """
        # 推断周期类型
        start_dt = self._parse_date(start_date)
        end_dt = self._parse_date(end_date)
        days = (end_dt - start_dt).days + 1
        if days <= 1:
            period = ReportPeriod.DAILY
        elif days <= 7:
            period = ReportPeriod.WEEKLY
        else:
            period = ReportPeriod.MONTHLY

        baseline = self._DEFAULT_BASELINE.get(period, self._DEFAULT_BASELINE[ReportPeriod.DAILY])

        # 简单扰动: 用 end_date 的日序号作为种子
        seed = end_dt.timetuple().tm_yday
        revenue = baseline["revenue"] * (1.0 + 0.05 * ((seed % 7) - 3) / 3.0)
        spend = baseline["spend"] * (1.0 + 0.04 * ((seed % 5) - 2) / 2.0)
        installs = int(baseline["installs"] * (1.0 + 0.06 * ((seed % 11) - 5) / 5.0))
        dau = int(baseline["dau"] * (1.0 + 0.03 * ((seed % 13) - 6) / 6.0))

        # 环比趋势 (默认值, 调用方可覆写)
        revenue_trend = round(((seed % 13) - 6) * 1.2, 1)
        spend_trend = round(((seed % 7) - 3) * 1.5, 1)
        installs_trend = round(((seed % 11) - 5) * 1.0, 1)
        dau_trend = round(((seed % 9) - 4) * 0.8, 1)

        # 派生指标
        arpdau = round(revenue / dau, 4) if dau > 0 else 0.0
        roas = round((revenue / spend) * 100, 1) if spend > 0 else 0.0

        # Top 游戏 (默认 5 个 mock)
        top_games = self._default_top_games(game_ids, revenue)
        # Top 创意 (默认 5 个 mock)
        top_creatives = self._default_top_creatives()
        # 异常 + 告警
        anomalies: list[dict] = []
        alerts: list[dict] = []
        if roas < 100.0:
            alerts.append({
                "alert_id": "low_roas",
                "severity": "warning",
                "message": f"整体 ROAS {roas:.1f}% 偏低",
                "current_value": roas,
                "threshold": 100.0,
            })
        if revenue_trend < -5.0:
            anomalies.append({
                "type": "revenue_decline",
                "value": revenue_trend,
                "message": f"收入环比下降 {abs(revenue_trend):.1f}%",
            })

        return ReportMetrics(
            period=period,
            start_date=start_date,
            end_date=end_date,
            total_revenue=round(revenue, 2),
            total_spend=round(spend, 2),
            total_installs=installs,
            avg_dau=dau,
            avg_arpdau=arpdau,
            overall_roas=roas,
            revenue_trend=revenue_trend,
            spend_trend=spend_trend,
            installs_trend=installs_trend,
            dau_trend=dau_trend,
            top_games=top_games,
            top_creatives=top_creatives,
            anomalies=anomalies,
            alerts=alerts,
        )

    def get_report(self, report_id: str) -> PeriodReport | None:
        """获取已生成的报告.

        优先从内存缓存读, 再从磁盘加载。
        """
        # 1. 缓存
        if report_id in self._cache:
            return self._cache[report_id]

        # 2. 磁盘
        # report_id 格式: {report_type}_{period}_{end_date}_{short_uuid}
        parts = report_id.split("_")
        if len(parts) < 3:
            return None
        # 兼容 report_type 可能包含下划线? 当前 ReportType 都是单词, 安全
        report_type = parts[0]
        period = parts[1]
        end_date_str = parts[2] if len(parts) >= 4 else ""

        period_dir = self.reports_root / period
        if not period_dir.exists():
            return None

        # 尝试按 report_id 匹配 json 文件
        for json_file in period_dir.glob("*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                if data.get("report_id") == report_id:
                    report = self._report_from_dict(data)
                    if report is not None:
                        self._cache[report_id] = report
                        return report
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("加载报告失败 %s: %s", json_file, e)
                continue
        return None

    def list_reports(
        self,
        period: str | None = None,
        report_type: str | None = None,
    ) -> list[PeriodReport]:
        """列出报告.

        Args:
            period: 按周期过滤 (None = 全部)
            report_type: 按类型过滤 (None = 全部)
        """
        results: list[PeriodReport] = []
        seen_ids: set[str] = set()

        # 决定要遍历的目录
        if period:
            period_dirs = [self.reports_root / period] if ReportPeriod.is_valid(period) else []
        else:
            period_dirs = [self.reports_root / p for p in ReportPeriod.all()]

        for pdir in period_dirs:
            if not pdir.exists():
                continue
            for json_file in sorted(pdir.glob("*.json")):
                try:
                    data = json.loads(json_file.read_text(encoding="utf-8"))
                    if report_type and data.get("report_type") != report_type:
                        continue
                    if data.get("report_id") in seen_ids:
                        continue
                    report = self._report_from_dict(data)
                    if report is None:
                        continue
                    seen_ids.add(report.report_id)
                    results.append(report)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("读取报告 %s 失败: %s", json_file, e)
                    continue
        return results

    def get_stats(self) -> dict:
        """统计信息。"""
        stats = {
            "total_reports": 0,
            "by_period": {p: 0 for p in ReportPeriod.all()},
            "by_type": {t: 0 for t in ReportType.all()},
            "latest_generated_at": "",
        }
        latest_ts = ""
        for report in self.list_reports():
            stats["total_reports"] += 1
            if report.period in stats["by_period"]:
                stats["by_period"][report.period] += 1
            if report.report_type in stats["by_type"]:
                stats["by_type"][report.report_type] += 1
            if report.generated_at > latest_ts:
                latest_ts = report.generated_at
        stats["latest_generated_at"] = latest_ts
        return stats

    # ── 内部辅助方法 ────────────────────────────────────────

    def _calc_start_date(self, end_dt: date, period: str) -> date:
        """根据周期类型计算起始日期。"""
        if period == ReportPeriod.DAILY:
            return end_dt
        if period == ReportPeriod.WEEKLY:
            # 周一作为周起始
            return end_dt - timedelta(days=end_dt.weekday())
        if period == ReportPeriod.MONTHLY:
            return end_dt.replace(day=1)
        raise ValueError(f"无效的 period: {period}")

    def _parse_date(self, date_str: str) -> date:
        """解析 YYYY-MM-DD 字符串为 date。"""
        return date.fromisoformat(date_str)

    def _make_report_id(self, report_type: str, period: str, end_date: str) -> str:
        """生成报告 ID。"""
        short_uuid = uuid.uuid4().hex[:8]
        return f"{report_type}_{period}_{end_date}_{short_uuid}"

    def _build_sections(self, report_type: str, metrics: ReportMetrics) -> list[dict]:
        """根据报告类型组装章节列表。"""
        sections: list[dict] = []
        if report_type == ReportType.EXECUTIVE:
            sections.append(self.generate_growth_section(metrics))
            sections.append(self.generate_monetization_section(metrics))
            sections.append(self.generate_ua_section(metrics))
            sections.append(self.generate_creative_section(metrics))
            sections.append(self.generate_portfolio_section(metrics))
        elif report_type == ReportType.GROWTH:
            sections.append(self.generate_growth_section(metrics))
            sections.append(self.generate_ua_section(metrics))
        elif report_type == ReportType.MONETIZATION:
            sections.append(self.generate_monetization_section(metrics))
            sections.append(self.generate_portfolio_section(metrics))
        elif report_type == ReportType.UA:
            sections.append(self.generate_ua_section(metrics))
            sections.append(self.generate_creative_section(metrics))
        elif report_type == ReportType.CREATIVE:
            sections.append(self.generate_creative_section(metrics))
        elif report_type == ReportType.PORTFOLIO:
            sections.append(self.generate_portfolio_section(metrics))
            sections.append(self.generate_growth_section(metrics))
            sections.append(self.generate_monetization_section(metrics))
        return sections

    def _build_summary(self, report_type: str, metrics: ReportMetrics) -> str:
        """生成非 executive 报告的简短摘要。"""
        type_labels = {
            ReportType.GROWTH: "增长报告",
            ReportType.MONETIZATION: "变现报告",
            ReportType.UA: "用户获取报告",
            ReportType.CREATIVE: "创意素材报告",
            ReportType.PORTFOLIO: "组合报告",
        }
        label = type_labels.get(report_type, "报告")
        return (
            f"## {label} ({metrics.period})\n\n"
            f"**周期**: {metrics.start_date} ~ {metrics.end_date}\n\n"
            f"**核心数据**: 收入 ${metrics.total_revenue:,.2f} · "
            f"花费 ${metrics.total_spend:,.2f} · "
            f"安装 {metrics.total_installs:,} · "
            f"DAU {metrics.avg_dau:,} · "
            f"ROAS {metrics.overall_roas:.1f}%"
        )

    def _build_recommendations(self, report_type: str, metrics: ReportMetrics) -> list[str]:
        """生成行动建议。"""
        recs: list[str] = []
        if metrics.revenue_trend < 0:
            recs.append(f"收入环比下降 {abs(metrics.revenue_trend):.1f}%, 建议排查 top 游戏变现异常")
        if metrics.spend_trend > 10:
            recs.append(f"花费环比上升 {metrics.spend_trend:.1f}%, 关注 CPI 与 ROAS 表现")
        if metrics.overall_roas < 100.0:
            recs.append("整体 ROAS 低于 100%, 建议优化买量结构或暂停低效投放")
        if metrics.installs_trend > 15:
            recs.append("安装增长强劲, 可适度加大预算捕捉增长窗口")
        if not recs:
            recs.append("各项指标平稳, 维持当前策略并持续观察")
        return recs

    def _default_top_games(self, game_ids: list[str] | None, total_revenue: float) -> list[dict]:
        """生成默认 Top 游戏列表 (mock)。"""
        ids = game_ids if game_ids else [
            "demo_game_000", "demo_game_001", "demo_game_002",
            "demo_game_003", "demo_game_004",
        ]
        weights = [0.30, 0.22, 0.18, 0.16, 0.14]
        # 补齐权重
        while len(weights) < len(ids):
            weights.append(0.05)
        # 归一化
        total_w = sum(weights[:len(ids)])
        games = []
        for i, gid in enumerate(ids):
            w = weights[i] / total_w
            revenue = total_revenue * w
            games.append({
                "game_id": gid,
                "name": gid,
                "revenue": round(revenue, 2),
                "revenue_share": round(w * 100, 1),
            })
        # 按收入降序
        games.sort(key=lambda g: g["revenue"], reverse=True)
        return games

    def _default_top_creatives(self) -> list[dict]:
        """生成默认 Top 创意素材列表 (mock)。"""
        return [
            {"creative_id": f"cr_{i:03d}", "name": f"MW_VIDEO_{i:03d}", "ctr": round(2.0 + i * 0.4, 2), "spend": round(120.0 + i * 35, 2)}
            for i in range(1, 6)
        ]

    def _trend_emoji(self, trend: float) -> str:
        """趋势 emoji。"""
        if trend > 1.0:
            return "📈"
        if trend < -1.0:
            return "📉"
        return "➡️"

    def _compute_md_path(self, report: PeriodReport) -> Path:
        """计算报告 Markdown 文件路径。"""
        period_dir = self.reports_root / report.period
        base_name = f"{report.end_date}.{report.report_type}"
        return period_dir / f"{base_name}.md"

    def _persist_report(self, report: PeriodReport) -> Path:
        """持久化报告到磁盘 (Markdown + JSON)。"""
        period_dir = self.reports_root / report.period
        period_dir.mkdir(parents=True, exist_ok=True)

        # 文件名: {end_date}.{report_type}.{ext}
        base_name = f"{report.end_date}.{report.report_type}"

        # Markdown
        md_path = period_dir / f"{base_name}.md"
        md_path.write_text(self._render_markdown(report), encoding="utf-8")

        # JSON (用于 list/get 接口)
        json_path = period_dir / f"{base_name}.json"
        json_path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return md_path

    def _render_markdown(self, report: PeriodReport) -> str:
        """渲染 Markdown 输出。"""
        type_labels = {
            ReportType.EXECUTIVE: "高管摘要",
            ReportType.GROWTH: "增长报告",
            ReportType.MONETIZATION: "变现报告",
            ReportType.UA: "用户获取报告",
            ReportType.CREATIVE: "创意素材报告",
            ReportType.PORTFOLIO: "组合报告",
        }
        period_labels = {
            ReportPeriod.DAILY: "日报",
            ReportPeriod.WEEKLY: "周报",
            ReportPeriod.MONTHLY: "月报",
        }
        title_label = type_labels.get(report.report_type, "报告")
        period_label = period_labels.get(report.period, "报告")
        lines = [
            f"# {title_label} · {period_label} · {report.end_date}",
            "",
            f"_报告周期_: {report.start_date} ~ {report.end_date}",
            f"_生成时间_: {report.generated_at}",
            f"_报告 ID_: `{report.report_id}`",
            "",
            "---",
            "",
            report.summary,
            "",
        ]
        # 各章节
        for section in report.sections:
            lines.append(section.get("content", ""))
            lines.append("")

        # 推荐建议
        if report.recommendations:
            lines.append("## 行动建议")
            lines.append("")
            for i, rec in enumerate(report.recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        # 告警 / 异常
        m = report.metrics
        if m.alerts:
            lines.append("## 告警")
            lines.append("")
            for a in m.alerts:
                lines.append(f"- **{a.get('alert_id', '')}** ({a.get('severity', 'info')}): {a.get('message', '')}")
            lines.append("")
        if m.anomalies:
            lines.append("## 异常")
            lines.append("")
            for a in m.anomalies:
                lines.append(f"- {a.get('type', '')}: {a.get('message', '')}")
            lines.append("")

        lines.append("---")
        lines.append("_由 PeriodReportGenerator 自动生成 · 完全本地化, 无外部 API 调用_")
        return "\n".join(lines)

    def _report_from_dict(self, data: dict) -> PeriodReport | None:
        """从字典重建 PeriodReport。"""
        try:
            metrics_data = data.get("metrics", {})
            metrics = ReportMetrics(
                period=metrics_data.get("period", ""),
                start_date=metrics_data.get("start_date", ""),
                end_date=metrics_data.get("end_date", ""),
                total_revenue=metrics_data.get("total_revenue", 0.0),
                total_spend=metrics_data.get("total_spend", 0.0),
                total_installs=metrics_data.get("total_installs", 0),
                avg_dau=metrics_data.get("avg_dau", 0),
                avg_arpdau=metrics_data.get("avg_arpdau", 0.0),
                overall_roas=metrics_data.get("overall_roas", 0.0),
                revenue_trend=metrics_data.get("revenue_trend", 0.0),
                spend_trend=metrics_data.get("spend_trend", 0.0),
                installs_trend=metrics_data.get("installs_trend", 0.0),
                dau_trend=metrics_data.get("dau_trend", 0.0),
                top_games=metrics_data.get("top_games", []),
                top_creatives=metrics_data.get("top_creatives", []),
                anomalies=metrics_data.get("anomalies", []),
                alerts=metrics_data.get("alerts", []),
            )
            return PeriodReport(
                report_id=data["report_id"],
                report_type=data["report_type"],
                period=data["period"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                metrics=metrics,
                sections=data.get("sections", []),
                summary=data.get("summary", ""),
                recommendations=data.get("recommendations", []),
                generated_at=data.get("generated_at", ""),
                file_path=data.get("file_path", ""),
            )
        except (KeyError, TypeError) as e:
            logger.warning("重建 PeriodReport 失败: %s", e)
            return None
