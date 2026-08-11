"""E17.2 机会记忆（OpportunityMemory）。

复用既有 Pattern Memory / Revenue Experience / ASO Memory 的「闭环学习」思想：
记录 发现机会 → 采取行动 → 结果，使相似情况未来置信度提升。

存储：data/ceo/opportunity_memory.jsonl（逐条追加，append-only）
键： (type, segment)  —— 例：「Merge 类 / 美国市场 / CREATIVE_REFRESH」成功 → 置信度加成
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class OpportunityMemoryRecord:
    game_id: str
    type: str  # OpportunityType.value
    segment: str
    action: str
    outcome_impact: float  # 实得影响（+0.18 表示 +18%）
    timestamp: str = ""

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, object]) -> "OpportunityMemoryRecord":
        return cls(
            game_id=str(d["game_id"]),
            type=str(d["type"]),
            segment=str(d.get("segment", "global")),
            action=str(d.get("action", "")),
            outcome_impact=float(d.get("outcome_impact", 0.0)),
            timestamp=str(d.get("timestamp", "")),
        )


class OpportunityMemory:
    def __init__(self, path: str = "data/ceo/opportunity_memory.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, rec: OpportunityMemoryRecord) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")

    def _all(self) -> List[OpportunityMemoryRecord]:
        if not self.path.exists():
            return []
        out: List[OpportunityMemoryRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            out.append(OpportunityMemoryRecord.from_dict(json.loads(line)))
        return out

    def records_for(self, opp_type: str, segment: str = "global") -> List[OpportunityMemoryRecord]:
        return [r for r in self._all() if r.type == opp_type and r.segment == segment]

    def confidence_boost(self, opp_type: str, segment: str = "global") -> float:
        """相似历史成功率 ≥2 样本时给予置信度加成（封顶 0.20）。"""
        recs = self.records_for(opp_type, segment)
        if len(recs) < 2:
            return 0.0
        success = sum(1 for r in recs if r.outcome_impact > 0)
        rate = success / len(recs)
        return min(0.20, rate * 0.15)

    def apply_boost(self, opp, segment: str = "global") -> None:
        boost = self.confidence_boost(opp.type.value, segment)
        if boost > 0:
            opp.confidence = min(0.99, round(opp.confidence + boost, 4))
