"""Asset Graph - 资产血缘图"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class AssetNode:
    """资产节点"""
    asset_id: str = ""
    parent_id: str = ""
    asset_type: str = ""
    prompt_dna: str = ""
    platform: str = ""
    seed: int = 0
    metrics: Dict[str, Any] = field(default_factory=dict)
    children: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "parent_id": self.parent_id,
            "asset_type": self.asset_type,
            "prompt_dna": self.prompt_dna,
            "platform": self.platform,
            "seed": self.seed,
            "metrics": self.metrics,
            "children": self.children,
        }


class AssetGraph:
    """资产血缘图"""

    def __init__(self):
        self._nodes: Dict[str, AssetNode] = {}

    def add_node(self, node: AssetNode) -> bool:
        if node.asset_id in self._nodes:
            return False
        self._nodes[node.asset_id] = node
        if node.parent_id and node.parent_id in self._nodes:
            parent = self._nodes[node.parent_id]
            if node.asset_id not in parent.children:
                parent.children.append(node.asset_id)
        return True

    def get_node(self, asset_id: str) -> Optional[AssetNode]:
        return self._nodes.get(asset_id)

    def get_parent(self, asset_id: str) -> Optional[AssetNode]:
        node = self.get_node(asset_id)
        if node and node.parent_id:
            return self._nodes.get(node.parent_id)
        return None

    def get_children(self, asset_id: str) -> List[AssetNode]:
        node = self.get_node(asset_id)
        if not node:
            return []
        return [self._nodes[cid] for cid in node.children if cid in self._nodes]

    def get_lineage(self, asset_id: str) -> List[AssetNode]:
        lineage = []
        current = self.get_node(asset_id)
        while current:
            lineage.append(current)
            current = self.get_parent(current.asset_id)
        return lineage

    def get_descendants(self, asset_id: str) -> List[AssetNode]:
        descendants = []
        node = self.get_node(asset_id)
        if not node:
            return descendants
        for child_id in node.children:
            child = self.get_node(child_id)
            if child:
                descendants.append(child)
                descendants.extend(self.get_descendants(child_id))
        return descendants

    def update_metrics(self, asset_id: str, metrics: Dict[str, Any]):
        node = self.get_node(asset_id)
        if node:
            node.metrics.update(metrics)

    def get_top_performers(self, metric_key: str = "ctr", limit: int = 10) -> List[AssetNode]:
        nodes = [n for n in self._nodes.values() if metric_key in n.metrics]
        return sorted(nodes, key=lambda n: n.metrics.get(metric_key, 0), reverse=True)[:limit]

    def size(self) -> int:
        return len(self._nodes)

    def get_stats(self) -> Dict[str, Any]:
        by_type = {}
        for node in self._nodes.values():
            by_type[node.asset_type] = by_type.get(node.asset_type, 0) + 1
        return {
            "total_assets": self.size(),
            "by_type": by_type,
        }