"""E13.6.2 Action Graph — 执行图构建与拓扑排序.

将 ActionNode 列表构建为有向无环图 (DAG)，通过拓扑排序确定执行顺序，
并检测回路、解析依赖关系。

核心能力:
  - build_graph: 从节点列表构建邻接表
  - topological_sort: Kahn 算法拓扑排序
  - detect_cycles: 回路检测
  - resolve_dependencies: 依赖解析与可达性分析
  - compute_phases: 按阶段分层

连接:
  E13.6.2 ActionPlanner → ActionGraph → ActionPlan
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from .action_models import ActionDependency, ActionNode, ActionStatus, PlanPhase
from .models import ExecutionActionType


class ActionGraph:
    """执行图 — 管理 ActionNode 之间的依赖关系与拓扑排序.

    用法:
        graph = ActionGraph()
        graph.add_nodes(nodes)
        order = graph.topological_sort()
        if graph.has_cycle:
            print("回路检测到!")
    """

    def __init__(self):
        self._nodes: dict[str, ActionNode] = {}
        self._adjacency: dict[str, list[str]] = defaultdict(list)
        self._in_degree: dict[str, int] = defaultdict(int)
        self._has_cycle: bool = False
        self._cycle_nodes: list[str] = []

    # ═══════════════════════════════════════════════════════════
    # 图构建
    # ═══════════════════════════════════════════════════════════

    def add_node(self, node: ActionNode) -> None:
        """添加节点."""
        self._nodes[node.node_id] = node
        if node.node_id not in self._in_degree:
            self._in_degree[node.node_id] = 0

    def add_nodes(self, nodes: list[ActionNode]) -> None:
        """批量添加节点."""
        for node in nodes:
            self.add_node(node)

    def add_edge(self, from_id: str, to_id: str) -> None:
        """添加有向边 from → to."""
        if from_id not in self._nodes or to_id not in self._nodes:
            return
        self._adjacency[from_id].append(to_id)
        self._in_degree[to_id] = self._in_degree.get(to_id, 0) + 1

    def build_from_nodes(self, nodes: list[ActionNode]) -> None:
        """从节点列表构建图 (自动解析依赖关系).

        Args:
            nodes: ActionNode 列表
        """
        self._nodes = {}
        self._adjacency = defaultdict(list)
        self._in_degree = defaultdict(int)
        self._has_cycle = False
        self._cycle_nodes = []

        # 添加所有节点
        for node in nodes:
            self.add_node(node)

        # 解析依赖关系 → 建边
        for node in nodes:
            for dep_id, dep_type in node.dependencies.items():
                if dep_id in self._nodes:
                    self.add_edge(dep_id, node.node_id)

    # ═══════════════════════════════════════════════════════════
    # 拓扑排序
    # ═══════════════════════════════════════════════════════════

    def topological_sort(self) -> list[str]:
        """Kahn 算法拓扑排序.

        Returns:
            list[str]: 拓扑排序后的节点 ID 列表
        """
        in_degree = dict(self._in_degree)
        queue: deque[str] = deque()

        # 入度为 0 的节点入队
        for node_id in self._nodes:
            if in_degree[node_id] == 0:
                queue.append(node_id)

        result: list[str] = []
        while queue:
            current = queue.popleft()
            result.append(current)

            for neighbor in self._adjacency.get(current, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 检测回路
        if len(result) != len(self._nodes):
            self._has_cycle = True
            self._cycle_nodes = [
                nid for nid in self._nodes if nid not in result
            ]

        return result

    def phase_ordered_sort(self) -> list[str]:
        """按阶段排序 — 先拓扑排序，再按 phase 分组.

        Returns:
            list[str]: 按阶段分组的拓扑排序节点 ID 列表
        """
        topo = self.topological_sort()

        # 按阶段分组排序
        phase_order = {
            PlanPhase.PREPARE: 0,
            PlanPhase.EXECUTE: 1,
            PlanPhase.VERIFY: 2,
            PlanPhase.MONITOR: 3,
            PlanPhase.ROLLBACK: 4,
        }

        def sort_key(node_id: str) -> tuple[int, int]:
            node = self._nodes.get(node_id)
            phase_rank = phase_order.get(node.phase, 1) if node else 1
            # 保持同阶段内的拓扑序
            topo_rank = topo.index(node_id) if node_id in topo else 999
            return (phase_rank, topo_rank)

        return sorted(topo, key=sort_key)

    # ═══════════════════════════════════════════════════════════
    # 回路检测
    # ═══════════════════════════════════════════════════════════

    def detect_cycles(self) -> list[list[str]]:
        """检测所有回路.

        Returns:
            list[list[str]]: 回路列表，每个回路是节点 ID 列表
        """
        self._has_cycle = False
        self._cycle_nodes = []

        visited: set[str] = set()
        in_stack: set[str] = set()
        cycles: list[list[str]] = []

        def dfs(node_id: str, path: list[str]) -> None:
            visited.add(node_id)
            in_stack.add(node_id)
            path.append(node_id)

            for neighbor in self._adjacency.get(node_id, []):
                if neighbor in in_stack:
                    # 找到回路
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)
                    self._has_cycle = True
                    self._cycle_nodes.extend(cycle)
                elif neighbor not in visited:
                    dfs(neighbor, path)

            path.pop()
            in_stack.discard(node_id)

        for node_id in self._nodes:
            if node_id not in visited:
                dfs(node_id, [])

        return cycles

    # ═══════════════════════════════════════════════════════════
    # 依赖分析
    # ═══════════════════════════════════════════════════════════

    def get_dependents(self, node_id: str) -> list[str]:
        """获取依赖某节点的所有节点 (下游)."""
        return list(self._adjacency.get(node_id, []))

    def get_dependencies(self, node_id: str) -> list[str]:
        """获取某节点的所有直接依赖 (上游)."""
        node = self._nodes.get(node_id)
        if node:
            return list(node.dependencies.keys())
        return []

    def get_transitive_dependencies(self, node_id: str) -> list[str]:
        """获取某节点的所有传递依赖 (BFS)."""
        result: set[str] = set()
        queue: deque[str] = deque([node_id])
        while queue:
            current = queue.popleft()
            node = self._nodes.get(current)
            if node:
                for dep_id in node.dependencies:
                    if dep_id not in result:
                        result.add(dep_id)
                        queue.append(dep_id)
        return list(result)

    def is_reachable(self, from_id: str, to_id: str) -> bool:
        """检查 from_id 是否可达 to_id (BFS)."""
        if from_id not in self._nodes or to_id not in self._nodes:
            return False
        visited: set[str] = set()
        queue: deque[str] = deque([from_id])
        while queue:
            current = queue.popleft()
            if current == to_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            for neighbor in self._adjacency.get(current, []):
                queue.append(neighbor)
        return False

    # ═══════════════════════════════════════════════════════════
    # 阶段计算
    # ═══════════════════════════════════════════════════════════

    def compute_phases(self) -> dict[str, list[str]]:
        """按 PlanPhase 分组节点.

        Returns:
            dict: {phase_value: [node_ids]}
        """
        phases: dict[str, list[str]] = defaultdict(list)
        for node_id, node in self._nodes.items():
            phases[node.phase.value].append(node_id)
        return dict(phases)

    def get_entry_nodes(self) -> list[str]:
        """获取入度为 0 的节点 (起始节点)."""
        return [nid for nid, deg in self._in_degree.items() if deg == 0]

    def get_exit_nodes(self) -> list[str]:
        """获取出度为 0 的节点 (终止节点)."""
        return [nid for nid in self._nodes if nid not in self._adjacency or not self._adjacency[nid]]

    # ═══════════════════════════════════════════════════════════
    # 属性
    # ═══════════════════════════════════════════════════════════

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return sum(len(v) for v in self._adjacency.values())

    @property
    def has_cycle(self) -> bool:
        return self._has_cycle

    @property
    def cycle_nodes(self) -> list[str]:
        return list(self._cycle_nodes)

    @property
    def nodes(self) -> dict[str, ActionNode]:
        return dict(self._nodes)