from __future__ import annotations

from market_ops.config import Settings
from market_ops.executive_report import ExecutiveReportBuilder


class FinalExecutiveReportBuilder(ExecutiveReportBuilder):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
