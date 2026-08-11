"""E17.9 — Daily Growth Operator 主入口（Agent）。

一键 CEO Daily Run：
  Reality(E17.1) → Opportunity(E17.2) → Decision(E17.3) → Strategy(E17.4)
  → Simulation 闸门(E17.8) → Execution(E17.6，仅 EXECUTE+PASS 自动)
  → Priority Top10 → 晨报三版本 → 通知落盘 → Operator Memory（跨日环比）

对外 API：
    op = DailyGrowthOperatorAgent(hub=GrowthRealityHub([...]), ...)
    result = op.run_daily(game_ids, date)          # 从数据源起跑
    result = op.run_daily_for_company(company, date)  # 已有快照直接跑（测试友好）

安全铁律：
- 只有 EXECUTE 决策 + 模拟 PASS 才自动执行（AUTO）；
- APPROVE / REVIEW → 等待审批；BLOCK → 阻断；OBSERVE/REJECT 不落地。
- SIM 纪律：默认全 SIM，summary.real_api_called 恒 False。

幂等：同日已跑过则直接返回 None（force=True 强制重跑）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .memory import JsonlOperatorMemory
from .models import (
    ActionKind,
    DailyRunResult,
    OperatorDayRecord,
    classify_company,
)
from .notifier import FileNotifier, Notifier
from .pipeline import DailyGrowthPipeline
from .ranking import rank_priorities
from .reporter import MorningReporter
from .scheduler import DailyScheduler

AUDIENCES = ("ceo", "ua", "product")


class DailyGrowthOperatorAgent:
    def __init__(
        self,
        hub=None,
        pipeline: Optional[DailyGrowthPipeline] = None,
        reporter: Optional[MorningReporter] = None,
        notifier: Optional[Notifier] = None,
        operator_memory: Optional[JsonlOperatorMemory] = None,
        top_n: int = 10,
        audiences: tuple = AUDIENCES,
    ):
        self.hub = hub
        self.pipeline = pipeline or DailyGrowthPipeline()
        self.reporter = reporter or MorningReporter()
        self.notifier = notifier or FileNotifier()
        self.operator_memory = operator_memory or JsonlOperatorMemory()
        self.scheduler = DailyScheduler(memory=self.operator_memory)
        self.top_n = top_n
        self.audiences = audiences

    # ------------------------------------------------------------------ #
    def run_daily(
        self, game_ids: List[str], date: str, force: bool = False
    ) -> Optional[DailyRunResult]:
        """从数据源起跑（需要构造时传入 hub=GrowthRealityHub）。"""
        if self.hub is None:
            raise ValueError("run_daily 需要 hub=GrowthRealityHub；"
                             "或改用 run_daily_for_company(company, date)")
        if not self.scheduler.should_run(date, force=force):
            return None  # 幂等：今天已经跑过
        company = self.hub.refresh(game_ids, date)
        return self._run(company, date)

    def run_daily_for_company(
        self, company, date: str, force: bool = False
    ) -> Optional[DailyRunResult]:
        """已有 CompanySnapshot 直接跑（测试/回放友好）。"""
        if not self.scheduler.should_run(date, force=force):
            return None
        return self._run(company, date)

    # ------------------------------------------------------------------ #
    def _run(self, company, date: str) -> DailyRunResult:
        dec_report, portfolio, sim_report, exec_reports, actions = (
            self.pipeline.run(company, created_at=date)
        )

        status = classify_company(company)
        priorities = rank_priorities(dec_report, sim_report, top_n=self.top_n)

        # 今日运营记录（先算，再给晨报做「昨天 vs 今天」）
        auto = [a for a in actions if a.kind == ActionKind.AUTO]
        approval = [a for a in actions if a.kind == ActionKind.APPROVAL]
        blocked = [a for a in actions if a.kind == ActionKind.BLOCK]
        auto_ids = {a.decision_audit_id for a in auto}
        revenue_impact = round(
            sum(
                d.expected_value
                for d in dec_report.decisions
                if d.audit_id in auto_ids
            ),
            6,
        )
        real_api = bool(
            sim_report.summary.get("real_api_called", False)
            or any(
                r.summary.get("real_api_called", False) for r in exec_reports
            )
        )
        today = OperatorDayRecord(
            date=date,
            decisions=len(dec_report.decisions),
            executed=len(auto),
            approved=len(approval),
            blocked=len(blocked),
            observed=int(dec_report.summary.get("observe", 0)),
            revenue_impact=revenue_impact,
            top_game=priorities[0].game_id if priorities else "",
            company_status=status.value,
            real_api_called=real_api,
        )
        yesterday = self.operator_memory.latest_before(date)

        reports = self.reporter.build_all(
            date, company, status, priorities, actions,
            yesterday=yesterday, today=today,
        )
        reports = {k: v for k, v in reports.items() if k in self.audiences}

        notified = [
            self.notifier.notify(date, audience, md)
            for audience, md in reports.items()
        ]
        self.operator_memory.record(today)

        return DailyRunResult(
            date=date,
            company_status=status,
            priorities=priorities,
            actions=actions,
            reports=reports,
            record=today,
            notified_paths=notified,
            summary={
                "decisions": today.decisions,
                "auto": today.executed,
                "approval": today.approved,
                "blocked": today.blocked,
                "observed": today.observed,
                "revenue_impact": today.revenue_impact,
                "company_status": status.value,
                "yesterday": yesterday.to_dict() if yesterday else None,
                "real_api_called": real_api,
            },
            dec_report=dec_report,
            portfolio=portfolio,
            sim_report=sim_report,
            exec_reports=exec_reports,
        )


__all__ = ["DailyGrowthOperatorAgent", "AUDIENCES"]
