"""E17.10 — Portfolio Dashboard 主入口（Agent）。

E17 的最后一块拼图：把 E17.1–E17.9 的产物折叠成一张 CEO 组合俯瞰图。

三种用法：
    agent = PortfolioDashboardAgent()

    # 1) 已有 E17.9 DailyRunResult（推荐：复用不重算）
    dash = agent.from_daily_run(company, result, memory_graph=graph)

    # 2) 手动喂上游产物（测试友好）
    dash = agent.build(company, date=..., dec_report=..., sim_report=...,
                       priorities=..., actions=..., memory_graph=...)

    # 3) 一键端到端：内部跑 E17.9 pipeline 再渲染落盘
    dash, paths = agent.run(company, date, memory_graph=graph)

Lean 纪律：输出是文件（Markdown + 自包含 HTML + JSON），无服务器、无框架。
确定性：同输入同输出；不依赖 audit_id。
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from src.ceo_intelligence.daily_operator.agent import DailyGrowthOperatorAgent
from src.ceo_intelligence.daily_operator.memory import JsonlOperatorMemory
from src.ceo_intelligence.daily_operator.pipeline import DailyGrowthPipeline
from .aggregator import PortfolioAggregator
from .models import PortfolioDashboard
from .notifier import FileNotifier
from .reporter import PortfolioReporter


class PortfolioDashboardAgent:
    def __init__(
        self,
        aggregator: Optional[PortfolioAggregator] = None,
        reporter: Optional[PortfolioReporter] = None,
        notifier: Optional[FileNotifier] = None,
    ) -> None:
        self.aggregator = aggregator or PortfolioAggregator()
        self.reporter = reporter or PortfolioReporter()
        self.notifier = notifier or FileNotifier()

    # ------------------------------------------------------------------ #
    def build(
        self,
        company: Any,
        *,
        date: str,
        dec_report: Any = None,
        sim_report: Any = None,
        priorities: Optional[List[Any]] = None,
        actions: Optional[List[Any]] = None,
        memory_graph: Any = None,
    ) -> PortfolioDashboard:
        """从上游产物直接聚合（无 IO）。"""
        return self.aggregator.aggregate(
            company,
            date=date,
            dec_report=dec_report,
            sim_report=sim_report,
            priorities=priorities,
            actions=actions,
            memory_graph=memory_graph,
        )

    def from_daily_run(
        self, company: Any, result: Any, *, memory_graph: Any = None
    ) -> PortfolioDashboard:
        """从 E17.9 DailyRunResult 聚合（复用其进程内原始产物引用）。"""
        return self.build(
            company,
            date=result.date,
            dec_report=result.dec_report,
            sim_report=result.sim_report,
            priorities=result.priorities,
            actions=result.actions,
            memory_graph=memory_graph,
        )

    def run(
        self,
        company: Any,
        date: str,
        *,
        memory_graph: Any = None,
        operator: Optional[DailyGrowthOperatorAgent] = None,
        operator_memory: Optional[JsonlOperatorMemory] = None,
        notify: bool = True,
        force: bool = True,
    ) -> Tuple[PortfolioDashboard, List[str]]:
        """一键端到端：跑 E17.9 pipeline → 聚合 → 渲染落盘。

        返回 (dashboard, 落盘路径列表)。notify=False 时不落盘。
        operator 可注入（测试隔离：自带 tmp 路径的 pipeline/memory）。
        """
        operator = operator or DailyGrowthOperatorAgent(
            pipeline=DailyGrowthPipeline(memory_graph=memory_graph),
            operator_memory=operator_memory or JsonlOperatorMemory(),
        )
        result = operator.run_daily_for_company(company, date, force=force)
        if result is None:  # 幂等挡下（force=False 且当日已跑）
            dash = self.build(company, date=date, memory_graph=memory_graph)
        else:
            dash = self.from_daily_run(company, result, memory_graph=memory_graph)
        paths = self.notifier.notify(dash) if notify else []
        return dash, paths


__all__ = ["PortfolioDashboardAgent"]
