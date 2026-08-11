"""P3.1 — Operator Run Store（防重复运行守卫，JSONL append-only）。

与 E17.9 JsonlOperatorMemory / P2.3 JsonlApprovalStore 同纪律：
- 只追加，不改写；同日多条 latest-wins
- 坏行容错跳过

与 E17.9 DailyScheduler 的分工（单一幂等源）：
- E17.9 幂等门管「E17 循环当日跑没跑」——P3.1 调它时恒 force=True；
- 本 Store 管「P3.1 全 11 阶段当日跑没跑」，是 P3.1 唯一幂等判据。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .models import OperatorRunResult, RunStatus

DEFAULT_PATH = "data/operator/runs.jsonl"

# 视为「当日已完成」的状态（SKIPPED/FAILED 不算，允许重跑）
_COMPLETED_STATES = (RunStatus.COMPLETED.value, RunStatus.PARTIAL.value)


class OperatorRunStore:
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = Path(path)

    # ------------------------------------------------------------------ #
    def record(self, result: OperatorRunResult) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------ #
    def _load(self) -> List[dict]:
        if not self.path.exists():
            return []
        rows: List[dict] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue  # 坏行容错
        return rows

    def get(self, date: str) -> Optional[dict]:
        """同日取最后一条（latest-wins）。"""
        found: Optional[dict] = None
        for r in self._load():
            if r.get("date") == date:
                found = r
        return found

    def has_completed(self, date: str) -> bool:
        """当日是否已有 COMPLETED / PARTIAL 记录（幂等判据）。"""
        row = self.get(date)
        return bool(row) and row.get("status") in _COMPLETED_STATES

    def runs_on(self, date: str) -> int:
        """当日已有的运行记录条数（用于确定性 run_id 序号）。"""
        return sum(1 for r in self._load() if r.get("date") == date)

    def history(self, limit: int = 30) -> List[dict]:
        """按日期升序的最近 limit 天（同日取最后一条）。"""
        by_date: Dict[str, dict] = {}
        for r in self._load():
            d = r.get("date", "")
            if d:
                by_date[d] = r
        rows = [by_date[k] for k in sorted(by_date)]
        return rows[-limit:] if limit > 0 else rows


__all__ = ["OperatorRunStore", "DEFAULT_PATH"]
