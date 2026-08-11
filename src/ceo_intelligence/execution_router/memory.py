"""E17.6 — Execution Memory：Decision → Strategy → Execution → Result 闭环记录。

JSONL append-only（data/ceo/execution_memory.jsonl），供 E17.7 Growth Memory Graph
沉淀"哪些执行链路真的赚了钱"。与 E16.1 RevenueExperienceStore / E17.2
OpportunityMemory 同一闭环思想，粒度为单个 ExecutionAction。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .models import ExecutionExperience


class ExecutionMemory:
    """执行经验存取（逐动作 JSONL）。"""

    def __init__(self, path: str = "data/ceo/execution_memory.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, exp: ExecutionExperience) -> None:
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(exp.to_dict(), ensure_ascii=False) + "\n")

    def all(self) -> List[ExecutionExperience]:
        if not self.path.exists():
            return []
        out: List[ExecutionExperience] = []
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(ExecutionExperience.from_dict(json.loads(line)))
                except (json.JSONDecodeError, KeyError):
                    continue
        return out

    def for_game(self, game_id: str) -> List[ExecutionExperience]:
        return [e for e in self.all() if e.game_id == game_id]

    def for_execution(self, execution_id: str) -> List[ExecutionExperience]:
        return [e for e in self.all() if e.execution_id == execution_id]

    def success_rate(self, domain: str, action_type: Optional[str] = None) -> float:
        """按域（可选按动作类型）的历史成功率；无样本返回 0.0。"""
        rows = [
            e for e in self.all()
            if e.domain == domain and (action_type is None or e.action_type == action_type)
        ]
        if not rows:
            return 0.0
        return sum(1 for e in rows if e.success) / len(rows)

    def stats(self) -> Dict[str, int]:
        rows = self.all()
        return {
            "total": len(rows),
            "success": sum(1 for e in rows if e.success),
            "rolled_back": sum(1 for e in rows if e.rolled_back),
        }


__all__ = ["ExecutionMemory"]
