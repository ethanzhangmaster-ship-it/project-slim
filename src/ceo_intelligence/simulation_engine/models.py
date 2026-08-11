"""E17.8 Growth Simulation Engine — 模型层。

三级执行门中一直缺席的「Simulation 门」：
Recommendation(E17.2) → **Simulation(E17.8)** → Approval(E17.3) → Execution(E17.6)

约定（与 E17.1–E17.7 / E16 一致）：
- 纯 dataclass + to_dict / from_dict，无 LLM、无 IO
- 确定性：分布来自固定网格采样（engine），可复现到 1e-6
- SIM 纪律：summary.real_api_called 永远 False
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List


# --------------------------------------------------------------------------- #
# 情景（what-if 旋钮）
# --------------------------------------------------------------------------- #
@dataclass
class SimulationScenario:
    """一个 what-if 情景：对先验均值/风险的确定性乘子。"""
    id: str
    label: str
    revenue_multiplier: float = 1.0
    roas_multiplier: float = 1.0
    risk_multiplier: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SimulationScenario":
        return cls(
            id=str(d["id"]),
            label=str(d.get("label", d["id"])),
            revenue_multiplier=float(d.get("revenue_multiplier", 1.0)),
            roas_multiplier=float(d.get("roas_multiplier", 1.0)),
            risk_multiplier=float(d.get("risk_multiplier", 1.0)),
        )


# 默认三情景：基线 / 乐观 / 悲观（确定性查表，可被调用方覆盖）
DEFAULT_SCENARIOS: List[SimulationScenario] = [
    SimulationScenario("baseline", "基线", 1.0, 1.0, 1.0),
    SimulationScenario("optimistic", "乐观", 1.25, 1.15, 0.85),
    SimulationScenario("pessimistic", "悲观", 0.70, 0.85, 1.30),
]


# --------------------------------------------------------------------------- #
# 先验（静态基线 + 记忆图谱加成）
# --------------------------------------------------------------------------- #
@dataclass
class SimulationPrior:
    """模拟先验：E17.3 静态基线 + E17.7 记忆图谱先验的混合结果。"""
    opportunity_type: str
    expected_revenue_change: float = 0.0
    expected_roas_change: float = 0.0
    confidence: float = 0.0
    risk: float = 0.0
    memory_boost: float = 0.0        # E17.7 confidence_boost_for 的加成
    avg_revenue_delta: float = 0.0   # E17.7 record_outcome 回填的实得均值
    samples: int = 0                 # 记忆样本数（<2 时不启用记忆混合）
    source: str = "static"           # static | static+memory

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SimulationPrior":
        return cls(
            opportunity_type=str(d.get("opportunity_type", "")),
            expected_revenue_change=float(d.get("expected_revenue_change", 0.0)),
            expected_roas_change=float(d.get("expected_roas_change", 0.0)),
            confidence=float(d.get("confidence", 0.0)),
            risk=float(d.get("risk", 0.0)),
            memory_boost=float(d.get("memory_boost", 0.0)),
            avg_revenue_delta=float(d.get("avg_revenue_delta", 0.0)),
            samples=int(d.get("samples", 0)),
            source=str(d.get("source", "static")),
        )


# --------------------------------------------------------------------------- #
# 分布与情景产出
# --------------------------------------------------------------------------- #
@dataclass
class OutcomeDistribution:
    """一个指标的情景分布（p10 / p50 / p90 / mean）。"""
    p10: float = 0.0
    p50: float = 0.0
    p90: float = 0.0
    mean: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OutcomeDistribution":
        return cls(
            p10=float(d.get("p10", 0.0)),
            p50=float(d.get("p50", 0.0)),
            p90=float(d.get("p90", 0.0)),
            mean=float(d.get("mean", 0.0)),
        )


@dataclass
class ScenarioOutcome:
    """一个决策在一个情景下的模拟产出。"""
    scenario_id: str
    revenue: OutcomeDistribution = field(default_factory=OutcomeDistribution)
    roas: OutcomeDistribution = field(default_factory=OutcomeDistribution)
    confidence: float = 0.0
    risk: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "revenue": self.revenue.to_dict(),
            "roas": self.roas.to_dict(),
            "confidence": self.confidence,
            "risk": self.risk,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ScenarioOutcome":
        return cls(
            scenario_id=str(d["scenario_id"]),
            revenue=OutcomeDistribution.from_dict(d.get("revenue", {})),
            roas=OutcomeDistribution.from_dict(d.get("roas", {})),
            confidence=float(d.get("confidence", 0.0)),
            risk=float(d.get("risk", 0.0)),
        )


# --------------------------------------------------------------------------- #
# 执行前闸门
# --------------------------------------------------------------------------- #
class PreFlightStatus(str, Enum):
    PASS = "pass"        # 可放行进入 Approval/Execution
    REVIEW = "review"    # 需人工复核（高风险 / 低置信 / 下行深）
    BLOCK = "block"      # 阻断（负期望），不得进入执行


@dataclass
class PreFlightFlag:
    """执行前闸门结论。"""
    status: PreFlightStatus = PreFlightStatus.PASS
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"status": self.status.value, "reason": self.reason}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PreFlightFlag":
        return cls(
            status=PreFlightStatus(d.get("status", "pass")),
            reason=str(d.get("reason", "")),
        )


# --------------------------------------------------------------------------- #
# 决策级 / 组合级模拟结果
# --------------------------------------------------------------------------- #
@dataclass
class DecisionSimulation:
    """一个 GrowthDecision 的完整模拟：先验 + 各情景分布 + 闸门。"""
    game_id: str
    opportunity_id: str
    action: str
    decision_type: str
    prior: SimulationPrior
    outcomes: List[ScenarioOutcome] = field(default_factory=list)
    flag: PreFlightFlag = field(default_factory=PreFlightFlag)
    decision_audit_id: str = ""

    def outcome(self, scenario_id: str) -> ScenarioOutcome:
        for o in self.outcomes:
            if o.scenario_id == scenario_id:
                return o
        raise KeyError(f"scenario not simulated: {scenario_id}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "opportunity_id": self.opportunity_id,
            "action": self.action,
            "decision_type": self.decision_type,
            "prior": self.prior.to_dict(),
            "outcomes": [o.to_dict() for o in self.outcomes],
            "flag": self.flag.to_dict(),
            "decision_audit_id": self.decision_audit_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DecisionSimulation":
        return cls(
            game_id=str(d["game_id"]),
            opportunity_id=str(d.get("opportunity_id", "")),
            action=str(d.get("action", "")),
            decision_type=str(d.get("decision_type", "")),
            prior=SimulationPrior.from_dict(d.get("prior", {})),
            outcomes=[ScenarioOutcome.from_dict(x) for x in d.get("outcomes", [])],
            flag=PreFlightFlag.from_dict(d.get("flag", {})),
            decision_audit_id=str(d.get("decision_audit_id", "")),
        )


@dataclass
class CounterfactualComparison:
    """反事实 A/B 对比：同一决策在两个情景下的 p50 差。"""
    game_id: str
    opportunity_id: str
    scenario_a: str
    scenario_b: str
    revenue_p50_delta: float = 0.0   # a - b
    roas_p50_delta: float = 0.0
    winner: str = ""                 # revenue p50 更高的情景 id

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CounterfactualComparison":
        return cls(
            game_id=str(d.get("game_id", "")),
            opportunity_id=str(d.get("opportunity_id", "")),
            scenario_a=str(d["scenario_a"]),
            scenario_b=str(d["scenario_b"]),
            revenue_p50_delta=float(d.get("revenue_p50_delta", 0.0)),
            roas_p50_delta=float(d.get("roas_p50_delta", 0.0)),
            winner=str(d.get("winner", "")),
        )


@dataclass
class PortfolioSimulationReport:
    """E17.8 主输出：组合级模拟报告（CEO 执行前视图）。"""
    created_at: str = ""
    total_decisions: int = 0
    simulations: List[DecisionSimulation] = field(default_factory=list)
    portfolio: Dict[str, OutcomeDistribution] = field(default_factory=dict)
    comparisons: List[CounterfactualComparison] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def blocked_decision_ids(self) -> List[str]:
        """被闸门 BLOCK 的 decision audit_id（供 pipeline 挡在 E17.6 之外）。"""
        return [
            s.decision_audit_id
            for s in self.simulations
            if s.flag.status == PreFlightStatus.BLOCK and s.decision_audit_id
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "created_at": self.created_at,
            "total_decisions": self.total_decisions,
            "simulations": [s.to_dict() for s in self.simulations],
            "portfolio": {k: v.to_dict() for k, v in self.portfolio.items()},
            "comparisons": [c.to_dict() for c in self.comparisons],
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioSimulationReport":
        return cls(
            created_at=str(d.get("created_at", "")),
            total_decisions=int(d.get("total_decisions", 0)),
            simulations=[
                DecisionSimulation.from_dict(x) for x in d.get("simulations", [])
            ],
            portfolio={
                k: OutcomeDistribution.from_dict(v)
                for k, v in d.get("portfolio", {}).items()
            },
            comparisons=[
                CounterfactualComparison.from_dict(x)
                for x in d.get("comparisons", [])
            ],
            summary=dict(d.get("summary", {})),
        )

    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append("# 组合模拟报告（Growth Simulation Engine · 执行前闸门）")
        lines.append("")
        s = self.summary
        lines.append(f"- 模拟决策数：**{self.total_decisions}**")
        lines.append(
            f"- 闸门结论：放行 {s.get('pass', 0)} / 复核 {s.get('review', 0)}"
            f" / 阻断 {s.get('block', 0)}"
        )
        base = self.portfolio.get("baseline")
        if base:
            lines.append(
                f"- 组合收入变化（基线情景）：p10 {base.p10:+.1%} / "
                f"p50 **{base.p50:+.1%}** / p90 {base.p90:+.1%}"
            )
        lines.append(f"- real_api_called：{s.get('real_api_called', False)}")
        lines.append("")
        if self.simulations:
            lines.append("## 决策级模拟（基线情景）")
            lines.append("")
            for sim in self.simulations:
                try:
                    o = sim.outcome("baseline")
                except KeyError:
                    continue
                lines.append(
                    f"- **{sim.game_id}** — {sim.action} "
                    f"| p50 {o.revenue.p50:+.1%} (p10 {o.revenue.p10:+.1%}) "
                    f"| 置信 {o.confidence:.0%} | 风险 {o.risk:.0%} "
                    f"| 闸门 {sim.flag.status.value}"
                    + (f"（{sim.flag.reason}）" if sim.flag.reason else "")
                )
        return "\n".join(lines)


__all__ = [
    "SimulationScenario",
    "DEFAULT_SCENARIOS",
    "SimulationPrior",
    "OutcomeDistribution",
    "ScenarioOutcome",
    "PreFlightStatus",
    "PreFlightFlag",
    "DecisionSimulation",
    "CounterfactualComparison",
    "PortfolioSimulationReport",
]
