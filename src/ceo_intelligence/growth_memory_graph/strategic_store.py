"""
P3.6.2 — StrategicStore（StrategicInsight 写入适配，唯一写入口守卫）。

只负责把 ``StrategicInsight`` 转成交给 ``KnowledgeFeedbackRecorder.record_insight()``，
**绝不直接碰 Graph**（D1 冻结：Graph Writer 唯一入口 = KnowledgeFeedbackRecorder，
保证 writer lineage / source attribution / feedback governance / audit/replay）。

```
StrategicBuilder ── StrategicInsight ──▶ StrategicStore ──▶ recorder.record_insight() ──▶ GrowthMemoryGraph
```

纪律：
- ❌ 禁 graph.add_node / graph.add_edge / 任何直接 mutation（AST 锁死）；
- ❌ 不写回 5 源、不调 consolidate、不调 Provider / SafeExecutor / DecisionEngine；
- ✅ ``real_api_called`` 恒 False；✅ fail-open（recorder 为 None / 异常 → 空计数）。
"""
from __future__ import annotations

from typing import Any, Dict, List

from .feedback import KnowledgeFeedbackRecorder


class StrategicStore:
    """StrategicInsight 写入适配（只调 recorder，不碰 Graph）。"""

    def __init__(self, recorder: Any = None) -> None:
        self.recorder = recorder

    @property
    def real_api_called(self) -> bool:
        return False

    def save(self, insight: Any) -> Dict[str, int]:
        """写入一条 StrategicInsight（经唯一写入口 KnowledgeFeedbackRecorder）。"""
        if self.recorder is None:
            return {"nodes_added": 0, "edges_added": 0}
        return self.recorder.record_insight(insight)

    def save_all(self, insights: List[Any]) -> Dict[str, int]:
        """批量写入；返回累计 {nodes_added, edges_added}（fail-open）。"""
        total: Dict[str, int] = {"nodes_added": 0, "edges_added": 0}
        for ins in insights or []:
            r = self.save(ins)
            total["nodes_added"] += r.get("nodes_added", 0)
            total["edges_added"] += r.get("edges_added", 0)
        return total


__all__ = ["StrategicStore"]
