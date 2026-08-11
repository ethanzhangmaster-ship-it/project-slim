"""E17.8 — JsonlSimulationStore：模拟报告 JSONL 落盘。

沿用 E16 / E17 Jsonl*Store 模式：append-only、容错解析（坏行跳过）、
默认路径 data/ceo/simulation_runs.jsonl。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .models import PortfolioSimulationReport


class JsonlSimulationStore:
    """组合模拟报告的 JSONL 持久化。"""

    def __init__(self, path: str = "data/ceo/simulation_runs.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, report: PortfolioSimulationReport) -> None:
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(report.to_dict(), ensure_ascii=False) + "\n")

    def all(self) -> List[PortfolioSimulationReport]:
        if not self.path.exists():
            return []
        out: List[PortfolioSimulationReport] = []
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(PortfolioSimulationReport.from_dict(json.loads(line)))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
        return out

    def latest(self) -> PortfolioSimulationReport | None:
        rows = self.all()
        return rows[-1] if rows else None


__all__ = ["JsonlSimulationStore"]
