"""P3.4.4 — Portfolio Decision Proposal（组合层决策建议生成器）。

定位：把 P3.4.3 的 ``AllocationSimulationResult`` 转换成一份**人可读、带证据链、只建议不执行**
的 ``PortfolioProposal``。

与上下游的关系：

```
P3.4.3 AllocationSimulationResult（只模拟不执行）
   │  本模块 consume
   ▼
PortfolioProposal（recommendation-only）
   │  经 E17.3 Decision Review → P2 Approval → 执行链
   ▼
PortfolioRecommendation（P3.4.5 顶层聚合，挂 CEO 报告）
```

本模块内嵌契约 §7 的 **Rule0~3 安全闸门**（``PortfolioGuard``）：

- Rule0  无现实数据（has_reality=False）→ BLOCKED
- Rule2  Reality confidence < 0.5        → BLOCKED
- Rule3  观察窗口不足（data_age_days<7） → NO_SCALE + BLOCKED（data_age_days 由上游可选注入）
- Rule1  |delta| / max(spend, eps) > 0.30 → APPROVAL（保留 delta，升级人工审批）
- 默认   AUTO

纪律红线（继承 P3.4 + 用户 P3.4.4 边界）：

- ❌ 不预测收入（无 ``new_revenue = old_revenue * multiplier``）。
- ❌ 不重算 ROAS / spend / revenue；只读 snapshot 既有值。
- ❌ 不修改 E17.3 Decision；不替代 StrategyMutation；不调 Provider。
- ❌ 不产生执行请求、不绕过 P2.3 Approval、不自动调预算——本层只产出建议文本与三态标记。
- ✅ ``real_api_called`` 恒为 ``False``（纯分析层，由 :data:`REAL_API_CALLED` 锁死）。
- ✅ 三态严格复用 P3.2 ``ActionState.AUTO / APPROVAL / BLOCKED``，不新造枚举。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from src.operator.report.models import ActionState

from .allocation_models import AllocationSimulationResult, REAL_API_CALLED
from .constraints import AllocationConstraints
from .models import GamePortfolioSnapshot, PortfolioSnapshot, _r
from .ranking_models import AllocationCandidate, PortfolioVerdict

# --------------------------------------------------------------------------- #
# 安全闸门 Rule 编号（契约 §7，便于 evidence / reason 直接引用）
# --------------------------------------------------------------------------- #
RULE0 = "rule0_no_reality"
RULE1 = "rule1_large_shift_approval"
RULE2 = "rule2_low_confidence"
RULE3 = "rule3_insufficient_data_age"

# Rule 阈值（确定性常量，不暴露为可配字段）
_GUARD_LARGE_SHIFT_RATIO = 0.30     # |delta| / max(spend, eps) 超过 → APPROVAL
_CONFIDENCE_BLOCK_THRESHOLD = 0.5  # Rule2：confidence < 0.5 → BLOCKED
_MIN_DATA_AGE_DAYS = 7             # Rule3：data_age_days < 7 → NO_SCALE + BLOCKED
_EPS = 1e-6
# 模拟整体被约束阻断时，提案置信的折损系数（分析仍有信息量，但不可直接落地）。
_SIM_BLOCK_CONF_PENALTY = 0.5
# APPROVAL 项相对 AUTO 项在「可自动落地置信」中的权重（需人工审批 → 折半）。
_APPROVAL_CONF_WEIGHT = 0.5


class ProposalGuardVerdict(str, Enum):
    """提案级闸门总判定（**不是**单游戏三态 ``ActionState``）。"""

    PROPOSABLE = "proposable"   # 全部 AUTO，方案可直接进入人工评审
    PARTIAL = "partial"         # 含 APPROVAL，需人工审批后落地
    BLOCKED = "blocked"         # 含 BLOCKED 或模拟整体被约束阻断


@dataclass
class GuardOutcome:
    """``PortfolioGuard`` 对单游戏的一次闸门判定结果。"""

    action_state: ActionState
    triggered_rules: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_state": self.action_state.value,
            "triggered_rules": list(self.triggered_rules),
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GuardOutcome":
        return cls(
            action_state=ActionState(d.get("action_state", "auto")),
            triggered_rules=list(d.get("triggered_rules", [])),
            evidence=list(d.get("evidence", [])),
        )


class PortfolioGuard:
    """Rule0~3 安全闸门（纯函数式，无外部依赖）。

    判定单游戏的 ``ActionState``（AUTO / APPROVAL / BLOCKED）：
    Rule0 / Rule2 / Rule3 为硬阻断；Rule1 为升级审批（保留 delta）。
    """

    def evaluate(
        self,
        game: GamePortfolioSnapshot,
        delta: float,
        current_spend: float,
        data_age_days: Optional[int] = None,
    ) -> GuardOutcome:
        """对单游戏执行 Rule0~3。

        参数
        ----
        game:          单游戏只读快照（提供 has_reality / confidence）。
        delta:         模拟资源变动（来自 P3.4.3）。
        current_spend: 当前预算占用（baseline amount）。
        data_age_days: 可选注入的观察天数（来自 P3.4 自跟踪 registry；
                        ``None`` 表示未提供 → 跳过 Rule3）。

        返回
        ----
        ``GuardOutcome``：``action_state`` / 触发的规则编号 / 证据文本。
        """
        triggered: List[str] = []
        evidence: List[str] = []

        # —— Rule0：无现实数据不决策 ——
        if not game.has_reality:
            triggered.append(RULE0)
            evidence.append("has_reality=False (no revenue/spend/roas observed)")
            return GuardOutcome(ActionState.BLOCKED, triggered, evidence)

        # —— Rule2：Reality Confidence 不足 ——
        conf = game.confidence if game.confidence is not None else 0.0
        if conf < _CONFIDENCE_BLOCK_THRESHOLD - _EPS:
            triggered.append(RULE2)
            evidence.append(
                f"confidence={conf:.3f}<{_CONFIDENCE_BLOCK_THRESHOLD} → BLOCKED"
            )
            return GuardOutcome(ActionState.BLOCKED, triggered, evidence)

        # —— Rule3：观察窗口不足（仅当上游注入了 data_age_days）——
        if data_age_days is not None and data_age_days < _MIN_DATA_AGE_DAYS:
            triggered.append(RULE3)
            evidence.append(
                f"data_age_days={data_age_days}<{_MIN_DATA_AGE_DAYS} → "
                f"NO_SCALE + BLOCKED"
            )
            return GuardOutcome(ActionState.BLOCKED, triggered, evidence)

        # —— Rule1：大额挪动 → 升级审批（保留 delta，不阻断）——
        denom = max(current_spend, _EPS)
        shift_ratio = (abs(delta) / denom) if denom > 0 else 0.0
        if shift_ratio > _GUARD_LARGE_SHIFT_RATIO + _EPS:
            triggered.append(RULE1)
            evidence.append(
                f"|delta|/spend={shift_ratio:.3f}>{_GUARD_LARGE_SHIFT_RATIO} "
                f"→ APPROVAL required"
            )
            return GuardOutcome(ActionState.APPROVAL, triggered, evidence)

        # —— 默认：可自动建议 ——
        return GuardOutcome(ActionState.AUTO, triggered, evidence)


@dataclass
class ProposalItem:
    """单游戏的一条决策建议（含证据链）。"""

    game_id: str
    rank: int
    recommended_action: PortfolioVerdict     # 可能经 Rule3 降级为 NO_SCALE
    budget_delta: float                       # 模拟增量（可为负）
    current_spend: float
    proposed_spend: float
    action_state: ActionState                 # Rule0~3 闸门结果
    confidence: float                         # = snapshot.confidence
    priority: float                           # round(score*100, 2)
    rationale: str                            # WHY：组合 score + delta + 闸门证据
    triggered_rules: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    strategy_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "rank": self.rank,
            "recommended_action": self.recommended_action.value,
            "budget_delta": _r(self.budget_delta),
            "current_spend": _r(self.current_spend),
            "proposed_spend": _r(self.proposed_spend),
            "action_state": self.action_state.value,
            "confidence": _r(self.confidence),
            "priority": _r(self.priority),
            "rationale": self.rationale,
            "triggered_rules": list(self.triggered_rules),
            "evidence": list(self.evidence),
            "strategy_score": _r(self.strategy_score),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProposalItem":
        return cls(
            game_id=d["game_id"],
            rank=int(d.get("rank", 0)),
            recommended_action=PortfolioVerdict(d.get("recommended_action", "maintain")),
            budget_delta=float(d.get("budget_delta", 0.0)),
            current_spend=float(d.get("current_spend", 0.0)),
            proposed_spend=float(d.get("proposed_spend", 0.0)),
            action_state=ActionState(d.get("action_state", "auto")),
            confidence=float(d.get("confidence", 0.0)),
            priority=float(d.get("priority", 0.0)),
            rationale=d.get("rationale", ""),
            triggered_rules=list(d.get("triggered_rules", [])),
            evidence=list(d.get("evidence", [])),
            strategy_score=float(d.get("strategy_score", 0.0)),
        )


@dataclass
class PortfolioProposal:
    """P3.4.4 顶层出参：一份组合层决策建议（只建议不执行）。

    ``confidence`` 语义：提案置信 = 模拟置信（输入完整度）× 可行动比例
    （未 BLOCKED 游戏数 / 总游戏数）。越多的游戏被闸门拦下，提案越不可直接落地，
    置信越低。这与 E17.3 Decision confidence、P1.7 Reality confidence 均不同。

    ``real_api_called`` 恒 ``False``：纯分析层，绝不触发 Provider。
    """

    proposal_id: str = ""
    as_of: str = ""
    items: List[ProposalItem] = field(default_factory=list)
    summary: str = ""                         # 一句话结论
    recommendation: str = ""                  # 完整人可读建议文本
    confidence: float = 0.0
    guard_verdict: ProposalGuardVerdict = ProposalGuardVerdict.BLOCKED
    auto_count: int = 0
    approval_count: int = 0
    blocked_count: int = 0
    evidence_chain: List[str] = field(default_factory=list)
    total_budget: float = 0.0
    gross_shift: float = 0.0
    notes: List[str] = field(default_factory=list)
    real_api_called: bool = REAL_API_CALLED  # 恒 False

    @property
    def is_blocked(self) -> bool:
        return self.guard_verdict is ProposalGuardVerdict.BLOCKED

    def item_of(self, game_id: str) -> Optional[ProposalItem]:
        for it in self.items:
            if it.game_id == game_id:
                return it
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "as_of": self.as_of,
            "items": [i.to_dict() for i in self.items],
            "summary": self.summary,
            "recommendation": self.recommendation,
            "confidence": _r(self.confidence),
            "guard_verdict": self.guard_verdict.value,
            "auto_count": self.auto_count,
            "approval_count": self.approval_count,
            "blocked_count": self.blocked_count,
            "evidence_chain": list(self.evidence_chain),
            "total_budget": _r(self.total_budget),
            "gross_shift": _r(self.gross_shift),
            "notes": list(self.notes),
            "real_api_called": self.real_api_called,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioProposal":
        return cls(
            proposal_id=d.get("proposal_id", ""),
            as_of=d.get("as_of", ""),
            items=[ProposalItem.from_dict(i) for i in d.get("items", [])],
            summary=d.get("summary", ""),
            recommendation=d.get("recommendation", ""),
            confidence=float(d.get("confidence", 0.0)),
            guard_verdict=ProposalGuardVerdict(d.get("guard_verdict", "blocked")),
            auto_count=int(d.get("auto_count", 0)),
            approval_count=int(d.get("approval_count", 0)),
            blocked_count=int(d.get("blocked_count", 0)),
            evidence_chain=list(d.get("evidence_chain", [])),
            total_budget=float(d.get("total_budget", 0.0)),
            gross_shift=float(d.get("gross_shift", 0.0)),
            notes=list(d.get("notes", [])),
            real_api_called=bool(d.get("real_api_called", REAL_API_CALLED)),
        )


def _merge_snapshots(
    snapshot: Union[PortfolioSnapshot, List[PortfolioSnapshot]]
) -> PortfolioSnapshot:
    """兼容「PortfolioSnapshot 列表」写法，合并为单一快照。"""
    if isinstance(snapshot, list):
        merged: List[GamePortfolioSnapshot] = []
        as_of = ""
        for s in snapshot:
            merged.extend(s.games)
            if s.generated_at:
                as_of = s.generated_at
        return PortfolioSnapshot(generated_at=as_of, games=merged)
    return snapshot


def _slug(s: str) -> str:
    """把 as_of 等字符串压成稳定 id 片段。"""
    if not s:
        return "unknown"
    return "".join(ch if (ch.isalnum() or ch in "-_") else "-" for ch in s)


class ProposalGenerator:
    """把 ``AllocationSimulationResult`` 转换为 ``PortfolioProposal``。

    只消费模拟结果与既有快照/排名，不产生任何执行动作。
    """

    def propose(
        self,
        simulation: AllocationSimulationResult,
        ranking: List[AllocationCandidate],
        snapshot: Union[PortfolioSnapshot, List[PortfolioSnapshot]],
        constraints: AllocationConstraints,
        data_age_days: Optional[Dict[str, int]] = None,
    ) -> PortfolioProposal:
        """生成决策建议。

        参数
        ----
        simulation:    P3.4.3 模拟结果（提供 baseline / proposed / delta / 约束判定）。
        ranking:       P3.4.2 候选列表（提供 recommended_action / score / confidence / reason）。
        snapshot:      组合快照（提供每游戏 has_reality / confidence 供闸门判定）。
        constraints:   硬约束（用于 evidence 引用，不直接重新校验）。
        data_age_days: 可选注入的观察天数映射 ``{game_id: int}``（P3.4 registry；
                        ``None`` 表示未提供 → 跳过 Rule3）。

        返回
        ----
        ``PortfolioProposal``（recommendation-only，``real_api_called`` 恒 ``False``）。
        """
        snap = _merge_snapshots(snapshot)
        games_by_id = {g.game_id: g for g in snap.games}
        ranking_by_id = {c.game_id: c for c in ranking}
        delta_by_id = {d.game_id: d for d in simulation.delta}
        baseline_by_id = {a.game_id: a for a in simulation.baseline_allocation}
        proposed_by_id = {a.game_id: a for a in simulation.proposed_allocation}

        guard = PortfolioGuard()
        items: List[ProposalItem] = []

        for gid in baseline_by_id:
            cand = ranking_by_id.get(gid)
            g = games_by_id.get(gid)
            d = delta_by_id.get(gid)
            base = baseline_by_id[gid].amount
            prop = proposed_by_id[gid].amount if gid in proposed_by_id else base
            delta = d.delta if d is not None else 0.0
            current_spend = base

            # —— 闸门判定（Rule0~3）——
            if g is not None:
                age = data_age_days.get(gid) if data_age_days else None
                outcome = guard.evaluate(g, delta, current_spend, age)
            else:
                # 模拟有该游戏但快照缺失 → 视为缺现实数据，硬阻断
                outcome = GuardOutcome(
                    ActionState.BLOCKED,
                    [RULE0],
                    ["no snapshot present for simulated game"],
                )

            # —— recommended_action（Rule3 降级为 NO_SCALE）——
            rec_action = (
                cand.recommended_action if cand is not None else PortfolioVerdict.MAINTAIN
            )
            if RULE3 in outcome.triggered_rules:
                rec_action = PortfolioVerdict.NO_SCALE

            score = cand.portfolio_score if cand is not None else 0.0
            conf = cand.confidence if cand is not None else 0.0
            priority = cand.priority if cand is not None else round(score * 100, 2)
            strat = cand.strategy_score if cand is not None else 0.0

            rationale = self._build_rationale(
                gid, cand, d, outcome, rec_action, simulation
            )

            items.append(
                ProposalItem(
                    game_id=gid,
                    rank=cand.rank if cand is not None else 0,
                    recommended_action=rec_action,
                    budget_delta=delta,
                    current_spend=current_spend,
                    proposed_spend=prop,
                    action_state=outcome.action_state,
                    confidence=conf,
                    priority=priority,
                    rationale=rationale,
                    triggered_rules=list(outcome.triggered_rules),
                    evidence=list(outcome.evidence),
                    strategy_score=strat,
                )
            )

        auto = sum(1 for i in items if i.action_state == ActionState.AUTO)
        approval = sum(1 for i in items if i.action_state == ActionState.APPROVAL)
        blocked = sum(1 for i in items if i.action_state == ActionState.BLOCKED)
        total = len(items)
        # 提案置信 = 模拟置信（输入完整度）× 可自动落地比例
        # （AUTO 计全权，APPROVAL 折半；模拟整体被约束阻断再折损）。
        auto_score = ((auto + _APPROVAL_CONF_WEIGHT * approval) / total) if total else 0.0
        conf = simulation.confidence * auto_score
        if simulation.is_blocked:
            conf = conf * _SIM_BLOCK_CONF_PENALTY
        confidence = round(conf, 6)

        guard_verdict = self._aggregate_verdict(simulation, auto, approval, blocked)
        summary = self._build_summary(
            simulation, total, auto, approval, blocked
        )
        evidence_chain = self._build_evidence_chain(
            simulation, auto, approval, blocked
        )
        recommendation = self._build_recommendation(
            summary, items, evidence_chain
        )

        return PortfolioProposal(
            proposal_id=f"prop-{_slug(simulation.as_of)}",
            as_of=simulation.as_of,
            items=items,
            summary=summary,
            recommendation=recommendation,
            confidence=confidence,
            guard_verdict=guard_verdict,
            auto_count=auto,
            approval_count=approval,
            blocked_count=blocked,
            evidence_chain=evidence_chain,
            total_budget=simulation.total_budget,
            gross_shift=simulation.gross_shift,
            notes=list(simulation.notes),
            real_api_called=REAL_API_CALLED,
        )

    # ------------------------------------------------------------------ #
    # 文本 / 证据链构造
    # ------------------------------------------------------------------ #
    def _build_rationale(
        self,
        game_id: str,
        cand: Optional[AllocationCandidate],
        delta_obj,
        outcome: GuardOutcome,
        rec_action: PortfolioVerdict,
        simulation: AllocationSimulationResult,
    ) -> str:
        parts: List[str] = []
        score = cand.portfolio_score if cand is not None else 0.0
        parts.append(
            f"recommend {rec_action.value.upper()} "
            f"(rank={cand.rank if cand else '?'}, portfolio_score={score:.3f})"
        )
        delta = delta_obj.delta if delta_obj is not None else 0.0
        current = delta_obj.before if delta_obj is not None else 0.0
        proposed = delta_obj.after if delta_obj is not None else 0.0
        parts.append(
            f"simulated Δ={delta:+.2f} (current={current:.2f} → proposed={proposed:.2f})"
        )
        if cand is not None and cand.reason:
            parts.append(f"ranker: {cand.reason}")
        if outcome.action_state == ActionState.BLOCKED:
            rules = ", ".join(outcome.triggered_rules)
            parts.append(f"BLOCKED by {rules}: {'; '.join(outcome.evidence)}")
        elif outcome.action_state == ActionState.APPROVAL:
            parts.append(f"APPROVAL required: {'; '.join(outcome.evidence)}")
        else:
            parts.append("AUTO: guard passed, proposal actionable")
        if RULE3 in outcome.triggered_rules:
            parts.append("action downgraded to NO_SCALE (insufficient observation window)")
        return "; ".join(parts)

    def _aggregate_verdict(
        self,
        simulation: AllocationSimulationResult,
        auto: int,
        approval: int,
        blocked: int,
    ) -> ProposalGuardVerdict:
        if simulation.is_blocked or blocked > 0:
            return ProposalGuardVerdict.BLOCKED
        if approval > 0:
            return ProposalGuardVerdict.PARTIAL
        return ProposalGuardVerdict.PROPOSABLE

    def _build_summary(
        self,
        simulation: AllocationSimulationResult,
        total: int,
        auto: int,
        approval: int,
        blocked: int,
    ) -> str:
        if total == 0:
            return (
                "Portfolio proposal: simulation produced no allocatable games "
                "(empty or fully blocked)."
            )
        if blocked == total:
            return (
                f"Portfolio proposal BLOCKED: all {total} game(s) failed "
                f"guard/simulation checks — no change recommended."
            )
        return (
            f"Portfolio proposal: reallocate {simulation.gross_shift:.2f} of "
            f"{simulation.total_budget:.2f} across {total} game(s); "
            f"{auto} AUTO / {approval} APPROVAL / {blocked} BLOCKED."
        )

    def _build_evidence_chain(
        self,
        simulation: AllocationSimulationResult,
        auto: int,
        approval: int,
        blocked: int,
    ) -> List[str]:
        chain: List[str] = []
        chain.append(
            f"Simulation verdict: {simulation.verdict.value.upper()} "
            f"(simulation confidence={simulation.confidence:.3f})."
        )
        if simulation.blocked_rules:
            chain.append(
                f"Simulation blocked by constraint(s): {', '.join(simulation.blocked_rules)}."
            )
        chain.append(
            f"Guard (Rule0~3): {auto} AUTO / {approval} APPROVAL / {blocked} BLOCKED."
        )
        chain.append(
            "Budget conservation: Σproposed == Σbaseline — no budget created or destroyed."
        )
        chain.append(
            "Discipline: proposal only — no budget changed, no execution request emitted; "
            "awaiting E17.3 Decision Review / human approval."
        )
        return chain

    def _build_recommendation(
        self,
        summary: str,
        items: List[ProposalItem],
        evidence_chain: List[str],
    ) -> str:
        lines: List[str] = [summary, ""]
        for it in items:
            line = (
                f"  {it.rank}. {it.game_id}: {it.recommended_action.value.upper()} "
                f"(Δ={it.budget_delta:+.2f}) → {it.action_state.value.upper()}; "
                f"{it.rationale}"
            )
            lines.append(line)
        lines.append("")
        lines.append("Evidence chain:")
        for ev in evidence_chain:
            lines.append(f"  - {ev}")
        return "\n".join(lines)


def build_proposal_generator() -> ProposalGenerator:
    """构建决策建议生成器（纯函数，无外部依赖）。"""
    return ProposalGenerator()
