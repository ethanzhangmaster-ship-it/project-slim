"""E17.4 — 策略记忆（Strategy Memory）。

闭环：Decision → Strategy → Result。
复用既有记忆系统的「历史成功 → 置信度加成」思想（E17.2 OpportunityMemory / E16 Experience Store），
新增独立 append-only 存储：data/ceo/strategy_memory.jsonl。

记录示例（spec）：
    Merge 游戏 / 美国 / Creative Refresh / 策略 UGC+真人开场 / 结果 ROAS +23%
    → 未来同 (game_id, strategy_type) 自动优先、置信度加成。

可选接入 E17.3 DecisionMemory 做跨层闭环（仅在提供真实 before/after 指标时写入，
避免用占位 0 值污染 E16 经验库的成功率统计）。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class StrategyMemoryRecord:
    game_id: str
    strategy_type: str
    objective: str
    outcome_impact: float  # +0.23 = ROAS +23%
    notes: str = ""
    timestamp: str = ""

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, object]) -> "StrategyMemoryRecord":
        return cls(
            game_id=str(d["game_id"]),
            strategy_type=str(d["strategy_type"]),
            objective=str(d.get("objective", "")),
            outcome_impact=float(d.get("outcome_impact", 0.0)),
            notes=str(d.get("notes", "")),
            timestamp=str(d.get("timestamp", "")),
        )


class StrategyMemory:
    def __init__(
        self,
        path: str = "data/ceo/strategy_memory.jsonl",
        decision_memory=None,  # Optional[DecisionMemory]
    ):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.decision_memory = decision_memory

    # ------------------------------------------------------------------ #
    def add(self, rec: StrategyMemoryRecord) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")

    def _all(self) -> List[StrategyMemoryRecord]:
        if not self.path.exists():
            return []
        out: List[StrategyMemoryRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            out.append(StrategyMemoryRecord.from_dict(json.loads(line)))
        return out

    def records_for(
        self, strategy_type: str, game_id: Optional[str] = None
    ) -> List[StrategyMemoryRecord]:
        recs = [r for r in self._all() if r.strategy_type == strategy_type]
        if game_id is not None:
            recs = [r for r in recs if r.game_id == game_id]
        return recs

    # ------------------------------------------------------------------ #
    # 置信度加成：相似历史成功（≥2 样本且成功率≥0.8）→ 加成（封顶 0.20）
    # ------------------------------------------------------------------ #
    def confidence_boost(
        self, base_conf: float, game_id: str, strategy_type: str
    ) -> float:
        recs = self.records_for(strategy_type, game_id)
        if len(recs) < 2:
            return base_conf
        success = sum(1 for r in recs if r.outcome_impact > 0)
        rate = success / len(recs)
        if rate >= 0.8:
            return min(0.99, round(base_conf + min(0.20, rate * 0.15), 4))
        return base_conf

    # ------------------------------------------------------------------ #
    def record_outcome(
        self,
        *,
        game_id: str,
        strategy_type: str,
        objective: str,
        outcome_impact: float,
        notes: str = "",
    ) -> None:
        """记录「决策→策略→结果」闭环。"""
        self.add(
            StrategyMemoryRecord(
                game_id=game_id,
                strategy_type=strategy_type,
                objective=objective,
                outcome_impact=outcome_impact,
                notes=notes,
            )
        )

    def record_experience(
        self,
        *,
        game_id: str,
        strategy_type: str,
        objective: str,
        outcome_impact: float,
        before_revenue: float,
        after_revenue: float,
        before_roas: float,
        after_roas: float,
        notes: str = "",
    ) -> None:
        """可选跨层闭环：把真实结果也沉淀进 E17.3 DecisionMemory 经验库。

        仅在调用方提供真实 before/after 指标时调用，避免占位 0 值污染成功率统计。
        """
        self.record_outcome(
            game_id=game_id,
            strategy_type=strategy_type,
            objective=objective,
            outcome_impact=outcome_impact,
            notes=notes,
        )
        if self.decision_memory is not None:
            self.decision_memory.record_outcome(
                game_id=game_id,
                action=strategy_type,
                reason=objective,
                before_revenue=before_revenue,
                after_revenue=after_revenue,
                before_roas=before_roas,
                after_roas=after_roas,
            )
