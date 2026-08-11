"""P3.2 — CEO Daily Report（Presentation + Action Orchestration Layer）。

只聚合、转换、编排，不重算、不决策、不调 Provider、不绕 Approval、不改 Decision。
"""
from __future__ import annotations

from .action_formatter import ActionFormatter, format_actions
from .builder import CEOReportBuilder, build_ceo_report, write_outputs
from .models import (
    ACTION_STATE_TITLE,
    ActionState,
    CEOAction,
    CEOActionStatus,
    CEODailyReport,
    ExecutionSummary,
    HealthSummary,
    OpportunityItem,
    RiskItem,
)
from .renderer import (
    render_actions_json,
    render_markdown,
    render_report_json,
)

__all__ = [
    "ActionState",
    "CEOActionStatus",
    "ACTION_STATE_TITLE",
    "CEOAction",
    "HealthSummary",
    "OpportunityItem",
    "RiskItem",
    "ExecutionSummary",
    "CEODailyReport",
    "ActionFormatter",
    "format_actions",
    "CEOReportBuilder",
    "build_ceo_report",
    "write_outputs",
    "render_markdown",
    "render_report_json",
    "render_actions_json",
]
