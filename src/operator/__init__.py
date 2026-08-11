"""P3.1 Daily Operator Scheduler — 包入口。

把 P1（真实数据）+ E17（决策脑）+ P2（执行链）编排成一条命令可重复运行的
每日增长经营流程（Operating Loop）。薄编排层：复用不重写。

用法：
    from src.operator import build_growth_operator

    scheduler = build_growth_operator(company=company)   # 或 hub=/game_ids=
    result = scheduler.run_daily_cycle("2026-07-30")
"""
from __future__ import annotations

from typing import Any, Optional

from .context import OperatorContext, build_operator_context
from .models import (
    ALL_STAGES,
    OperatorRunResult,
    RunStatus,
    STAGE_CEO_REPORT,
    STAGE_FAILED,
    STAGE_MEMORY,
    STAGE_OK,
    STAGE_SKIPPED,
    STAGE_STRATEGY,
    StageResult,
)
from .pipeline import DailyOperatorPipeline
from .scheduler import GrowthOperatorScheduler
from .state import OperatorRunStore


def build_growth_operator(
    *,
    run_store: Optional[OperatorRunStore] = None,
    **context_kwargs: Any,
) -> GrowthOperatorScheduler:
    """一键装配：context → pipeline → scheduler。

    context_kwargs 透传 build_operator_context（company/hub/game_ids/mode/...）。
    """
    ctx = build_operator_context(**context_kwargs)
    return GrowthOperatorScheduler(ctx, run_store=run_store)


__all__ = [
    "OperatorContext",
    "build_operator_context",
    "OperatorRunResult",
    "StageResult",
    "RunStatus",
    "ALL_STAGES",
    "STAGE_OK",
    "STAGE_SKIPPED",
    "STAGE_FAILED",
    "STAGE_MEMORY",
    "STAGE_STRATEGY",
    "STAGE_CEO_REPORT",
    "DailyOperatorPipeline",
    "GrowthOperatorScheduler",
    "OperatorRunStore",
    "build_growth_operator",
]
