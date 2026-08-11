"""V4.4 Dependency Graph — auto-dependency resolution for workflows.

Auto-calculates execution order from task dependencies.
Supports DAG validation and topological sort.

Example:
  A → B → C
  A → C, B → D → C

No manual ordering needed.
"""

from __future__ import annotations

from typing import Any


class DependencyGraph:
    """DAG-based dependency resolution for task execution."""

    def __init__(self) -> None:
        self._nodes: dict[str, set[str]] = {}  # node → {dependencies}
        self._reverse: dict[str, set[str]] = {}  # node → {dependents}

    def add_node(self, name: str, dependencies: list[str] | None = None) -> None:
        """Add a node with its dependencies."""
        deps = set(dependencies or [])
        self._nodes[name] = deps
        if name not in self._reverse:
            self._reverse[name] = set()
        for dep in deps:
            if dep not in self._reverse:
                self._reverse[dep] = set()
            self._reverse[dep].add(name)

    def add_nodes(self, nodes: dict[str, list[str]]) -> None:
        """Add multiple nodes at once.

        Args:
            nodes: {name: [dependencies]}
        """
        for name, deps in nodes.items():
            self.add_node(name, deps)

    def get_dependencies(self, name: str) -> list[str]:
        """Get direct dependencies of a node."""
        return list(self._nodes.get(name, set()))

    def get_dependents(self, name: str) -> list[str]:
        """Get nodes that depend on a given node."""
        return list(self._reverse.get(name, set()))

    def get_all_dependencies(self, name: str) -> list[str]:
        """Get all transitive dependencies of a node."""
        result = set()
        self._collect_deps(name, result)
        result.discard(name)
        return list(result)

    def _collect_deps(self, name: str, result: set[str]) -> None:
        """Recursively collect all dependencies."""
        if name in result:
            return
        result.add(name)
        for dep in self._nodes.get(name, set()):
            self._collect_deps(dep, result)

    def topological_sort(self) -> list[str]:
        """Topological sort of the DAG.

        Returns:
            Ordered list of nodes where dependencies come first.

        Raises:
            ValueError: If the graph has a cycle.
        """
        in_degree = {node: len(deps) for node, deps in self._nodes.items()}
        for node in self._nodes:
            if node not in in_degree:
                in_degree[node] = 0

        # Start with nodes that have no dependencies
        queue = [node for node, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for dependent in self._reverse.get(node, set()):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self._nodes):
            raise ValueError("Cycle detected in dependency graph")

        return result

    def has_cycle(self) -> bool:
        """Check if the graph has a cycle."""
        try:
            self.topological_sort()
            return False
        except ValueError:
            return True

    def get_execution_levels(self) -> list[list[str]]:
        """Get execution levels — nodes at the same level can run in parallel.

        Level 0: nodes with no dependencies.
        Level 1: nodes whose dependencies are all in level 0.
        etc.
        """
        sorted_nodes = self.topological_sort()
        levels = []
        visited = set()

        while len(visited) < len(sorted_nodes):
            level = []
            for node in sorted_nodes:
                if node in visited:
                    continue
                deps = self._nodes.get(node, set())
                if deps.issubset(visited):
                    level.append(node)
            if not level:
                break
            levels.append(level)
            visited.update(level)

        return levels

    def get_node_count(self) -> int:
        """Get total number of nodes."""
        return len(self._nodes)

    def get_graph_summary(self) -> dict[str, Any]:
        """Get graph summary."""
        try:
            levels = self.get_execution_levels()
        except ValueError:
            levels = []

        return {
            "nodes": len(self._nodes),
            "edges": sum(len(deps) for deps in self._nodes.values()),
            "levels": len(levels),
            "has_cycle": self.has_cycle(),
            "execution_order": self.topological_sort() if not self.has_cycle() else [],
        }