"""E12.7.6 Feedback Processor — 执行结果 → 反馈 → 决策更新."""

from __future__ import annotations

from typing import Any


class FeedbackProcessor:
    """反馈处理器 — 将执行结果转化为可操作的反馈和决策更新.

    流程:
      ExecutionResult → Feedback → Decision Update

    例如:
      策略: 增加 Rescue Hook Creative
      结果: CTR +40%, ROAS +25%
      反馈: Strategy confidence +0.15, Pattern confidence +0.10
    """

    def __init__(self):
        self._process_count: int = 0

    @property
    def process_count(self) -> int:
        return self._process_count

    # ── Process ───────────────────────────────────────────────

    def process(self, execution_result: dict[str, Any]) -> dict[str, Any]:
        """处理执行结果，生成反馈."""
        self._process_count += 1

        feedback: dict[str, Any] = {
            "execution_success": execution_result.get("executed", False),
            "roi_impact": 0.0,
            "confidence_delta": 0.0,
            "strategy_adjustments": [],
            "warnings": [],
            "recommendations": [],
        }

        # Extract metrics
        plan = execution_result.get("result", {}).get("plan", {})
        tasks = plan.get("tasks", [])

        if not execution_result.get("executed", False):
            feedback["warnings"].append("Execution failed")
            feedback["confidence_delta"] = -0.1
            return feedback

        # Analyze task results
        feedback = self._analyze_tasks(feedback, tasks)

        # Determine ROI impact
        feedback = self._compute_roi_impact(feedback, tasks)

        # Generate recommendations
        feedback = self._generate_recommendations(feedback, execution_result)

        return feedback

    def process_cycle(
        self, execution_result: dict[str, Any], strategy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """处理单次循环的反馈."""
        feedback = self.process(execution_result)

        if strategy:
            feedback["strategy_id"] = strategy.get("strategy_id", "")
            feedback["strategy_confidence"] = strategy.get("confidence", 0.5)

        return feedback

    # ── Analysis ──────────────────────────────────────────────

    def _analyze_tasks(
        self, feedback: dict[str, Any], tasks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """分析任务结果."""
        feedback.setdefault("warnings", [])
        success_count = 0
        failure_count = 0

        for task in tasks:
            status = task.get("status", "")
            if status in ("success", "rolled_back"):
                success_count += 1
            elif status == "failed":
                failure_count += 1

        total = success_count + failure_count
        if total > 0:
            feedback["success_rate"] = success_count / total
            if success_count / total > 0.8:
                feedback["confidence_delta"] = 0.1
            elif success_count / total < 0.5:
                feedback["confidence_delta"] = -0.1
                feedback["warnings"].append("Low success rate")
        else:
            feedback["success_rate"] = 0.0

        feedback["success_tasks"] = success_count
        feedback["failed_tasks"] = failure_count

        return feedback

    def _compute_roi_impact(
        self, feedback: dict[str, Any], tasks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """计算ROI影响."""
        total_roi_impact = 0.0
        for task in tasks:
            metrics = task.get("metrics", {})
            roas = metrics.get("roas", 0.0)
            if roas > 0:
                # +ROI if ROAS > 1.0, -ROI if ROAS < 1.0
                total_roi_impact += (roas - 1.0) * 0.1

        feedback["roi_impact"] = round(total_roi_impact, 4)
        return feedback

    def _generate_recommendations(
        self, feedback: dict[str, Any], execution_result: dict[str, Any],
    ) -> dict[str, Any]:
        """生成建议."""
        feedback.setdefault("recommendations", [])
        feedback.setdefault("strategy_adjustments", [])
        if feedback.get("success_rate", 0) >= 1.0:
            feedback["recommendations"].append("scale_strategy")
            feedback["strategy_adjustments"].append({"action": "scale", "factor": 1.2})
        elif feedback.get("success_rate", 0) >= 0.8:
            feedback["recommendations"].append("continue_strategy")
            feedback["strategy_adjustments"].append({"action": "continue", "factor": 1.0})
        elif feedback.get("success_rate", 0) >= 0.5:
            feedback["recommendations"].append("adjust_strategy")
            feedback["strategy_adjustments"].append({"action": "adjust", "factor": 0.8})
        else:
            feedback["recommendations"].append("rethink_strategy")
            feedback["strategy_adjustments"].append({"action": "rollback", "factor": 0.0})

        return feedback

    # ── Confidence Updates ────────────────────────────────────

    def compute_confidence_delta(
        self,
        execution_result: dict[str, Any],
        previous_confidence: float = 0.5,
    ) -> float:
        """计算置信度变化."""
        feedback = self.process(execution_result)
        base_delta = feedback.get("confidence_delta", 0.0)

        # ROI impact bonus
        roi_impact = feedback.get("roi_impact", 0.0)
        if roi_impact > 0:
            base_delta += min(0.1, roi_impact)

        # Clamp
        return max(-0.3, min(0.3, base_delta))

    def update_strategy_confidence(
        self, strategy: dict[str, Any], execution_result: dict[str, Any],
    ) -> dict[str, Any]:
        """更新策略置信度."""
        current_confidence = strategy.get("confidence", 0.5)
        delta = self.compute_confidence_delta(execution_result, current_confidence)
        new_confidence = max(0.0, min(1.0, current_confidence + delta))

        strategy["confidence"] = new_confidence
        strategy["confidence_delta"] = delta
        return strategy

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            "process_count": self._process_count,
        }