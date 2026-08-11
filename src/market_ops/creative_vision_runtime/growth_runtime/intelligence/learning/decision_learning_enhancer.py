"""E13.7.5 Decision Learning Enhancer — 决策学习增强器.

Day 7.5.3:
  在 Decision 创建前查询历史类似决策，分析成功/失败原因，
  从"记录决策结果"升级为"用历史决策反馈优化未来决策"。

核心流程:
  Decision Context (action_type, strategy, opportunity, ...)
              |
              v
  DecisionLearningEnhancer.enhance(context, decision_memory)
              |
              +--> _find_similar()      → 查找历史类似决策
              |
              +--> _analyze_outcomes()  → 分析成功/失败模式
              |
              +--> _detect_risks()      → 检测风险信号
              |
              +--> _generate_recommendation() → 生成推荐
              |
              v
  DecisionLearningResult (recommendation + condition + confidence)

设计原则:
  - 纯查询决策记忆，不修改任何数据
  - 基于历史决策结果的统计分析
  - 确定性可解释的推荐逻辑
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

from .models.learning_models import (
    DecisionLearningResult,
    RiskSignal,
)


class DecisionLearningEnhancer:
    """决策学习增强器 — 基于历史决策反馈优化当前决策.

    用法:
        enhancer = DecisionLearningEnhancer()
        result = enhancer.enhance(
            context={"action_type": "increase_budget", "strategy": "scale_winning"},
            decision_memory=decision_memory,
        )
    """

    def __init__(
        self,
        min_similar_decisions: int = 3,
        min_confidence: float = 0.50,
    ) -> None:
        """初始化增强器.

        Args:
            min_similar_decisions: 最小相似决策数 (不足时不做推荐)
            min_confidence: 最小推荐置信度
        """
        self._min_similar_decisions = min_similar_decisions
        self._min_confidence = min_confidence
        self._enhancement_count: int = 0

    @property
    def enhancement_count(self) -> int:
        return self._enhancement_count

    # ── Public API ───────────────────────────────────────────────

    def enhance(
        self,
        context: dict[str, Any] | None = None,
        decision_memory: Any = None,
        action_type: str = "",
        strategy_name: str = "",
        opportunity_type: str = "",
        risk_signals: list[RiskSignal] | None = None,
    ) -> DecisionLearningResult:
        """基于历史决策反馈增强当前决策.

        Args:
            context: 决策上下文
            decision_memory: DecisionMemory 实例
            action_type: 动作类型
            strategy_name: 策略名称
            opportunity_type: 机会类型
            risk_signals: 已知风险信号列表

        Returns:
            DecisionLearningResult: 决策学习结果
        """
        self._enhancement_count += 1
        ctx = context or {}

        action_type = action_type or ctx.get("action_type", "")
        strategy_name = strategy_name or ctx.get("strategy_name", "")
        opportunity_type = opportunity_type or ctx.get("opportunity_type", "")

        if decision_memory is None:
            return DecisionLearningResult(
                confidence=0.0,
                metadata={"reason": "no_decision_memory"},
            )

        # 1. 查找历史类似决策
        similar = self._find_similar(
            decision_memory, action_type, strategy_name, opportunity_type
        )

        if len(similar) < self._min_similar_decisions:
            return DecisionLearningResult(
                similar_decisions=len(similar),
                confidence=0.0,
                metadata={"reason": "insufficient_similar_decisions"},
            )

        # 2. 分析成功/失败
        outcomes = self._analyze_outcomes(similar)

        # 3. 检测风险信号
        detected_risks = self._detect_decision_risks(similar, outcomes)

        # 4. 生成推荐
        recommendation, condition_text, adjustments = self._generate_recommendation(
            outcomes, detected_risks, risk_signals or []
        )

        # 5. 计算置信度
        confidence = self._compute_confidence(outcomes, similar)

        return DecisionLearningResult(
            recommendation=recommendation,
            condition=condition_text,
            confidence=round(confidence, 4),
            similar_decisions=len(similar),
            success_count=outcomes["success_count"],
            failure_count=outcomes["failure_count"],
            success_rate=round(outcomes["success_rate"], 4),
            failure_reasons=outcomes["failure_reasons"],
            risk_signals=detected_risks,
            adjustments=adjustments,
            metadata={
                "action_type": action_type,
                "strategy_name": strategy_name,
                "opportunity_type": opportunity_type,
            },
        )

    # ── Similar Decision Search ─────────────────────────────────

    def _find_similar(
        self,
        decision_memory: Any,
        action_type: str = "",
        strategy_name: str = "",
        opportunity_type: str = "",
    ) -> list[dict[str, Any]]:
        """查找历史类似决策.

        从 DecisionMemory 中查询相似决策，返回标准化格式。
        """
        similar: list[dict[str, Any]] = []

        try:
            # 通过 find_similar 查询
            if hasattr(decision_memory, "find_similar"):
                results = decision_memory.find_similar(
                    opportunity_type=opportunity_type,
                    limit=50,
                )
                for exp in results:
                    if not exp.is_resolved:
                        continue

                    # 动作类型匹配 (宽松)
                    if action_type:
                        exp_plan = exp.action_plan if isinstance(exp.action_plan, dict) else {}
                        exp_action = exp_plan.get("action_type", "")
                        if exp_action and action_type.lower() not in exp_action.lower():
                            continue

                    # 策略名匹配 (宽松)
                    if strategy_name and strategy_name.lower() not in exp.strategy_name.lower():
                        continue

                    similar.append({
                        "decision_id": exp.decision_id,
                        "strategy_name": exp.strategy_name,
                        "action_type": exp.action_plan.get("action_type", "") if isinstance(exp.action_plan, dict) else "",
                        "result": exp.result,
                        "confidence": exp.confidence,
                        "risk_score": exp.risk_score,
                        "final_score": exp.final_score,
                        "lessons_learned": exp.lessons_learned if hasattr(exp, "lessons_learned") else [],
                        "result_reason": exp.result_reason if hasattr(exp, "result_reason") else "",
                        "result_metrics": exp.result_metrics if hasattr(exp, "result_metrics") else {},
                        "created_at": exp.created_at if hasattr(exp, "created_at") else "",
                    })

            # 备选: 通过 get_recent 遍历
            elif hasattr(decision_memory, "get_recent"):
                results = decision_memory.get_recent(limit=100)
                for exp in results:
                    if not exp.is_resolved:
                        continue
                    if action_type and action_type.lower() not in str(exp.action_plan).lower():
                        continue
                    if strategy_name and strategy_name.lower() not in exp.strategy_name.lower():
                        continue
                    similar.append({
                        "decision_id": exp.decision_id,
                        "strategy_name": exp.strategy_name,
                        "action_type": exp.action_plan.get("action_type", "") if isinstance(exp.action_plan, dict) else "",
                        "result": exp.result,
                        "confidence": exp.confidence,
                        "risk_score": exp.risk_score,
                        "final_score": exp.final_score,
                        "lessons_learned": exp.lessons_learned if hasattr(exp, "lessons_learned") else [],
                        "result_reason": exp.result_reason if hasattr(exp, "result_reason") else "",
                        "result_metrics": exp.result_metrics if hasattr(exp, "result_metrics") else {},
                        "created_at": exp.created_at if hasattr(exp, "created_at") else "",
                    })
        except Exception:
            pass

        return similar

    # ── Outcome Analysis ────────────────────────────────────────

    def _analyze_outcomes(
        self, similar: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """分析历史决策结果."""
        success_count = sum(1 for d in similar if d["result"] == "success")
        failure_count = sum(1 for d in similar if d["result"] == "failure")
        partial_count = sum(1 for d in similar if d["result"] == "partial")
        total = len(similar)
        success_rate = success_count / total if total > 0 else 0.0

        # 失败原因分析
        failure_reasons: list[str] = []
        for d in similar:
            if d["result"] == "failure":
                reason = d.get("result_reason", "")
                if reason:
                    failure_reasons.append(reason)
                for lesson in d.get("lessons_learned", []):
                    if lesson:
                        failure_reasons.append(lesson)

        # 去重并取最常见原因
        reason_counter = Counter(failure_reasons)
        top_reasons = [r for r, _ in reason_counter.most_common(5) if r]

        return {
            "success_count": success_count,
            "failure_count": failure_count,
            "partial_count": partial_count,
            "total": total,
            "success_rate": success_rate,
            "failure_reasons": top_reasons,
        }

    # ── Risk Detection ──────────────────────────────────────────

    def _detect_decision_risks(
        self,
        similar: list[dict[str, Any]],
        outcomes: dict[str, Any],
    ) -> list[str]:
        """检测决策风险信号."""
        risks: list[str] = []

        # 1. 高失败率
        if outcomes["failure_count"] > outcomes["success_count"]:
            risks.append(f"High historical failure rate: {outcomes['failure_count']}/{outcomes['total']}")

        # 2. 近期趋势下降
        if len(similar) >= 8:
            sorted_sims = sorted(similar, key=lambda d: d.get("created_at", ""), reverse=True)
            recent = sorted_sims[:4]
            older = sorted_sims[-4:]
            recent_success = sum(1 for d in recent if d["result"] == "success") / max(len(recent), 1)
            older_success = sum(1 for d in older if d["result"] == "success") / max(len(older), 1)
            if recent_success < older_success - 0.2:
                risks.append(
                    f"Declining success trend: {older_success:.0%} → {recent_success:.0%}"
                )

        # 3. 高平均风险评分
        avg_risk = sum(d.get("risk_score", 0) for d in similar) / max(len(similar), 1)
        if avg_risk > 0.6:
            risks.append(f"Average historical risk score: {avg_risk:.2f}")

        # 4. 低平均置信度
        avg_confidence = sum(d.get("confidence", 0) for d in similar) / max(len(similar), 1)
        if avg_confidence < 0.5:
            risks.append(f"Low average confidence: {avg_confidence:.2f}")

        return risks

    # ── Recommendation Generation ───────────────────────────────

    def _generate_recommendation(
        self,
        outcomes: dict[str, Any],
        detected_risks: list[str],
        external_risks: list[RiskSignal],
    ) -> tuple[str, str, list[str]]:
        """生成推荐.

        Returns:
            (recommendation, condition, adjustments)
        """
        success_rate = outcomes["success_rate"]
        adjustments: list[str] = []

        # 高风险信号 → deny
        high_risk_signals = [r for r in external_risks if r.risk_level in ("high", "critical")]
        if high_risk_signals:
            return (
                "deny",
                f"High risk signals detected: {high_risk_signals[0].signal_type}",
                high_risk_signals[0].recommendations if high_risk_signals else [],
            )

        # 高成功率 → approve
        if success_rate >= 0.7 and outcomes["success_count"] >= 5:
            return "approve", "", adjustments

        # 中等成功率但有风险 → approve_with_condition
        if success_rate >= 0.5 and outcomes["success_count"] >= 3:
            if detected_risks:
                condition = detected_risks[0]
                if "creative" in " ".join(detected_risks).lower() or "creative" in str(outcomes.get("failure_reasons", [])).lower():
                    condition = "Refresh creative assets before execution"
                    adjustments.append("Prepare new creative variants")
                elif "trend" in " ".join(detected_risks).lower():
                    condition = "Start with reduced budget (50%) and monitor for 3 days"
                    adjustments.append("Set budget cap at 50% of target")
                else:
                    condition = f"Condition: {detected_risks[0]}"
                return "approve_with_condition", condition, adjustments
            return "approve", "", adjustments

        # 低成功率 → adjust
        if success_rate < 0.5 and outcomes["total"] >= 5:
            adjustments = [
                "Re-evaluate strategy parameters",
                "Consider alternative action types",
                "Reduce execution scope",
            ]
            return "adjust", "Historical success rate below threshold", adjustments

        # 默认 → approve (数据不足)
        return "approve", "", adjustments

    # ── Confidence ──────────────────────────────────────────────

    def _compute_confidence(
        self,
        outcomes: dict[str, Any],
        similar: list[dict[str, Any]],
    ) -> float:
        """计算推荐置信度."""
        total = outcomes["total"]
        success_rate = outcomes["success_rate"]

        # 样本量因子
        sample_factor = 1.0 - math.exp(-total / 10.0)

        # 结果确定性
        result_certainty = abs(success_rate - 0.5) * 2.0  # 越远离0.5越确定

        # 结果一致性
        results = [d["result"] for d in similar]
        most_common_count = Counter(results).most_common(1)[0][1] if results else 0
        consistency = most_common_count / total if total > 0 else 0.0

        confidence = (
            sample_factor * 0.40
            + result_certainty * 0.35
            + consistency * 0.25
        )

        return round(min(0.95, max(0.0, confidence)), 4)


__all__ = [
    "DecisionLearningEnhancer",
]