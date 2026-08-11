"""E17.4 Growth Strategy Planner — 模型层。

把 E17.3 的「公司级决策」转成「可执行的经营作战计划」。

约定（与 E17.1 / E17.2 / E17.3 一致）：
- 纯 dataclass + to_dict / from_dict，无 LLM、无 IO
- StrategyType 复用 OpportunityType.value 作为键，便于模板查表与记忆闭环
- StrategyTask.dependency 用「前置任务的 order（字符串）」引用，供 StrategyGraph 拓扑排序
- 额外字段（expected_value / decision_type_value / quality_gate_passed / gate_reasons /
  needs_approval）是对 spec 核心模型的有用补强，不影响既有契约
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from src.ceo_intelligence.decision_engine.models import GrowthDecision


class StrategyType(str, Enum):
    """策略类型 = 决策动作（与 OpportunityType.value 对齐）。"""
    CREATIVE_REFRESH = "creative_refresh"
    UA_SCALE = "ua_scale"
    UA_STOP_LOSS = "ua_stop_loss"
    ASO_OPTIMIZATION = "aso_optimization"
    MONETIZATION = "monetization"
    REVENUE_RECOVERY = "revenue_recovery"
    RETENTION = "retention"
    RELEASE_HEALTH = "release_health"


def strategy_type_from_decision(decision: GrowthDecision) -> str:
    """从 decision.opportunity_id（格式 game_id:type）解析策略类型。"""
    return decision.opportunity_id.rsplit(":", 1)[-1]


class StrategyQualityError(Exception):
    """策略未通过质量门禁时抛出（create_plan 默认 strict=True）。"""


@dataclass
class StrategyTask:
    order: int
    owner: str
    action: str
    dependency: List[str] = field(default_factory=list)
    expected_output: str = ""
    deadline: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StrategyTask":
        return cls(
            order=int(d["order"]),
            owner=str(d["owner"]),
            action=str(d["action"]),
            dependency=list(d.get("dependency", [])),
            expected_output=str(d.get("expected_output", "")),
            deadline=str(d.get("deadline", "")),
        )


@dataclass
class GrowthStrategyPlan:
    game_id: str
    decision_id: str
    objective: str
    strategy_type: str
    tasks: List[StrategyTask] = field(default_factory=list)
    success_metrics: Dict[str, Any] = field(default_factory=dict)
    rollback_plan: str = ""
    estimated_duration_days: int = 0
    confidence: float = 0.0
    expected_value: float = 0.0
    created_at: str = ""
    decision_type_value: str = ""
    quality_gate_passed: bool = True
    gate_reasons: List[str] = field(default_factory=list)
    needs_approval: bool = False

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.decision_id:
            self.decision_id = f"plan_{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "decision_id": self.decision_id,
            "objective": self.objective,
            "strategy_type": self.strategy_type,
            "tasks": [t.to_dict() for t in self.tasks],
            "success_metrics": self.success_metrics,
            "rollback_plan": self.rollback_plan,
            "estimated_duration_days": self.estimated_duration_days,
            "confidence": self.confidence,
            "expected_value": self.expected_value,
            "created_at": self.created_at,
            "decision_type_value": self.decision_type_value,
            "quality_gate_passed": self.quality_gate_passed,
            "gate_reasons": self.gate_reasons,
            "needs_approval": self.needs_approval,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GrowthStrategyPlan":
        return cls(
            game_id=d["game_id"],
            decision_id=d.get("decision_id", ""),
            objective=d.get("objective", ""),
            strategy_type=d.get("strategy_type", ""),
            tasks=[StrategyTask.from_dict(t) for t in d.get("tasks", [])],
            success_metrics=dict(d.get("success_metrics", {})),
            rollback_plan=d.get("rollback_plan", ""),
            estimated_duration_days=int(d.get("estimated_duration_days", 0)),
            confidence=float(d.get("confidence", 0.0)),
            expected_value=float(d.get("expected_value", 0.0)),
            created_at=d.get("created_at", ""),
            decision_type_value=d.get("decision_type_value", ""),
            quality_gate_passed=bool(d.get("quality_gate_passed", True)),
            gate_reasons=list(d.get("gate_reasons", [])),
            needs_approval=bool(d.get("needs_approval", False)),
        )

    def to_markdown(self) -> str:
        lines: List[str] = [f"# 作战计划：{self.game_id} — {self.strategy_type}", ""]
        lines.append(f"- 目标：{self.objective}")
        lines.append(f"- 预期收益提升：{self.expected_value:+.1%}")
        lines.append(
            f"- 周期：{self.estimated_duration_days} 天 ｜ 置信：{self.confidence:.0%} "
            f"｜ 出口：{self.decision_type_value} ｜ 需审批：{'是' if self.needs_approval else '否'}"
        )
        lines.append(f"- 回滚：{self.rollback_plan}")
        lines.append(
            f"- 质量门禁：{'通过' if self.quality_gate_passed else '未通过 — ' + '; '.join(self.gate_reasons)}"
        )
        lines.append("")
        lines.append("## 任务清单")
        for t in sorted(self.tasks, key=lambda x: x.order):
            dep = f"（依赖 {','.join(t.dependency)}）" if t.dependency else ""
            lines.append(
                f"{t.order}. [{t.owner}] {t.action}（截止 Day {t.deadline}）产出：{t.expected_output} {dep}"
            )
        lines.append("")
        lines.append(f"成功标准：{_fmt_metrics(self.success_metrics)}")
        return "\n".join(lines)


@dataclass
class StrategyValidationResult:
    ok: bool
    reasons: List[str] = field(default_factory=list)
    needs_approval: bool = False


@dataclass
class PortfolioStrategyPlan:
    plans: List[GrowthStrategyPlan] = field(default_factory=list)
    rejected: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_markdown(self) -> str:
        s = self.summary
        lines: List[str] = ["# 每周经营作战计划（Growth Strategy Planner · CEO Brain）", ""]
        lines.append(
            f"- 计划数：**{s.get('planned', 0)}** ｜ 拒绝：**{s.get('rejected', 0)}** "
            f"｜ 需审批：**{s.get('needs_approval', 0)}**"
        )
        lines.append(f"- 组合预期收益提升：**{s.get('total_expected_uplift', 0.0):+.1%}**")
        lines.append("")
        if self.plans:
            lines.append("## 本周重点")
            lines.append("")
            for i, p in enumerate(self.plans, 1):
                lines.append(f"{i}. **{p.game_id}** — {p.strategy_type}（{p.objective}）")
                lines.append(
                    f"   预期收益：{p.expected_value:+.1%} ｜ 周期：{p.estimated_duration_days} 天 "
                    f"｜ 置信：{p.confidence:.0%} ｜ 出口：{p.decision_type_value}"
                )
                lines.append("   关键里程碑：")
                for t in sorted(p.tasks, key=lambda x: x.order):
                    dep = f"（依赖 {','.join(t.dependency)}）" if t.dependency else ""
                    lines.append(f"     · Day {t.deadline}  [{t.owner}] {t.action} {dep}")
                lines.append(f"   成功标准：{_fmt_metrics(p.success_metrics)}")
                lines.append(f"   回滚：{p.rollback_plan}")
                lines.append("")
        if self.rejected:
            lines.append("## 被质量门禁拒绝")
            for r in self.rejected:
                lines.append(f"- {r.get('game_id', '')}：{r.get('reason', '')}")
        return "\n".join(lines)


def _fmt_metrics(m: Dict[str, Any]) -> str:
    return "，".join(f"{k} {v}" for k, v in m.items()) or "—"


__all__ = [
    "StrategyType",
    "strategy_type_from_decision",
    "StrategyQualityError",
    "StrategyTask",
    "GrowthStrategyPlan",
    "StrategyValidationResult",
    "PortfolioStrategyPlan",
]
