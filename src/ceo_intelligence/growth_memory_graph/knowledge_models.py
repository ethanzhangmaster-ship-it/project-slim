"""
P3.5 — Growth Knowledge Graph：跨源 consolidated 高层实体模型。

复用 E17.7 的 ``GraphNode`` / ``GraphEdge`` / ``NodeType`` / ``EdgeType``（不新造图模型），
把 5 个分散的 memory 源（E16 Recovery / E17.7 Graph / Strategy Memory / Execution Memory /
Portfolio Memory）沉淀为一套统一的「经验型」高层节点：

    Game
      |- CreativePattern / UAPattern / MonetizationPattern
      |- StrategyResult
      |- ExecutionOutcome
      |- RecoveryHistory
      |- PortfolioDecision

纪律（与全库一致）：纯 dataclass + to_dict / from_dict，无 LLM、无 IO、确定性。
每个实体都提供 to_node() -> GraphNode 与 from_node(cls, node) 以与 E17.7 图互转。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .models import (
    EdgeType,
    GraphNode,
    NodeType,
    node_id,
)

# pattern.kind -> (NodeType, HAS_*_PATTERN EdgeType)
_PATTERN_NODE = {
    "creative": NodeType.CREATIVE_PATTERN,
    "ua": NodeType.UA_PATTERN,
    "monetization": NodeType.MONETIZATION_PATTERN,
}
_PATTERN_EDGE = {
    "creative": EdgeType.HAS_CREATIVE_PATTERN,
    "ua": EdgeType.HAS_UA_PATTERN,
    "monetization": EdgeType.HAS_MONETIZATION_PATTERN,
}
_PATTERN_KINDS = tuple(_PATTERN_NODE.keys())


# --------------------------------------------------------------------------- #
# Creative / UA / Monetization Pattern（统一模型，按 kind 区分节点类型）
# --------------------------------------------------------------------------- #
@dataclass
class GrowthPattern:
    """跨游戏学到的模式（creative / ua / monetization）。

    由 E17.7 extract_patterns(graph) 按 domain 派生；games 是曾经命中该模式的游戏。
    """

    kind: str                      # "creative" | "ua" | "monetization"
    key: str                       # "strategy_type::action_type"
    strategy_type: str = ""
    action_type: str = ""
    success_rate: float = 0.0
    samples: int = 0
    avg_reward: float = 0.0
    games: List[str] = field(default_factory=list)

    def node_id(self) -> str:
        return node_id(_PATTERN_NODE[self.kind], self.key)

    def to_node(self) -> GraphNode:
        return GraphNode(
            id=self.node_id(),
            type=_PATTERN_NODE[self.kind],
            label=f"{self.kind}:{self.key}",
            payload={
                "kind": self.kind,
                "key": self.key,
                "strategy_type": self.strategy_type,
                "action_type": self.action_type,
                "success_rate": round(self.success_rate, 6),
                "samples": int(self.samples),
                "avg_reward": round(self.avg_reward, 6),
                "games": list(self.games),
            },
        )

    @classmethod
    def from_node(cls, n: GraphNode) -> "GrowthPattern":
        p = n.payload
        return cls(
            kind=str(p.get("kind", "")),
            key=str(p.get("key", "")),
            strategy_type=str(p.get("strategy_type", "")),
            action_type=str(p.get("action_type", "")),
            success_rate=float(p.get("success_rate", 0.0)),
            samples=int(p.get("samples", 0)),
            avg_reward=float(p.get("avg_reward", 0.0)),
            games=list(p.get("games", [])),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "key": self.key,
            "strategy_type": self.strategy_type,
            "action_type": self.action_type,
            "success_rate": self.success_rate,
            "samples": self.samples,
            "avg_reward": self.avg_reward,
            "games": list(self.games),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GrowthPattern":
        return cls(
            kind=str(d.get("kind", "")),
            key=str(d.get("key", "")),
            strategy_type=str(d.get("strategy_type", "")),
            action_type=str(d.get("action_type", "")),
            success_rate=float(d.get("success_rate", 0.0)),
            samples=int(d.get("samples", 0)),
            avg_reward=float(d.get("avg_reward", 0.0)),
            games=list(d.get("games", [])),
        )


# --------------------------------------------------------------------------- #
# Strategy Result（来自 P3.3 Strategy Memory / E17.7 pattern）
# --------------------------------------------------------------------------- #
@dataclass
class StrategyResult:
    """策略级长期经验（策略有没有长期价值）。

    来自 StrategyMemoryAdapter.build_insights：historical_success_rate / samples /
    avg_reward / recommendation；confidence / status 取 StrategyState。
    """

    strategy_id: str
    dimension: str = ""
    success_rate: float = 0.0
    samples: int = 0
    avg_reward: float = 0.0
    confidence: float = 0.0
    status: str = "active"
    recommendation: str = "hold"
    rationale: str = ""
    games: List[str] = field(default_factory=list)

    def node_id(self) -> str:
        return node_id(NodeType.STRATEGY_RESULT, self.strategy_id)

    def to_node(self) -> GraphNode:
        return GraphNode(
            id=self.node_id(),
            type=NodeType.STRATEGY_RESULT,
            label=self.strategy_id,
            payload={
                "strategy_id": self.strategy_id,
                "dimension": self.dimension,
                "success_rate": round(self.success_rate, 6),
                "samples": int(self.samples),
                "avg_reward": round(self.avg_reward, 6),
                "confidence": round(self.confidence, 6),
                "status": self.status,
                "recommendation": self.recommendation,
                "rationale": self.rationale,
                "games": list(self.games),
            },
        )

    @classmethod
    def from_node(cls, n: GraphNode) -> "StrategyResult":
        p = n.payload
        return cls(
            strategy_id=str(p.get("strategy_id", "")),
            dimension=str(p.get("dimension", "")),
            success_rate=float(p.get("success_rate", 0.0)),
            samples=int(p.get("samples", 0)),
            avg_reward=float(p.get("avg_reward", 0.0)),
            confidence=float(p.get("confidence", 0.0)),
            status=str(p.get("status", "active")),
            recommendation=str(p.get("recommendation", "hold")),
            rationale=str(p.get("rationale", "")),
            games=list(p.get("games", [])),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "dimension": self.dimension,
            "success_rate": self.success_rate,
            "samples": self.samples,
            "avg_reward": self.avg_reward,
            "confidence": self.confidence,
            "status": self.status,
            "recommendation": self.recommendation,
            "rationale": self.rationale,
            "games": list(self.games),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StrategyResult":
        return cls(
            strategy_id=str(d.get("strategy_id", "")),
            dimension=str(d.get("dimension", "")),
            success_rate=float(d.get("success_rate", 0.0)),
            samples=int(d.get("samples", 0)),
            avg_reward=float(d.get("avg_reward", 0.0)),
            confidence=float(d.get("confidence", 0.0)),
            status=str(d.get("status", "active")),
            recommendation=str(d.get("recommendation", "hold")),
            rationale=str(d.get("rationale", "")),
            games=list(d.get("games", [])),
        )


# --------------------------------------------------------------------------- #
# Execution Outcome（来自 E17.6 Execution Memory，按 game x domain 聚合）
# --------------------------------------------------------------------------- #
@dataclass
class ExecutionOutcome:
    """某游戏某域的历史执行表现（成功率 / 回滚率）。"""

    game_id: str
    domain: str
    success_rate: float = 0.0
    samples: int = 0
    rolled_back_rate: float = 0.0

    def node_id(self) -> str:
        return node_id(NodeType.EXECUTION_OUTCOME, f"{self.game_id}:{self.domain}")

    def to_node(self) -> GraphNode:
        return GraphNode(
            id=self.node_id(),
            type=NodeType.EXECUTION_OUTCOME,
            label=f"{self.game_id}:{self.domain}",
            payload={
                "game_id": self.game_id,
                "domain": self.domain,
                "success_rate": round(self.success_rate, 6),
                "samples": int(self.samples),
                "rolled_back_rate": round(self.rolled_back_rate, 6),
            },
        )

    @classmethod
    def from_node(cls, n: GraphNode) -> "ExecutionOutcome":
        p = n.payload
        return cls(
            game_id=str(p.get("game_id", "")),
            domain=str(p.get("domain", "")),
            success_rate=float(p.get("success_rate", 0.0)),
            samples=int(p.get("samples", 0)),
            rolled_back_rate=float(p.get("rolled_back_rate", 0.0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "domain": self.domain,
            "success_rate": self.success_rate,
            "samples": self.samples,
            "rolled_back_rate": self.rolled_back_rate,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExecutionOutcome":
        return cls(
            game_id=str(d.get("game_id", "")),
            domain=str(d.get("domain", "")),
            success_rate=float(d.get("success_rate", 0.0)),
            samples=int(d.get("samples", 0)),
            rolled_back_rate=float(d.get("rolled_back_rate", 0.0)),
        )


# --------------------------------------------------------------------------- #
# Recovery History（来自 E16 Recovery Experience Store）
# --------------------------------------------------------------------------- #
@dataclass
class RecoveryHistory:
    """某类故障的恢复经验（恢复成功率 / 平均回报）。"""

    failure_type: str
    recovery_strategy: str = ""
    success_rate: float = 0.0
    n: int = 0
    avg_reward: float = 0.0
    game_id: str = ""                 # 单一游戏命中时填；否则空（全局经验）
    games: List[str] = field(default_factory=list)

    def node_id(self) -> str:
        return node_id(
            NodeType.RECOVERY_HISTORY,
            f"{self.failure_type}:{self.recovery_strategy}",
        )

    def to_node(self) -> GraphNode:
        return GraphNode(
            id=self.node_id(),
            type=NodeType.RECOVERY_HISTORY,
            label=f"{self.failure_type}:{self.recovery_strategy}",
            payload={
                "failure_type": self.failure_type,
                "recovery_strategy": self.recovery_strategy,
                "success_rate": round(self.success_rate, 6),
                "n": int(self.n),
                "avg_reward": round(self.avg_reward, 6),
                "game_id": self.game_id,
                "games": list(self.games),
            },
        )

    @classmethod
    def from_node(cls, n: GraphNode) -> "RecoveryHistory":
        p = n.payload
        return cls(
            failure_type=str(p.get("failure_type", "")),
            recovery_strategy=str(p.get("recovery_strategy", "")),
            success_rate=float(p.get("success_rate", 0.0)),
            n=int(p.get("n", 0)),
            avg_reward=float(p.get("avg_reward", 0.0)),
            game_id=str(p.get("game_id", "")),
            games=list(p.get("games", [])),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "failure_type": self.failure_type,
            "recovery_strategy": self.recovery_strategy,
            "success_rate": self.success_rate,
            "n": self.n,
            "avg_reward": self.avg_reward,
            "game_id": self.game_id,
            "games": list(self.games),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RecoveryHistory":
        return cls(
            failure_type=str(d.get("failure_type", "")),
            recovery_strategy=str(d.get("recovery_strategy", "")),
            success_rate=float(d.get("success_rate", 0.0)),
            n=int(d.get("n", 0)),
            avg_reward=float(d.get("avg_reward", 0.0)),
            game_id=str(d.get("game_id", "")),
            games=list(d.get("games", [])),
        )


# --------------------------------------------------------------------------- #
# Portfolio Decision（来自 P3.4.5 PortfolioOptimizationResult / ProposalItem）
# --------------------------------------------------------------------------- #
@dataclass
class PortfolioDecision:
    """单游戏的跨游戏资源分配建议（只建议不执行）。

    直接来自 PortfolioProposal.items[]；guard 是三态
    （AUTO / APPROVAL / BLOCKED），status 是优化结果总状态。
    """

    game_id: str
    recommendation: str = ""         # scale / maintain / reduce / sunset / no_scale
    confidence: float = 0.0
    priority: float = 0.0
    guard: str = "auto"              # ActionState.value
    status: str = ""                 # OptimizationStatus.value
    optimization_id: str = ""
    rank: int = 0

    def node_id(self) -> str:
        return node_id(NodeType.PORTFOLIO_DECISION, self.game_id)

    def to_node(self) -> GraphNode:
        return GraphNode(
            id=self.node_id(),
            type=NodeType.PORTFOLIO_DECISION,
            label=f"{self.game_id}:{self.recommendation}",
            payload={
                "game_id": self.game_id,
                "recommendation": self.recommendation,
                "confidence": round(self.confidence, 6),
                "priority": round(self.priority, 6),
                "guard": self.guard,
                "status": self.status,
                "optimization_id": self.optimization_id,
                "rank": int(self.rank),
            },
        )

    @classmethod
    def from_node(cls, n: GraphNode) -> "PortfolioDecision":
        p = n.payload
        return cls(
            game_id=str(p.get("game_id", "")),
            recommendation=str(p.get("recommendation", "")),
            confidence=float(p.get("confidence", 0.0)),
            priority=float(p.get("priority", 0.0)),
            guard=str(p.get("guard", "auto")),
            status=str(p.get("status", "")),
            optimization_id=str(p.get("optimization_id", "")),
            rank=int(p.get("rank", 0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "priority": self.priority,
            "guard": self.guard,
            "status": self.status,
            "optimization_id": self.optimization_id,
            "rank": self.rank,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioDecision":
        return cls(
            game_id=str(d.get("game_id", "")),
            recommendation=str(d.get("recommendation", "")),
            confidence=float(d.get("confidence", 0.0)),
            priority=float(d.get("priority", 0.0)),
            guard=str(d.get("guard", "auto")),
            status=str(d.get("status", "")),
            optimization_id=str(d.get("optimization_id", "")),
            rank=int(d.get("rank", 0)),
        )


__all__ = [
    "GrowthPattern",
    "StrategyResult",
    "ExecutionOutcome",
    "RecoveryHistory",
    "PortfolioDecision",
    "PATTERN_KINDS",
    "pattern_node_type",
    "pattern_edge_type",
]
