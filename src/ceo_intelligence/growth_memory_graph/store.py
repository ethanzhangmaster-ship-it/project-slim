"""E17.7 — GrowthMemoryGraph：内存 Map + JSONL 持久化的增长记忆图谱。

存储（沿用 E17.6 ExecutionMemory / E16 Jsonl*Store 模式，不引第三方图库）：
- 内存：nodes: Dict[id, GraphNode]；edges: Dict[(src,tgt,type), GraphEdge]
- 落盘：data/ceo/memory_graph.jsonl，逐行 {"kind": "node"|"edge", ...}
  append-only；加载时按顺序重放（节点 last-write-wins 合并 payload）。
- 幂等：重复摄入相同节点/边不重复落盘（payload 变化才追加更新行）。

确定性遍历：所有查询输出按插入顺序 / ID 排序，无随机性。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    EdgeType,
    ExecutionChain,
    GraphEdge,
    GraphNode,
    MemoryEvent,
    NodeType,
    node_id,
)


class GrowthMemoryGraph:
    """增长记忆图谱（确定性、无 LLM、纯 JSONL）。"""

    def __init__(self, path: str = "data/ceo/memory_graph.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: Dict[Tuple[str, str, str], GraphEdge] = {}
        self._out: Dict[str, List[Tuple[str, str, str]]] = {}  # src -> edge keys
        self._in: Dict[str, List[Tuple[str, str, str]]] = {}   # tgt -> edge keys
        self._load()

    # ------------------------------------------------------------------ #
    # 持久化
    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        if not self.path.exists():
            return
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    if row.get("kind") == "node":
                        self._put_node(GraphNode.from_dict(row["data"]), persist=False)
                    elif row.get("kind") == "edge":
                        self._put_edge(GraphEdge.from_dict(row["data"]), persist=False)
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

    def _append(self, kind: str, data: Dict[str, Any]) -> None:
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": kind, "data": data}, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------ #
    # 写入（幂等）
    # ------------------------------------------------------------------ #
    def _put_node(self, node: GraphNode, *, persist: bool = True) -> bool:
        """新增或合并节点；返回是否有实际变化。"""
        existing = self.nodes.get(node.id)
        if existing is None:
            self.nodes[node.id] = node
            if persist:
                self._append("node", node.to_dict())
            return True
        # last-write-wins 合并 payload（仅新键或值变化才算更新）
        merged = dict(existing.payload)
        changed = False
        for k, v in node.payload.items():
            if merged.get(k) != v:
                merged[k] = v
                changed = True
        # label 首写优先：stub 节点（后到）不得覆盖权威 label，保证重摄入幂等
        if node.label and not existing.label:
            existing.label = node.label
            changed = True
        if changed:
            existing.payload = merged
            if persist:
                self._append("node", existing.to_dict())
        return changed

    def _put_edge(self, edge: GraphEdge, *, persist: bool = True) -> bool:
        if edge.key in self.edges:
            return False
        self.edges[edge.key] = edge
        self._out.setdefault(edge.src, []).append(edge.key)
        self._in.setdefault(edge.tgt, []).append(edge.key)
        if persist:
            self._append("edge", edge.to_dict())
        return True

    def add_node(self, node: GraphNode) -> bool:
        return self._put_node(node)

    def add_edge(self, edge: GraphEdge) -> bool:
        return self._put_edge(edge)

    def ingest_event(self, event: MemoryEvent) -> Dict[str, int]:
        """摄入一个记忆事件；返回 {nodes_added, edges_added}（幂等去重后计数）。"""
        n = sum(1 for node in event.nodes if self._put_node(node))
        e = sum(1 for edge in event.edges if self._put_edge(edge))
        return {"nodes_added": n, "edges_added": e}

    # ------------------------------------------------------------------ #
    # 从 E17.6 ExecutionMemory 重建（无需重跑上游）
    # ------------------------------------------------------------------ #
    def build_from_execution_memory(self, execution_memory) -> Dict[str, int]:
        """吃 ExecutionMemory.all() 的 ExecutionExperience，重建全链路图。"""
        from .ingest import event_from_experience

        total = {"nodes_added": 0, "edges_added": 0}
        for exp in execution_memory.all():
            r = self.ingest_event(event_from_experience(exp))
            total["nodes_added"] += r["nodes_added"]
            total["edges_added"] += r["edges_added"]
        return total

    # ------------------------------------------------------------------ #
    # 查询
    # ------------------------------------------------------------------ #
    def get_node(self, nid: str) -> Optional[GraphNode]:
        return self.nodes.get(nid)

    def neighbors(
        self,
        nid: str,
        edge_type: Optional[EdgeType] = None,
        direction: str = "out",
    ) -> List[GraphNode]:
        keys = (self._out if direction == "out" else self._in).get(nid, [])
        out: List[GraphNode] = []
        for key in keys:
            edge = self.edges[key]
            if edge_type is not None and edge.type != edge_type:
                continue
            other = edge.tgt if direction == "out" else edge.src
            node = self.nodes.get(other)
            if node is not None:
                out.append(node)
        return out

    def query(
        self,
        node_type: Optional[NodeType] = None,
        game_id: Optional[str] = None,
        **payload_filters: Any,
    ) -> List[GraphNode]:
        """按类型 / 游戏 / payload 键值过滤节点（确定性：按 id 排序）。"""
        out: List[GraphNode] = []
        for node in self.nodes.values():
            if node_type is not None and node.type != node_type:
                continue
            if game_id is not None and node.payload.get("game_id") != game_id:
                continue
            if any(node.payload.get(k) != v for k, v in payload_filters.items()):
                continue
            out.append(node)
        return sorted(out, key=lambda n: n.id)

    def trace_execution(self, execution_id: str) -> Optional[ExecutionChain]:
        """回溯一条 execution 的完整因果链：game → … → results。"""
        exec_node = self.nodes.get(node_id(NodeType.EXECUTION, execution_id))
        if exec_node is None:
            return None
        chain_ids: List[str] = []

        # 向上回溯：execution ← strategy ← decision ← opportunity ← game
        upstream: List[str] = []
        cursor = exec_node
        for edge_type in (
            EdgeType.EXECUTES,          # strategy -> execution
            EdgeType.PLANS_STRATEGY,    # decision -> strategy
            EdgeType.LEADS_TO_DECISION, # opportunity -> decision
            EdgeType.HAS_OPPORTUNITY,   # game -> opportunity
        ):
            parents = self.neighbors(cursor.id, edge_type, direction="in")
            if not parents:
                break
            cursor = parents[0]
            upstream.append(cursor.id)
        chain_ids.extend(reversed(upstream))
        chain_ids.append(exec_node.id)

        # 向下展开：actions + results
        actions = sorted(
            self.neighbors(exec_node.id, EdgeType.INCLUDES_ACTION),
            key=lambda n: int(n.payload.get("source_task_order", 0)),
        )
        success = 0
        for act in actions:
            chain_ids.append(act.id)
            for res in self.neighbors(act.id, EdgeType.PRODUCES_RESULT):
                chain_ids.append(res.id)
                if res.payload.get("success"):
                    success += 1

        return ExecutionChain(
            execution_id=execution_id,
            game_id=exec_node.payload.get("game_id", ""),
            decision_id=exec_node.payload.get("decision_id", ""),
            strategy_type=exec_node.payload.get("strategy_type", ""),
            node_ids=chain_ids,
            success_actions=success,
            total_actions=len(actions),
        )

    def game_subgraph(self, game_id: str) -> Dict[str, Any]:
        """从 game 节点 BFS（出边）可达的子图（确定性顺序）。"""
        root = node_id(NodeType.GAME, game_id)
        if root not in self.nodes:
            return {"nodes": [], "edges": []}
        seen = {root}
        order = [root]
        queue = [root]
        sub_edges: List[GraphEdge] = []
        while queue:
            cur = queue.pop(0)
            for key in self._out.get(cur, []):
                edge = self.edges[key]
                sub_edges.append(edge)
                if edge.tgt not in seen:
                    seen.add(edge.tgt)
                    order.append(edge.tgt)
                    queue.append(edge.tgt)
        return {
            "nodes": [self.nodes[nid].to_dict() for nid in order if nid in self.nodes],
            "edges": [e.to_dict() for e in sub_edges],
        }

    def success_rate_by(
        self,
        strategy_type: Optional[str] = None,
        domain: Optional[str] = None,
        action_type: Optional[str] = None,
        game_id: Optional[str] = None,
    ) -> float:
        """按策略/域/动作/游戏过滤 RESULT 节点的成功率；无样本返回 0.0。"""
        rows = [
            n for n in self.query(NodeType.RESULT)
            if (strategy_type is None or n.payload.get("strategy_type") == strategy_type)
            and (domain is None or n.payload.get("domain") == domain)
            and (action_type is None or n.payload.get("action_type") == action_type)
            and (game_id is None or n.payload.get("game_id") == game_id)
        ]
        if not rows:
            return 0.0
        return sum(1 for n in rows if n.payload.get("success")) / len(rows)

    def stats(self) -> Dict[str, int]:
        by_type: Dict[str, int] = {}
        for node in self.nodes.values():
            by_type[node.type.value] = by_type.get(node.type.value, 0) + 1
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            **{f"nodes_{k}": v for k, v in sorted(by_type.items())},
        }


__all__ = ["GrowthMemoryGraph"]
