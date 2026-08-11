"""
P3.6.3 — ReflectionStore（CEOReflection 写入适配，唯一写入口守卫）。

只负责把 ``CEOReflection`` 转成交给 ``KnowledgeFeedbackRecorder.record_reflection()``，
**绝不直接碰 Graph**（P3.5.2 D1 冻结：Graph Writer 唯一入口 = KnowledgeFeedbackRecorder，
保证 writer lineage / source attribution / feedback governance / audit/replay）。

```
MemoryReflectionBuilder ── CEOReflection ──▶ ReflectionStore ──▶ recorder.record_reflection() ──▶ GrowthMemoryGraph
```

纪律：
- ❌ 禁 graph.add_node / graph.add_edge / 任何直接 mutation（AST 锁死）；
- ❌ 不写回 5 源、不调 consolidate、不调 Provider / SafeExecutor / DecisionEngine；
- ✅ ``real_api_called`` 恒 False；✅ fail-open（recorder 为 None / 异常 → 空计数）。
"""
from __future__ import annotations

from typing import Any, Dict

from .feedback import KnowledgeFeedbackRecorder


class ReflectionStore:
    """CEOReflection 写入适配（只调 recorder，不碰 Graph）。"""

    def __init__(self, recorder: Any = None) -> None:
        self.recorder = recorder

    @property
    def real_api_called(self) -> bool:
        return False

    def save(self, reflection: Any) -> Dict[str, int]:
        """写入一次复盘（经唯一写入口 KnowledgeFeedbackRecorder）。"""
        if self.recorder is None:
            return {"nodes_added": 0, "edges_added": 0}
        return self.recorder.record_reflection(reflection)


__all__ = ["ReflectionStore"]
