"""P2.5.7 Feedback Bridge（执行经验回流 Memory，P2.5 最关键的一层）。

把一次执行的结果沉淀为「经验」，回流到：
    ① ExecutionExperienceStore（E16 风格 JSONL 经验库，供查询 success_rate/avg_reward）
    ② E17.7 GrowthMemoryGraph（execution -> action -> result 链路，供 E17.3 决策引擎学习）

设计纪律：
- 只观察、只回流，不做决策、不改写执行结果、不调用平台 API
- reward 由 before/after 状态相对改善推导（默认 eCPM 相对 delta）
- 与 E17.7 的桥接用懒导入，避免循环依赖
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from src.execution.monitor.models import _as_str
from src.execution.models import ExecutionRequest
from src.execution.safe_executor.models import SafeExecutionOutcome


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_ecpm(state: Dict[str, Any]) -> float:
    """从 before/after_state 中抽取 eCPM（兼容 ecpm / e_cpm / value）。"""
    if not isinstance(state, dict):
        return 0.0
    for key in ("ecpm", "e_cpm", "value"):
        v = state.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    return 0.0


def default_reward(record: "ExecutionExperienceRecord") -> "tuple[float, bool]":
    """默认 reward：eCPM 相对改善（与 E16 compute_reward 思路一致）。

    返回 (reward, success)。reward>0 即 success。
    """
    b = record.result.get("before_ecpm", 0.0) or 0.0
    a = record.result.get("after_ecpm", 0.0) or 0.0
    if b > 0 and a > 0:
        reward = (a - b) / b
    elif b == 0 and a > 0:
        reward = 1.0
    elif a > 0:
        reward = 1.0
    else:
        reward = 0.0
    return reward, reward > 0.0


@dataclass
class ExecutionExperienceRecord:
    """一次执行回流的经验记录（Memory 的「Result」原子）。

    结构（规格）：
        {
          "action": "update_waterfall",
          "context": {"game": "merge_witch", "network": "max"},
          "result": {"before_ecpm": 12.3, "after_ecpm": 22.4},
          "reward": 0.82,
          "success": true
        }
    """

    action: str
    context: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)
    reward: float = 0.0
    success: bool = False
    provider: str = ""
    execution_id: str = ""
    verdict: str = ""
    timestamp: str = ""
    record_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.record_id:
            self.record_id = f"exp_{uuid.uuid4().hex[:12]}"
        if not self.timestamp:
            self.timestamp = _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "action": _as_str(self.action),
            "context": self.context,
            "result": self.result,
            "reward": round(self.reward, 4),
            "success": self.success,
            "provider": self.provider,
            "execution_id": self.execution_id,
            "verdict": self.verdict,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExecutionExperienceRecord":
        return cls(
            action=str(d.get("action", "")),
            context=d.get("context") or {},
            result=d.get("result") or {},
            reward=float(d.get("reward", 0.0)),
            success=bool(d.get("success", False)),
            provider=str(d.get("provider", "")),
            execution_id=str(d.get("execution_id", "")),
            verdict=str(d.get("verdict", "")),
            timestamp=str(d.get("timestamp", "")),
            record_id=str(d.get("record_id", "")),
            metadata=d.get("metadata") or {},
        )


@runtime_checkable
class ExecutionExperienceStore(Protocol):
    """经验库协议（供测试注入 fake / 生产用 JSONL 实现）。"""

    def add(self, record: ExecutionExperienceRecord) -> None: ...

    def for_action(self, action: str) -> List[Dict[str, Any]]: ...

    def stats(self, action: str) -> Dict[str, Any]: ...


class JsonlExecutionExperienceStore:
    """append-only JSONL 执行经验库（E16 风格）。"""

    def __init__(self, path: str = "data/ceo/execution_experience.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def add(self, record: ExecutionExperienceRecord) -> None:
        reward, success = default_reward(record)
        record.reward = round(reward, 4)
        record.success = success
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def all(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        out: List[Dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def for_action(self, action: str) -> List[Dict[str, Any]]:
        return [e for e in self.all() if e.get("action") == action]

    def stats(self, action: str) -> Dict[str, Any]:
        rows = self.for_action(action)
        n = len(rows)
        if n == 0:
            return {"n": 0, "success_rate": 0.0, "avg_reward": 0.0}
        successes = sum(1 for r in rows if r.get("success"))
        avg_reward = sum(float(r.get("reward", 0.0)) for r in rows) / n
        return {
            "n": n,
            "success_rate": round(successes / n, 4),
            "avg_reward": round(avg_reward, 4),
        }


class FeedbackBridge:
    """把一次执行回流为经验，并推入 Memory（经验库 + E17.7 图谱）。"""

    def __init__(
        self,
        store: Optional[ExecutionExperienceStore] = None,
        graph: Any = None,
    ) -> None:
        self.store = store or JsonlExecutionExperienceStore()
        self.graph = graph

    def push(
        self,
        request: Optional[ExecutionRequest],
        outcome: SafeExecutionOutcome,
    ) -> ExecutionExperienceRecord:
        ctx = outcome.context
        provider = ""
        if outcome.result is not None:
            provider = _as_str(getattr(outcome.result, "provider", ""))
        game = _as_str(ctx.target)
        if request is not None:
            intent = getattr(request, "intent", None)
            if intent is not None and intent.target_id:
                game = _as_str(intent.target_id)

        before_ecpm = _extract_ecpm(ctx.before_state)
        after_ecpm = _extract_ecpm(ctx.after_state)

        record = ExecutionExperienceRecord(
            action=_as_str(ctx.action),
            context={"game": game, "network": provider},
            result={"before_ecpm": before_ecpm, "after_ecpm": after_ecpm},
            provider=provider,
            execution_id=ctx.execution_id,
            verdict=_as_str(outcome.verdict),
            timestamp=ctx.started_at,
            metadata={
                "mode": ctx.mode,
                "is_real": (
                    bool(getattr(outcome.result, "real_api_called", False))
                    if outcome.result is not None
                    else False
                ),
            },
        )
        reward, success = default_reward(record)
        record.reward = round(reward, 4)
        record.success = success
        self.store.add(record)
        return record

    def push_to_graph(
        self, record: ExecutionExperienceRecord, graph: Any = None
    ) -> Dict[str, Any]:
        """把经验推入 E17.7 GrowthMemoryGraph（execution -> action -> result 链路）。

        懒导入避免循环依赖；非法/缺失 graph 时安全跳过（返回 skipped=True）。
        """
        target = graph or self.graph
        if target is None:
            return {"skipped": True, "reason": "no_graph"}

        try:
            from src.ceo_intelligence.growth_memory_graph.models import (
                EdgeType,
                NodeType,
                GraphEdge,
                GraphNode,
                node_id,
            )
            from src.ceo_intelligence.growth_memory_graph.store import (
                GrowthMemoryGraph,
            )
        except Exception:  # noqa: BLE001 — 图谱模块缺失时优雅降级
            return {"skipped": True, "reason": "import_error"}

        if not isinstance(target, GrowthMemoryGraph):
            return {"skipped": True, "reason": "not_a_graph"}

        exe_id = record.execution_id or record.record_id
        game = record.context.get("game", "")
        exe_node = GraphNode(
            id=node_id(NodeType.EXECUTION, exe_id),
            type=NodeType.EXECUTION,
            label=f"execution:{exe_id}",
            payload={
                "action": record.action,
                "provider": record.provider,
                "verdict": record.verdict,
                "game": game,
                "reward": record.reward,
                "success": record.success,
            },
        )
        act_node = GraphNode(
            id=node_id(NodeType.ACTION, exe_id),
            type=NodeType.ACTION,
            label=f"action:{exe_id}",
            payload={"action": record.action, "provider": record.provider},
        )
        res_node = GraphNode(
            id=node_id(NodeType.RESULT, exe_id),
            type=NodeType.RESULT,
            label=f"result:{exe_id}",
            payload={
                "before_ecpm": record.result.get("before_ecpm", 0.0),
                "after_ecpm": record.result.get("after_ecpm", 0.0),
                "reward": record.reward,
                "success": record.success,
            },
        )
        e1 = GraphEdge(exe_node.id, act_node.id, EdgeType.INCLUDES_ACTION)
        e2 = GraphEdge(act_node.id, res_node.id, EdgeType.PRODUCES_RESULT)

        added = []
        for n in (exe_node, act_node, res_node):
            if target.add_node(n):
                added.append(n.id)
        for e in (e1, e2):
            target.add_edge(e)
        return {"skipped": False, "nodes_added": added, "edges": 2}


__all__ = [
    "default_reward",
    "ExecutionExperienceRecord",
    "ExecutionExperienceStore",
    "JsonlExecutionExperienceStore",
    "FeedbackBridge",
]
