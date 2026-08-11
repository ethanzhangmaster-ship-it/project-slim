"""P3.3 — Strategy Loop 模型层。

Strategy Feedback Controller 的全部数据结构。纯 dataclass + to_dict / from_dict，
无 LLM、无 IO、确定性（同数据同输出）。

纪律（与全库一致）：
- str-Enum 序列化用 .value 归一化（py3.11 str(Enum) 兼容陷阱）
- 不重新计算业务指标，只承载「读出来的结果 + 策略级经验」
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


def _as_str(v: Any) -> str:
    """py3.11 str-Enum 序列化归一化（与 P2.3 / operator.models 同纪律）。"""
    return str(getattr(v, "value", v))


class StrategyStatus(str, Enum):
    """策略长期状态。"""

    ACTIVE = "active"
    LEARNING = "learning"
    DISABLED = "disabled"


@dataclass
class StrategyState:
    """策略长期状态（P3.3 新增的 strategy-level 经验单元）。

    与 E17.7 的 action-level GraphPattern 解耦：E17.7 记「这个动作有没有用」，
    这里记「这个策略组合有没有长期价值」，并持久化于 strategy_memory.jsonl。
    """

    strategy_id: str
    dimension: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    performance: Dict[str, Any] = field(default_factory=dict)
    status: StrategyStatus = StrategyStatus.ACTIVE

    def __post_init__(self) -> None:
        # 保证 performance 至少有计数键，下游逻辑可直接累加
        p = self.performance
        for k in ("wins", "losses", "reward_sum", "samples",
                  "consecutive_failures", "last_outcome"):
            p.setdefault(k, 0)

    # -- 派生指标 -------------------------------------------------------- #
    @property
    def samples(self) -> int:
        return int(self.performance.get("samples", 0))

    @property
    def success_rate(self) -> float:
        s = self.samples
        return (int(self.performance.get("wins", 0)) / s) if s else 0.0

    @property
    def disabled(self) -> bool:
        return self.status == StrategyStatus.DISABLED

    # -- 序列化 ---------------------------------------------------------- #
    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "dimension": self.dimension,
            "parameters": dict(self.parameters),
            "confidence": round(float(self.confidence), 6),
            "performance": dict(self.performance),
            "status": _as_str(self.status),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StrategyState":
        return cls(
            strategy_id=str(d["strategy_id"]),
            dimension=str(d.get("dimension", "")),
            parameters=dict(d.get("parameters", {})),
            confidence=float(d.get("confidence", 0.5)),
            performance=dict(d.get("performance", {})),
            status=StrategyStatus(str(d.get("status", "active"))),
        )


@dataclass
class BusinessOutcome:
    """业务结果快照（用于 evaluator 推导 reward）。"""

    metric: str            # "ecpm" / "roas" / "revenue"
    before: float
    after: float
    unit: str = ""

    def delta_ratio(self) -> float:
        if self.before == 0:
            return 1.0 if self.after > 0 else (-1.0 if self.after < 0 else 0.0)
        return (self.after - self.before) / abs(self.before)


@dataclass
class StrategyFeedback:
    """单次动作 → 策略反馈（P3.3.1 核心产物）。

    由 OutcomeEvaluator 把 Action + ExecutionResult + BusinessOutcome 聚合成此结构。
    """

    action_id: str
    strategy_id: str
    reward: float
    outcome: str           # "SUCCESS" / "FAILURE" / "NEUTRAL"
    evidence: str
    timestamp: str = ""    # 空串（确定性）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "strategy_id": self.strategy_id,
            "reward": round(float(self.reward), 6),
            "outcome": self.outcome,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StrategyFeedback":
        return cls(
            action_id=str(d["action_id"]),
            strategy_id=str(d["strategy_id"]),
            reward=float(d["reward"]),
            outcome=str(d["outcome"]),
            evidence=str(d.get("evidence", "")),
            timestamp=str(d.get("timestamp", "")),
        )


@dataclass
class StrategyProposal:
    """建议修改策略（不是 Decision）。只进 Simulation Queue，不执行。"""

    current_strategy: str
    proposed_change: str
    expected_impact: str
    confidence: float
    requires_simulation: bool = True
    # P3.5.1：经验增强（可选，默认空；不覆盖原 confidence，仅供 CEO/Guard 参考）
    knowledge_signal: Optional[Dict[str, Any]] = None   # KnowledgeSignal.to_dict()
    knowledge_confidence: Optional[float] = None       # 经验降权后的有效置信

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_strategy": self.current_strategy,
            "proposed_change": self.proposed_change,
            "expected_impact": self.expected_impact,
            "confidence": round(float(self.confidence), 6),
            "requires_simulation": bool(self.requires_simulation),
            "knowledge_signal": self.knowledge_signal,
            "knowledge_confidence": (
                round(float(self.knowledge_confidence), 6)
                if self.knowledge_confidence is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StrategyProposal":
        return cls(
            current_strategy=str(d["current_strategy"]),
            proposed_change=str(d["proposed_change"]),
            expected_impact=str(d.get("expected_impact", "")),
            confidence=float(d.get("confidence", 0.0)),
            requires_simulation=bool(d.get("requires_simulation", True)),
            knowledge_signal=d.get("knowledge_signal"),
            knowledge_confidence=(
                float(d["knowledge_confidence"])
                if d.get("knowledge_confidence") is not None
                else None
            ),
        )


@dataclass
class StrategyInsight:
    """P3.3.1 交付物：过去执行结果 → 策略洞察。"""

    strategy_id: str
    dimension: str
    historical_success_rate: float
    samples: int
    avg_reward: float
    recommendation: str       # "boost" / "reduce" / "disable" / "hold"
    rationale: str

    def to_line(self) -> str:
        """喂给 CEO 决策单「今日学习」段的单行洞察。"""
        pct = f"{self.historical_success_rate * 100:.1f}%"
        return (
            f"[{self.strategy_id}] 历史成功率 {pct}（样本 {self.samples}）"
            f" → 建议：{self.recommendation}。{self.rationale}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "dimension": self.dimension,
            "historical_success_rate": round(float(self.historical_success_rate), 6),
            "samples": int(self.samples),
            "avg_reward": round(float(self.avg_reward), 6),
            "recommendation": self.recommendation,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StrategyInsight":
        return cls(
            strategy_id=str(d["strategy_id"]),
            dimension=str(d.get("dimension", "")),
            historical_success_rate=float(d.get("historical_success_rate", 0.0)),
            samples=int(d.get("samples", 0)),
            avg_reward=float(d.get("avg_reward", 0.0)),
            recommendation=str(d.get("recommendation", "hold")),
            rationale=str(d.get("rationale", "")),
        )


@dataclass
class StrategyLoopResult:
    """一轮 Strategy Loop 的交付物。"""

    insights: List[StrategyInsight] = field(default_factory=list)
    proposals: List[StrategyProposal] = field(default_factory=list)
    states: Dict[str, StrategyState] = field(default_factory=dict)
    feedbacks: List[StrategyFeedback] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)  # 喂 CEO 决策单的洞察行
    # P3.3.3：过闸的安全动作提案 → 真实闭环（AdaptiveStrategyResult 列表）
    adaptive: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "insights": [i.to_dict() for i in self.insights],
            "proposals": [p.to_dict() for p in self.proposals],
            "states": {k: v.to_dict() for k, v in self.states.items()},
            "feedbacks": [f.to_dict() for f in self.feedbacks],
            "patterns": list(self.patterns),
            "adaptive": [
                (r.to_dict() if hasattr(r, "to_dict") else r) for r in self.adaptive
            ],
        }


__all__ = [
    "StrategyStatus",
    "StrategyState",
    "BusinessOutcome",
    "StrategyFeedback",
    "StrategyProposal",
    "StrategyInsight",
    "StrategyLoopResult",
]
