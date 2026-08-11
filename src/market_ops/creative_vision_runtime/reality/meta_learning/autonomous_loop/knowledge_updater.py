"""E12.5.5 — Knowledge Updater。

根据新证据更新知识图谱节点的置信度。

核心算法:
  - Bayesian 更新: 新置信度 = (旧置信度 × 旧证据 + 新证据 × 成功率) / (旧证据 + 新证据)
  - 冲突检测: 新证据与旧知识矛盾时的处理
  - 衰减: 旧知识随时间衰减

原则:
  - 确定性更新（无 AI/ML）
  - 可解释的置信度变化
"""

from __future__ import annotations

from .models import KnowledgeUpdate
from ..knowledge_graph.models import KnowledgeEdge, KnowledgeNode


class KnowledgeUpdater:
    """知识更新器 —— Bayesian 更新 + 冲突检测。

    Usage:
        >>> updater = KnowledgeUpdater()
        >>> updated_node, update_record = updater.update_node_confidence(
        ...     node, success_count=20, total_count=25, cycle_id="MLC_001"
        ... )
        >>> # 更新 edge
        >>> updated_edge, update_record = updater.update_edge_confidence(
        ...     edge, success_count=20, total_count=25, cycle_id="MLC_001"
        ... )
    """

    # 默认先验证据权重
    DEFAULT_PRIOR_WEIGHT: int = 10

    # 衰减因子（每天）
    DECAY_FACTOR: float = 0.001

    # 冲突阈值
    CONFLICT_THRESHOLD: float = 0.30

    def __init__(
        self,
        prior_weight: int = 10,
        decay_factor: float = 0.001,
        conflict_threshold: float = 0.30,
    ) -> None:
        self.DEFAULT_PRIOR_WEIGHT = prior_weight
        self.DECAY_FACTOR = decay_factor
        self.CONFLICT_THRESHOLD = conflict_threshold

    # ── Node Confidence Update ─────────────────────────────

    def update_node_confidence(
        self,
        node: KnowledgeNode,
        success_count: int,
        total_count: int,
        cycle_id: str = "",
        days_since_creation: float = 0.0,
    ) -> tuple[KnowledgeNode, KnowledgeUpdate]:
        """Bayesian 更新节点置信度。

        new_conf = (old_conf × prior_weight × decay + success_rate × total_count)
                 / (prior_weight × decay + total_count)

        Args:
            node:              知识节点
            success_count:     成功次数
            total_count:       总实验次数
            cycle_id:          周期 ID
            days_since_creation: 节点创建后天数（用于衰减）

        Returns:
            (更新后的节点, 更新记录)
        """
        if total_count == 0:
            return node, KnowledgeUpdate(
                node_id=node.node_id,
                old_confidence=node.confidence,
                new_confidence=node.confidence,
                evidence_count=0,
                cycle_id=cycle_id,
                update_reason="No new evidence",
            )

        old_confidence = node.confidence
        new_success_rate = success_count / total_count

        # 衰减
        decay = max(0.5, 1.0 - self.DECAY_FACTOR * days_since_creation)

        # Bayesian 更新
        effective_prior = self.DEFAULT_PRIOR_WEIGHT * decay
        new_confidence = (
            old_confidence * effective_prior + new_success_rate * total_count
        ) / (effective_prior + total_count)

        # 冲突检测
        update_reason = ""
        if abs(new_success_rate - old_confidence) > self.CONFLICT_THRESHOLD:
            if new_success_rate > old_confidence:
                update_reason = f"Strong positive evidence: success_rate={new_success_rate:.2f} >> old_conf={old_confidence:.2f}"
            else:
                update_reason = f"Conflict detected: success_rate={new_success_rate:.2f} << old_conf={old_confidence:.2f}"

        # 更新节点
        node.confidence = round(new_confidence, 4)

        update_record = KnowledgeUpdate(
            node_id=node.node_id,
            old_confidence=old_confidence,
            new_confidence=node.confidence,
            evidence_count=total_count,
            cycle_id=cycle_id,
            update_reason=update_reason or "Bayesian update",
        )

        return node, update_record

    # ── Edge Confidence Update ─────────────────────────────

    def update_edge_confidence(
        self,
        edge: KnowledgeEdge,
        success_count: int,
        total_count: int,
        cycle_id: str = "",
    ) -> tuple[KnowledgeEdge, KnowledgeUpdate]:
        """Bayesian 更新边置信度。

        Args:
            edge:          知识边
            success_count: 成功次数
            total_count:   总实验次数
            cycle_id:      周期 ID

        Returns:
            (更新后的边, 更新记录)
        """
        if total_count == 0:
            return edge, KnowledgeUpdate(
                node_id=f"{edge.source_id}→{edge.target_id}",
                old_confidence=edge.confidence,
                new_confidence=edge.confidence,
                evidence_count=0,
                cycle_id=cycle_id,
                update_reason="No new evidence",
            )

        old_confidence = edge.confidence
        new_success_rate = success_count / total_count

        # Bayesian 更新
        new_confidence = (
            old_confidence * edge.evidence_count + new_success_rate * total_count
        ) / (edge.evidence_count + total_count)

        # 更新 edge
        edge.confidence = round(new_confidence, 4)
        edge.weight = round(new_success_rate, 4)
        edge.evidence_count += total_count

        update_record = KnowledgeUpdate(
            node_id=f"{edge.source_id}→{edge.target_id}",
            old_confidence=old_confidence,
            new_confidence=edge.confidence,
            evidence_count=total_count,
            cycle_id=cycle_id,
            update_reason=f"Bayesian update: {total_count} new experiments",
        )

        return edge, update_record

    # ── Batch Update ───────────────────────────────────────

    def update_nodes_batch(
        self,
        node_results: list[tuple[KnowledgeNode, int, int]],
        cycle_id: str = "",
    ) -> tuple[list[KnowledgeNode], list[KnowledgeUpdate]]:
        """批量更新节点。

        Args:
            node_results: [(node, success_count, total_count), ...]
            cycle_id:     周期 ID

        Returns:
            (更新后的节点列表, 更新记录列表)
        """
        updated_nodes: list[KnowledgeNode] = []
        records: list[KnowledgeUpdate] = []

        for node, success, total in node_results:
            updated_node, record = self.update_node_confidence(
                node, success, total, cycle_id
            )
            updated_nodes.append(updated_node)
            records.append(record)

        return updated_nodes, records

    def update_edges_batch(
        self,
        edge_results: list[tuple[KnowledgeEdge, int, int]],
        cycle_id: str = "",
    ) -> tuple[list[KnowledgeEdge], list[KnowledgeUpdate]]:
        """批量更新边。

        Args:
            edge_results: [(edge, success_count, total_count), ...]
            cycle_id:     周期 ID

        Returns:
            (更新后的边列表, 更新记录列表)
        """
        updated_edges: list[KnowledgeEdge] = []
        records: list[KnowledgeUpdate] = []

        for edge, success, total in edge_results:
            updated_edge, record = self.update_edge_confidence(
                edge, success, total, cycle_id
            )
            updated_edges.append(updated_edge)
            records.append(record)

        return updated_edges, records

    # ── Confidence Decay ───────────────────────────────────

    def apply_decay(
        self,
        node: KnowledgeNode,
        days_since_creation: float,
    ) -> KnowledgeNode:
        """对节点应用时间衰减。

        Args:
            node:               知识节点
            days_since_creation: 创建后天数

        Returns:
            衰减后的节点
        """
        decay = max(0.5, 1.0 - self.DECAY_FACTOR * days_since_creation)
        node.confidence = round(node.confidence * decay, 4)
        return node

    def __repr__(self) -> str:
        return f"KnowledgeUpdater(prior={self.DEFAULT_PRIOR_WEIGHT})"