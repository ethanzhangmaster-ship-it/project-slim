"""E13.6.5 Result Analyzer — 执行结果分析器.

从 EngineResult 和 AuditLog 中提取结构化反馈，分析执行质量、效率、
安全性和业务结果，生成 ExecutionFeedback。

核心设计:
  - 从 EngineResult 提取执行统计 (成功率、失败数、回滚)
  - 从 AuditLog 提取审计条目
  - 从 SafetyEvaluation 提取安全信号
  - 从 ExecutionContext 提取决策上下文
  - 输出 ExecutionFeedback 供 RewardCalculator 消费

连接:
  E13.6.3 ExecutionEngine → ResultAnalyzer → RewardCalculator → FeedbackLoop
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..audit_log import AuditLog
from ..execution_core import EngineResult
from ..execution_context import ExecutionContext
from .models import ExecutionFeedback


# ═══════════════════════════════════════════════════════════════
# Result Analyzer
# ═══════════════════════════════════════════════════════════════


class ResultAnalyzer:
    """执行结果分析器 — 将原始执行结果转化为结构化反馈.

    用法:
        analyzer = ResultAnalyzer()
        feedback = analyzer.analyze(
            engine_result=engine_result,
            audit_log=audit_log,
            context=execution_context,
            safety_evaluation=safety_eval_dict,
        )
    """

    def __init__(self):
        self._analysis_count: int = 0

    # ── 主入口 ────────────────────────────────────────────────

    def analyze(
        self,
        engine_result: EngineResult,
        audit_log: AuditLog | None = None,
        context: ExecutionContext | None = None,
        safety_evaluation: dict[str, Any] | None = None,
    ) -> ExecutionFeedback:
        """分析执行结果，生成 ExecutionFeedback.

        Args:
            engine_result: 执行引擎结果
            audit_log: 审计日志
            context: 执行上下文
            safety_evaluation: 安全评估结果 (dict)

        Returns:
            ExecutionFeedback: 结构化反馈
        """
        self._analysis_count += 1

        # 提取审计条目
        audit_entries = []
        if audit_log is not None:
            audit_entries = audit_log.to_memory_format()

        # 提取上下文
        context_dict = context.to_dict() if context else {}

        # 提取主要动作类型
        action_type = self._extract_primary_action_type(engine_result, audit_entries)

        # 计算执行耗时
        duration_ms = self._calculate_duration(engine_result)

        feedback = ExecutionFeedback(
            decision_id=context_dict.get("decision_id", ""),
            task_id=engine_result.task_id,
            plan_id=engine_result.plan_id,
            opportunity_id=context_dict.get("opportunity_id", ""),
            strategy_id=context_dict.get("strategy_id", ""),
            execution_summary=engine_result.stats(),
            audit_entries=audit_entries,
            safety_evaluation=safety_evaluation,
            context=context_dict,
            action_type=action_type,
            total_nodes=engine_result.total_nodes,
            success_nodes=engine_result.success_count,
            failure_nodes=engine_result.failure_count,
            skipped_nodes=engine_result.skipped_count,
            rollback_nodes=engine_result.rollback_count,
            execution_duration_ms=duration_ms,
        )

        return feedback

    # ── 批量分析 ──────────────────────────────────────────────

    def analyze_batch(
        self,
        engine_results: list[EngineResult],
        audit_log: AuditLog | None = None,
        context: ExecutionContext | None = None,
        safety_evaluation: dict[str, Any] | None = None,
    ) -> list[ExecutionFeedback]:
        """批量分析多个执行结果.

        Args:
            engine_results: 执行引擎结果列表
            audit_log: 审计日志
            context: 执行上下文
            safety_evaluation: 安全评估结果

        Returns:
            list[ExecutionFeedback]: 反馈列表
        """
        return [
            self.analyze(
                engine_result=result,
                audit_log=audit_log,
                context=context,
                safety_evaluation=safety_evaluation,
            )
            for result in engine_results
        ]

    # ── 统计分析 ──────────────────────────────────────────────

    def analyze_trends(
        self,
        feedbacks: list[ExecutionFeedback],
    ) -> dict[str, Any]:
        """分析反馈趋势.

        Args:
            feedbacks: 反馈列表 (按时间排序)

        Returns:
            dict: 趋势分析
        """
        if not feedbacks:
            return {"count": 0, "trends": {}}

        n = len(feedbacks)
        success_rates = [f.success_rate for f in feedbacks]
        failure_counts = [f.failure_nodes for f in feedbacks]
        rollback_counts = [f.rollback_nodes for f in feedbacks]

        # 趋势方向
        def _trend(values: list[float]) -> str:
            if len(values) < 2:
                return "stable"
            first_half = sum(values[:n//2]) / max(n//2, 1)
            second_half = sum(values[n//2:]) / max(n - n//2, 1)
            if second_half > first_half * 1.05:
                return "improving"
            elif second_half < first_half * 0.95:
                return "declining"
            return "stable"

        return {
            "count": n,
            "avg_success_rate": round(sum(success_rates) / n, 4),
            "avg_failure_count": round(sum(failure_counts) / n, 2),
            "avg_rollback_count": round(sum(rollback_counts) / n, 2),
            "trends": {
                "success_rate": _trend(success_rates),
                "failures": _trend([-c for c in failure_counts]),
                "rollbacks": _trend([-c for c in rollback_counts]),
            },
            "blocked_count": sum(1 for f in feedbacks if f.was_blocked),
            "approval_count": sum(1 for f in feedbacks if f.needed_approval),
        }

    # ── 辅助 ──────────────────────────────────────────────────

    def _extract_primary_action_type(
        self,
        engine_result: EngineResult,
        audit_entries: list[dict[str, Any]],
    ) -> str:
        """提取主要动作类型."""
        if audit_entries:
            # 取第一个审计条目的动作类型
            return audit_entries[0].get("action_type", "")
        return ""

    def _calculate_duration(self, engine_result: EngineResult) -> float:
        """计算执行耗时 (毫秒)."""
        if not engine_result.started_at or not engine_result.completed_at:
            return 0.0
        try:
            start = datetime.fromisoformat(engine_result.started_at)
            end = datetime.fromisoformat(engine_result.completed_at)
            return (end - start).total_seconds() * 1000
        except (ValueError, TypeError):
            return 0.0

    # ── 统计 ──────────────────────────────────────────────────

    @property
    def analysis_count(self) -> int:
        return self._analysis_count

    def reset(self) -> None:
        """重置计数器."""
        self._analysis_count = 0