"""E17.9 — Operator Memory（运营日记忆，跨日环比）。

JSONL append-only（与 E16/E17 各 Jsonl*Store 同纪律）：
- record(day_record)             追加一天的运营记录
- latest_before(date)            取 date 之前最近一天（晨报「昨天 vs 今天」）
- get(date)                      取某天记录（幂等判断：今天是否已跑过）
- history(limit)                 最近 N 天

默认落盘 data/ceo/operator_memory.jsonl。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .models import OperatorDayRecord

DEFAULT_PATH = "data/ceo/operator_memory.jsonl"


class JsonlOperatorMemory:
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = Path(path)

    # ------------------------------------------------------------------ #
    def record(self, day: OperatorDayRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(day.to_dict(), ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------ #
    def _load(self) -> List[OperatorDayRecord]:
        if not self.path.exists():
            return []
        out: List[OperatorDayRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(OperatorDayRecord.from_dict(json.loads(line)))
            except Exception:
                continue  # 容错：坏行跳过
        return out

    def get(self, date: str) -> Optional[OperatorDayRecord]:
        """同日多条时取最后一条（append-only，后写覆盖语义）。"""
        found: Optional[OperatorDayRecord] = None
        for r in self._load():
            if r.date == date:
                found = r
        return found

    def latest_before(self, date: str) -> Optional[OperatorDayRecord]:
        """date 之前（不含当日）最近一天的记录。ISO 日期字符串可直接比较。"""
        best: Optional[OperatorDayRecord] = None
        for r in self._load():
            if r.date < date and (best is None or r.date >= best.date):
                best = r
        return best

    def history(self, limit: int = 30) -> List[OperatorDayRecord]:
        """按日期升序的最近 limit 天（同日取最后一条）。"""
        by_date: Dict[str, OperatorDayRecord] = {}
        for r in self._load():
            by_date[r.date] = r
        rows = [by_date[k] for k in sorted(by_date)]
        return rows[-limit:] if limit > 0 else rows


__all__ = ["JsonlOperatorMemory", "DEFAULT_PATH"]
