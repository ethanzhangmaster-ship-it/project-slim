"""Creative Knowledge Graph - 创意知识图谱

节点类型：
- Creature: dragon, cat, fox, owl, unicorn, fairy, phoenix...
- Environment: magic_forest, crystal_cave, moon_lake...
- Hook: collection, curiosity, crisis, reward...
- Theme: cute, magical, epic, kawaii, cozy...
- Lighting: warm, cool, golden, moonlit...
- Color: purple, blue, gold, pink, green...
- Character: witch, wizard, girl, boy...
- Gameplay: merge, collection, match3...
- Metric: ctr, roas, cvr, ipm

边类型：
- HAS_A: Creature → Theme (dragon → cute)
- WORKS_WITH: Creature → Environment (dragon → magic_forest)
- PREDICTS: Theme → Metric (cute → ctr_high)
- CORRELATES_WITH: Environment → Lighting (magic_forest → warm)
- INCREASES: Feature → Metric (warm_lighting → roas)
- DECREASES: Feature → Metric (text_heavy → ctr)
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

try:
    import networkx as nx
    _HAS_NETWORKX = True
except ImportError:
    _HAS_NETWORKX = False


NODE_TYPES = {
    "Creature",
    "Environment",
    "Hook",
    "Theme",
    "Lighting",
    "Color",
    "Character",
    "Gameplay",
    "Metric",
}

EDGE_TYPES = {
    "HAS_A",
    "WORKS_WITH",
    "PREDICTS",
    "CORRELATES_WITH",
    "INCREASES",
    "DECREASES",
}


@dataclass(slots=True)
class GraphNode:
    node_id: str
    node_type: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GraphEdge:
    from_node: str
    to_node: str
    edge_type: str
    weight: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)


class CreativeKnowledgeGraph:
    def __init__(self) -> None:
        self._use_networkx = _HAS_NETWORKX
        if self._use_networkx:
            self._graph = nx.DiGraph()
        else:
            self._nodes: dict[str, GraphNode] = {}
            self._out_edges: dict[str, list[GraphEdge]] = {}
            self._in_edges: dict[str, list[GraphEdge]] = {}

    def add_node(self, node_id: str, node_type: str, properties: dict[str, Any] | None = None) -> None:
        if node_type not in NODE_TYPES:
            raise ValueError(f"Unknown node type: {node_type}. Valid types: {NODE_TYPES}")
        props = properties or {}

        if self._use_networkx:
            self._graph.add_node(node_id, node_type=node_type, **props)
        else:
            self._nodes[node_id] = GraphNode(node_id=node_id, node_type=node_type, properties=props)
            if node_id not in self._out_edges:
                self._out_edges[node_id] = []
            if node_id not in self._in_edges:
                self._in_edges[node_id] = []

    def add_edge(
        self,
        from_node: str,
        to_node: str,
        edge_type: str,
        weight: float = 1.0,
        properties: dict[str, Any] | None = None,
    ) -> None:
        if edge_type not in EDGE_TYPES:
            raise ValueError(f"Unknown edge type: {edge_type}. Valid types: {EDGE_TYPES}")
        props = properties or {}

        if self._use_networkx:
            if not self._graph.has_node(from_node):
                raise ValueError(f"Node {from_node} does not exist")
            if not self._graph.has_node(to_node):
                raise ValueError(f"Node {to_node} does not exist")
            self._graph.add_edge(from_node, to_node, edge_type=edge_type, weight=weight, **props)
        else:
            if from_node not in self._nodes:
                raise ValueError(f"Node {from_node} does not exist")
            if to_node not in self._nodes:
                raise ValueError(f"Node {to_node} does not exist")
            edge = GraphEdge(
                from_node=from_node,
                to_node=to_node,
                edge_type=edge_type,
                weight=weight,
                properties=props,
            )
            self._out_edges[from_node].append(edge)
            self._in_edges[to_node].append(edge)

    def get_neighbors(self, node_id: str, edge_type: str | None = None) -> list[tuple[str, str, float]]:
        if self._use_networkx:
            if node_id not in self._graph:
                return []
            neighbors = []
            for _, nbr, data in self._graph.out_edges(node_id, data=True):
                if edge_type is None or data.get("edge_type") == edge_type:
                    neighbors.append((nbr, data.get("edge_type", ""), data.get("weight", 1.0)))
            return neighbors
        else:
            if node_id not in self._out_edges:
                return []
            result = []
            for edge in self._out_edges[node_id]:
                if edge_type is None or edge.edge_type == edge_type:
                    result.append((edge.to_node, edge.edge_type, edge.weight))
            return result

    def get_path(self, from_node: str, to_node: str, max_depth: int = 3) -> list[list[str]]:
        paths: list[list[str]] = []

        def dfs(current: str, target: str, visited: set[str], path: list[str], depth: int) -> None:
            if depth > max_depth:
                return
            if current == target and len(path) > 1:
                paths.append(list(path))
                return
            neighbors = self.get_neighbors(current)
            for nbr, _, _ in neighbors:
                if nbr not in visited:
                    visited.add(nbr)
                    path.append(nbr)
                    dfs(nbr, target, visited, path, depth + 1)
                    path.pop()
                    visited.remove(nbr)

        if from_node == to_node:
            return [[from_node]]

        visited = {from_node}
        dfs(from_node, to_node, visited, [from_node], 0)
        return paths

    def query_pattern(self, pattern_dict: dict[str, Any]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        node_type = pattern_dict.get("node_type")
        properties = pattern_dict.get("properties", {})
        has_edge = pattern_dict.get("has_edge")
        edge_to_type = pattern_dict.get("edge_to_type")

        node_ids = self._get_all_node_ids()
        for nid in node_ids:
            node_data = self._get_node_data(nid)
            if node_type and node_data.get("node_type") != node_type:
                continue
            match = True
            for k, v in properties.items():
                if node_data.get("properties", {}).get(k) != v:
                    match = False
                    break
            if not match:
                continue

            if has_edge:
                neighbors = self.get_neighbors(nid, has_edge)
                if not neighbors:
                    continue
                if edge_to_type:
                    has_target_type = False
                    for nbr, _, _ in neighbors:
                        nbr_data = self._get_node_data(nbr)
                        if nbr_data.get("node_type") == edge_to_type:
                            has_target_type = True
                            break
                    if not has_target_type:
                        continue

            results.append({
                "node_id": nid,
                "node_type": node_data.get("node_type"),
                "properties": node_data.get("properties", {}),
            })

        return results

    def get_top_features_for_metric(self, metric: str, limit: int = 10) -> list[dict[str, Any]]:
        features: list[dict[str, Any]] = []

        metric_node = f"metric_{metric}"
        if not self._node_exists(metric_node):
            return []

        all_node_ids = self._get_all_node_ids()
        for nid in all_node_ids:
            if nid == metric_node:
                continue
            increase_edges = self._find_edges(nid, metric_node, "INCREASES")
            decrease_edges = self._find_edges(nid, metric_node, "DECREASES")

            for edge in increase_edges:
                node_data = self._get_node_data(nid)
                features.append({
                    "feature": nid,
                    "feature_type": node_data.get("node_type"),
                    "effect": "increase",
                    "weight": edge["weight"],
                    "confidence": edge["properties"].get("confidence", 0.5),
                })

            for edge in decrease_edges:
                node_data = self._get_node_data(nid)
                features.append({
                    "feature": nid,
                    "feature_type": node_data.get("node_type"),
                    "effect": "decrease",
                    "weight": edge["weight"],
                    "confidence": edge["properties"].get("confidence", 0.5),
                })

        features.sort(key=lambda x: abs(x["weight"]), reverse=True)
        return features[:limit]

    def infer_impact(self, feature: str, metric: str) -> dict[str, Any]:
        result = {
            "feature": feature,
            "metric": metric,
            "direct_impact": None,
            "indirect_paths": [],
            "total_impact_score": 0.0,
            "confidence": 0.0,
        }

        metric_node = f"metric_{metric}"
        if not self._node_exists(feature) or not self._node_exists(metric_node):
            return result

        direct_increase = self._find_edges(feature, metric_node, "INCREASES")
        direct_decrease = self._find_edges(feature, metric_node, "DECREASES")

        if direct_increase:
            w = sum(e["weight"] for e in direct_increase) / len(direct_increase)
            result["direct_impact"] = {"direction": "increase", "weight": w}
            result["total_impact_score"] += w
            result["confidence"] = max(result["confidence"], direct_increase[0]["properties"].get("confidence", 0.5))
        if direct_decrease:
            w = sum(e["weight"] for e in direct_decrease) / len(direct_decrease)
            result["direct_impact"] = {"direction": "decrease", "weight": w}
            result["total_impact_score"] -= w
            result["confidence"] = max(result["confidence"], direct_decrease[0]["properties"].get("confidence", 0.5))

        paths = self.get_path(feature, metric_node, max_depth=3)
        for path in paths:
            if len(path) <= 2:
                continue
            path_weight = 1.0
            path_confidence = 1.0
            for i in range(len(path) - 1):
                edges = self._find_edges(path[i], path[i + 1])
                if edges:
                    avg_w = sum(e["weight"] for e in edges) / len(edges)
                    path_weight *= avg_w
                    path_confidence = min(path_confidence, edges[0]["properties"].get("confidence", 0.5))
            result["indirect_paths"].append({
                "path": path,
                "weight": path_weight,
                "confidence": path_confidence,
            })
            result["total_impact_score"] += path_weight * 0.5
            result["confidence"] = max(result["confidence"], path_confidence * 0.7)

        return result

    def add_from_memory(self, memory_data: list[dict[str, Any]]) -> int:
        count = 0
        for item in memory_data:
            nodes = item.get("nodes", [])
            edges = item.get("edges", [])

            for n in nodes:
                nid = n.get("node_id")
                ntype = n.get("node_type")
                if nid and ntype:
                    if not self._node_exists(nid):
                        self.add_node(nid, ntype, n.get("properties", {}))
                        count += 1

            for e in edges:
                from_n = e.get("from_node")
                to_n = e.get("to_node")
                etype = e.get("edge_type")
                if from_n and to_n and etype:
                    if self._node_exists(from_n) and self._node_exists(to_n):
                        self.add_edge(
                            from_n,
                            to_n,
                            etype,
                            weight=e.get("weight", 1.0),
                            properties=e.get("properties", {}),
                        )
                        count += 1

        return count

    def update_from_results(self, results_list: list[dict[str, Any]]) -> int:
        updated = 0

        for result in results_list:
            features = result.get("features", {})
            metrics = result.get("metrics", {})
            sample_count = result.get("sample_count", 1)

            for feat_name, feat_value in features.items():
                feat_node = f"feature_{feat_name}_{feat_value}" if isinstance(feat_value, str) else f"feature_{feat_name}"
                if not self._node_exists(feat_node):
                    self.add_node(feat_node, "Theme", {"value": feat_value})

                for metric_name, metric_value in metrics.items():
                    metric_node = f"metric_{metric_name}"
                    if not self._node_exists(metric_node):
                        self.add_node(metric_node, "Metric", {})

                    baseline = result.get("baseline", {}).get(metric_name, 0)
                    if baseline > 0:
                        lift = (metric_value - baseline) / baseline
                        edge_type = "INCREASES" if lift > 0 else "DECREASES"
                        weight = min(abs(lift), 2.0)

                        existing = self._find_edges(feat_node, metric_node, edge_type)
                        if existing:
                            old_weight = existing[0]["weight"]
                            old_conf = existing[0]["properties"].get("confidence", 0.5)
                            old_samples = existing[0]["properties"].get("sample_count", 1)
                            new_samples = old_samples + sample_count
                            new_weight = (old_weight * old_samples + weight * sample_count) / new_samples
                            new_conf = min(1.0, old_conf + sample_count * 0.01)
                            self._update_edge(
                                feat_node,
                                metric_node,
                                edge_type,
                                new_weight,
                                {"confidence": new_conf, "sample_count": new_samples},
                            )
                        else:
                            self.add_edge(
                                feat_node,
                                metric_node,
                                edge_type,
                                weight=weight,
                                properties={"confidence": 0.3, "sample_count": sample_count},
                            )
                        updated += 1

        return updated

    def export_to_dict(self) -> dict[str, Any]:
        nodes = []
        edges = []

        node_ids = self._get_all_node_ids()
        for nid in node_ids:
            data = self._get_node_data(nid)
            nodes.append({
                "node_id": nid,
                "node_type": data.get("node_type"),
                "properties": data.get("properties", {}),
            })

        for nid in node_ids:
            neighbors = self.get_neighbors(nid)
            for nbr, etype, weight in neighbors:
                edge_data = self._get_edge_data(nid, nbr, etype)
                edges.append({
                    "from_node": nid,
                    "to_node": nbr,
                    "edge_type": etype,
                    "weight": weight,
                    "properties": edge_data.get("properties", {}),
                })

        return {
            "version": "1.0",
            "use_networkx": self._use_networkx,
            "nodes": nodes,
            "edges": edges,
        }

    def load_from_dict(self, data: dict[str, Any]) -> None:
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])

        for n in nodes:
            self.add_node(n["node_id"], n["node_type"], n.get("properties", {}))

        for e in edges:
            self.add_edge(
                e["from_node"],
                e["to_node"],
                e["edge_type"],
                weight=e.get("weight", 1.0),
                properties=e.get("properties", {}),
            )

    def get_summary(self) -> dict[str, Any]:
        node_type_counts: dict[str, int] = {}
        edge_type_counts: dict[str, int] = {}

        node_ids = self._get_all_node_ids()
        for nid in node_ids:
            data = self._get_node_data(nid)
            ntype = data.get("node_type", "unknown")
            node_type_counts[ntype] = node_type_counts.get(ntype, 0) + 1

        total_edges = 0
        for nid in node_ids:
            neighbors = self.get_neighbors(nid)
            for _, etype, _ in neighbors:
                edge_type_counts[etype] = edge_type_counts.get(etype, 0) + 1
                total_edges += 1

        return {
            "total_nodes": len(node_ids),
            "total_edges": total_edges,
            "node_type_counts": node_type_counts,
            "edge_type_counts": edge_type_counts,
            "use_networkx": self._use_networkx,
        }

    def _get_all_node_ids(self) -> list[str]:
        if self._use_networkx:
            return list(self._graph.nodes())
        else:
            return list(self._nodes.keys())

    def _node_exists(self, node_id: str) -> bool:
        if self._use_networkx:
            return self._graph.has_node(node_id)
        else:
            return node_id in self._nodes

    def _get_node_data(self, node_id: str) -> dict[str, Any]:
        if self._use_networkx:
            if node_id not in self._graph:
                return {}
            data = dict(self._graph.nodes[node_id])
            node_type = data.pop("node_type", None)
            return {"node_type": node_type, "properties": data}
        else:
            if node_id not in self._nodes:
                return {}
            node = self._nodes[node_id]
            return {"node_type": node.node_type, "properties": node.properties}

    def _find_edges(
        self,
        from_node: str,
        to_node: str,
        edge_type: str | None = None,
    ) -> list[dict[str, Any]]:
        results = []
        if self._use_networkx:
            if self._graph.has_edge(from_node, to_node):
                data = dict(self._graph[from_node][to_node])
                et = data.pop("edge_type", None)
                weight = data.pop("weight", 1.0)
                if edge_type is None or et == edge_type:
                    results.append({"edge_type": et, "weight": weight, "properties": data})
        else:
            if from_node in self._out_edges:
                for edge in self._out_edges[from_node]:
                    if edge.to_node == to_node:
                        if edge_type is None or edge.edge_type == edge_type:
                            results.append({
                                "edge_type": edge.edge_type,
                                "weight": edge.weight,
                                "properties": edge.properties,
                            })
        return results

    def _get_edge_data(self, from_node: str, to_node: str, edge_type: str) -> dict[str, Any]:
        edges = self._find_edges(from_node, to_node, edge_type)
        return edges[0] if edges else {}

    def _update_edge(
        self,
        from_node: str,
        to_node: str,
        edge_type: str,
        new_weight: float,
        new_properties: dict[str, Any],
    ) -> None:
        if self._use_networkx:
            if self._graph.has_edge(from_node, to_node):
                self._graph[from_node][to_node]["weight"] = new_weight
                for k, v in new_properties.items():
                    self._graph[from_node][to_node][k] = v
        else:
            if from_node in self._out_edges:
                for edge in self._out_edges[from_node]:
                    if edge.to_node == to_node and edge.edge_type == edge_type:
                        edge.weight = new_weight
                        edge.properties.update(new_properties)
            if to_node in self._in_edges:
                for edge in self._in_edges[to_node]:
                    if edge.from_node == from_node and edge.edge_type == edge_type:
                        edge.weight = new_weight
                        edge.properties.update(new_properties)
