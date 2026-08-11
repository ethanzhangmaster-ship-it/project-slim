"""P3.1 — Growth Operator Scheduler（每日循环唯一入口）。

责任边界（不可越界）：
- 只负责：幂等守卫 / 编排调用 / 异常兜底 / 运行状态落盘。
- 不负责：决策（E17.3）、执行动作（P2.4 唯一出口）、修改策略（P3.3）、
  真实定时触发（外部 cron / WorkBuddy automation / Windows 任务计划）。

幂等：同日已有 COMPLETED/PARTIAL 记录 → 返回 SKIPPED（force=True 重跑）。
run_id 确定性生成：op-<date>-<当日序号>。
"""
from __future__ import annotations

from typing import Optional

from .context import OperatorContext
from .models import (
    OperatorRunResult,
    RunStatus,
    STAGE_FAILED,
    StageResult,
)
from .pipeline import DailyOperatorPipeline
from .state import OperatorRunStore


class GrowthOperatorScheduler:
    def __init__(
        self,
        context: OperatorContext,
        run_store: Optional[OperatorRunStore] = None,
        pipeline: Optional[DailyOperatorPipeline] = None,
    ):
        self.ctx = context
        self.run_store = run_store or OperatorRunStore()
        self.pipeline = pipeline or DailyOperatorPipeline(context)

    # ------------------------------------------------------------------ #
    def run_daily_cycle(
        self, business_date: str, force: bool = False
    ) -> OperatorRunResult:
        """唯一入口：一条命令跑完整每日增长经营流程。"""
        # 1) 幂等门（P3.1 单一幂等源）
        if not force and self.run_store.has_completed(business_date):
            prev = self.run_store.get(business_date) or {}
            return OperatorRunResult(
                run_id=prev.get("run_id", f"op-{business_date}-0"),
                date=business_date,
                status=RunStatus.SKIPPED,
                report_id=prev.get("report_id", ""),
                summary={
                    "reason": "当日已运行（幂等拦截）",
                    "previous_status": prev.get("status", ""),
                },
            )

        run_id = f"op-{business_date}-{self.run_store.runs_on(business_date) + 1}"

        # 2) 编排（pipeline 内部逐阶段兜底；此处兜底编排层自身异常）
        try:
            stages, agg = self.pipeline.execute(business_date, run_id=run_id)
            failed = [s for s in stages if s.status == STAGE_FAILED]
            status = RunStatus.PARTIAL if failed else RunStatus.COMPLETED
            result = OperatorRunResult(
                run_id=run_id,
                date=business_date,
                status=status,
                stages=stages,
                decisions=agg.get("decisions", {}),
                executions=agg.get("executions", {}),
                errors=[f"{s.stage}: {s.detail}" for s in failed],
                report_id=agg.get("report_path", ""),
                real_api_called=bool(agg.get("real_api_called", False)),
                summary=agg.get("summary", {}),
            )
        except Exception as exc:  # noqa: BLE001 — 最终兜底，绝不裸抛
            result = OperatorRunResult(
                run_id=run_id,
                date=business_date,
                status=RunStatus.FAILED,
                errors=[f"pipeline: {type(exc).__name__}: {exc}"],
            )

        # 3) 运行结束（含失败）必写状态
        self.run_store.record(result)
        return result


__all__ = ["GrowthOperatorScheduler"]
