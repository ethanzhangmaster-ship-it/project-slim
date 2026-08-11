"""P3.3 — Strategy Loop（策略反馈控制器，编排层）。

Observe → Evaluate → Learn → Adjust → Emit

纪律红线（与全库一致）：
- 只读 E17.7 / P2.5 / P2.6 / DailyRunResult；不重算业务指标；
- **不**调用 Provider、**不**触发任何执行、**不**修改 E17.3 Decision；
- 突变引擎产出的 StrategyProposal 一律 `requires_simulation=True`，
  经 StrategyGuard 校验后只进入 *Simulation Queue*（本阶段不执行）。

P3.3.1 范围：读过去执行结果 → 生成 StrategyInsight + 经验更新。
P3.3.2 脚手架：突变引擎产出 Proposal（进 Simulation Queue，不执行）。
P3.3.3（后续）才会把 Proposal 真正灌入 Simulation→Approval→Execution。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.ceo_intelligence.daily_operator.models import ActionKind

from .evaluator import OutcomeEvaluator
from .guard import StrategyGuard
from .memory import StrategyMemoryAdapter
from .models import (
    StrategyFeedback,
    StrategyInsight,
    StrategyLoopResult,
    StrategyProposal,
)
from .mutation import StrategyMutationEngine

# P3.3.3（延迟导入避免循环依赖；此处仅作可选装配）
from src.operator.adaptive_strategy import (
    AdaptiveStrategyController,
    AdaptiveStrategyRequest,
)


class _AutoOk:
    """供 evaluator 判定 AUTO 动作为「已执行成功」的轻量桩。"""

    ok = True
    verdict = "executed"


_AUTO_OK = _AutoOk()


class StrategyLoop:
    """把一日执行结果折进策略经验，并产出调整建议（不执行）。"""

    def __init__(
        self,
        memory_adapter: StrategyMemoryAdapter,
        mutation_engine: Optional[StrategyMutationEngine] = None,
        guard: Optional[StrategyGuard] = None,
        evaluator: Optional[OutcomeEvaluator] = None,
        graph: Any = None,
        adaptive_controller: Optional[AdaptiveStrategyController] = None,
        advisor: Optional[Any] = None,
    ) -> None:
        self.memory = memory_adapter
        self.mutator = mutation_engine or StrategyMutationEngine()
        self.guard = guard or StrategyGuard()
        self.evaluator = evaluator or OutcomeEvaluator()
        self.graph = graph
        # P3.3.3：可选装配——为过闸的安全动作提案闭环真实执行
        self.adaptive_controller = adaptive_controller
        # P3.5.1（可选）：经验增强顾问；None → 不接经验（零回归）
        self.advisor = advisor
        # 注意：P3.5.2 决策学习写入**不**在本层发生——StrategyLoop 是策略产生层，
        # 反馈由 Operator Layer（pipeline / src/operator/feedback.py）消费 Result 后写入。

    # ------------------------------------------------------------------
    # P3.3.3：把过闸的 StrategyProposal 关键词适配成 AdaptiveStrategyRequest。
    # 仅匹配安全动作模板；其余提案保持 P3.3 非变异路径（只建议不执行）。
    # ------------------------------------------------------------------
    _ADAPT_KEYWORDS: Dict[str, tuple] = {
        "adaptive.network_cleanup": (
            "network_cleanup", "disable", "僵尸", "关停", "ecpm", "network",
        ),
        "adaptive.campaign_pause": (
            "campaign_pause", "campaign", "pause", "stop_loss", "止损", "暂停", "roas",
        ),
    }

    def _adapt_proposal(
        self,
        proposal: StrategyProposal,
        *,
        target: str,
        mode: str,
        approver: str,
        approver_role: str,
    ) -> Optional[AdaptiveStrategyRequest]:
        text = " ".join([
            proposal.current_strategy,
            proposal.proposed_change,
            proposal.expected_impact,
        ]).lower()
        for strategy_id, kws in self._ADAPT_KEYWORDS.items():
            if any(k in text for k in kws):
                return AdaptiveStrategyRequest(
                    proposal_id=f"adp_{strategy_id.split('.')[-1]}_{target}",
                    strategy_id=strategy_id,
                    target=target,
                    expected_change=proposal.proposed_change,
                    parameters={},
                    mode=mode,
                    approver=approver,
                    approver_role=approver_role,
                )
        return None

    # ------------------------------------------------------------------ #
    def run(
        self,
        daily: Any,
        exec_report: Any = None,
        recoveries: Optional[List[Any]] = None,
        date: str = "",
        *,
        adaptive_target: Optional[str] = None,
        adaptive_mode: str = "dry_run",
        adaptive_approver: str = "",
        adaptive_approver_role: str = "",
    ) -> StrategyLoopResult:
        # 1) Observe —— 读当日三态行动（不重算）
        actions = list(getattr(daily, "actions", []) or [])

        # 2) Evaluate —— 每个行动 → StrategyFeedback
        feedbacks: List[StrategyFeedback] = []
        for action in actions:
            exec_result = _AUTO_OK if getattr(action, "kind", None) == ActionKind.AUTO else None
            strat_id = getattr(action, "opportunity_type", "") or None
            fb = self.evaluator.evaluate(
                action, execution_result=exec_result, strategy_id=strat_id
            )
            feedbacks.append(fb)

        # 3) Learn —— 折进策略经验（成功增信 / 失败降权 / 连续失败停用）
        for fb in feedbacks:
            self.memory.apply_feedback(fb)
        self.memory.save()

        # 4) Adjust —— 读 E17.7 + 本地状态 → 洞察；突变引擎 → 建议
        insights = self.memory.build_insights(self.graph)
        raw_proposals = self.mutator.propose(self.memory.all_states(), insights)

        # 5) Guard —— 只放行过闸（gated）的建议进入 Simulation Queue
        proposals: List[StrategyProposal] = []
        for p in raw_proposals:
            verdict = self.guard.validate(p)
            if verdict.allowed:
                proposals.append(p)

        # 5.2) P3.5.1 —— 经验增强：用 Knowledge Graph 修正提案（只读，不改变 Decision/Execution/Approval）
        if self.advisor is not None:
            from src.ceo_intelligence.growth_memory_graph.advisor import (
                knowledge_adjusted_confidence,
                knowledge_requires_approval,
            )
            for p in proposals:
                sig = self.advisor.advise_strategy(p)
                if sig.similar_case_count <= 0 and not sig.risk_flags:
                    continue
                p.knowledge_signal = sig.to_dict()
                if sig.risk_flags:
                    # 历史失败模式 → 有效置信降权 + 强制走审批/Simulation
                    p.knowledge_confidence = knowledge_adjusted_confidence(
                        p.confidence, sig
                    )
                    p.requires_simulation = True

        # 5.5) P3.3.3 —— 过闸的安全动作提案 → 真实闭环
        # 保留 P3.3 非变异路径（proposals 仍原样产出）；仅对匹配安全模板的
        # 提案再走一次 AdaptiveStrategyController（Simulation → Approval → Execution）。
        adaptive_results: List[Any] = []
        if self.adaptive_controller is not None and adaptive_target:
            for p in proposals:
                req = self._adapt_proposal(
                    p,
                    target=adaptive_target,
                    mode=adaptive_mode,
                    approver=adaptive_approver,
                    approver_role=adaptive_approver_role,
                )
                if req is None:
                    continue
                adaptive_results.append(self.adaptive_controller.run(req))

        # 6) Emit —— 组装交付物（不执行任何动作）
        pattern_lines = [i.to_line() for i in insights]
        for p in proposals:
            line = (
                f"[提案] {p.current_strategy} → {p.proposed_change}"
                f"（置信 {p.confidence}，须经 Simulation 闸门）"
            )
            if p.knowledge_confidence is not None:
                line += f" [经验降权→{p.knowledge_confidence}]"
            pattern_lines += [line]
            if p.knowledge_signal:
                for e in p.knowledge_signal.get("evidence", []):
                    pattern_lines += [f"[知识增强] {p.current_strategy}: {e}"]

        return StrategyLoopResult(
            insights=insights,
            proposals=proposals,
            states=self.memory.all_states(),
            feedbacks=feedbacks,
            patterns=pattern_lines,
            adaptive=adaptive_results,
        )


# ---------------------------------------------------------------------- #
def write_strategy_outputs(
    date: str, out_dir: str, result: StrategyLoopResult
) -> Dict[str, str]:
    """落盘策略产物（四文件），返回路径 dict。"""
    d = Path(out_dir) / date
    d.mkdir(parents=True, exist_ok=True)

    insights_path = d / "strategy_insights.json"
    proposals_path = d / "strategy_proposals.json"
    states_path = d / "strategy_states.json"
    adaptive_path = d / "strategy_adaptive.json"

    insights_path.write_text(
        json.dumps([i.to_dict() for i in result.insights],
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    proposals_path.write_text(
        json.dumps([p.to_dict() for p in result.proposals],
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    states_path.write_text(
        json.dumps(
            {k: v.to_dict() for k, v in result.states.items()},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    adaptive_path.write_text(
        json.dumps(
            [r.to_dict() if hasattr(r, "to_dict") else r for r in result.adaptive],
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "strategy_insights": str(insights_path),
        "strategy_proposals": str(proposals_path),
        "strategy_states": str(states_path),
        "strategy_adaptive": str(adaptive_path),
    }


__all__ = ["StrategyLoop", "write_strategy_outputs"]
