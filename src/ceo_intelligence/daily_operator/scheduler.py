"""E17.9 — Daily Scheduler（幂等门 + 运行窗口）。

真正的定时触发由外部（WorkBuddy automation / cron / Windows 任务计划）负责；
本模块只回答两个确定性问题：
1. should_run(date)：今天是否还没跑过？（幂等：同日重复触发不重跑，除非 force）
2. next_run_date(date)：下一次应跑的日期（date + 1 天）

无 LLM、无网络；仅读 OperatorMemory。
"""
from __future__ import annotations

from datetime import date as _date, timedelta
from typing import Optional

from .memory import JsonlOperatorMemory


class DailyScheduler:
    def __init__(self, memory: Optional[JsonlOperatorMemory] = None):
        self.memory = memory or JsonlOperatorMemory()

    def has_run(self, date: str) -> bool:
        return self.memory.get(date) is not None

    def should_run(self, date: str, force: bool = False) -> bool:
        """幂等门：同日已有记录则不再跑（force=True 强制重跑）。"""
        if force:
            return True
        return not self.has_run(date)

    @staticmethod
    def next_run_date(date: str) -> str:
        """ISO 日期 + 1 天。"""
        d = _date.fromisoformat(date)
        return (d + timedelta(days=1)).isoformat()


__all__ = ["DailyScheduler"]
