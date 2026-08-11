"""E13.6.5 Feedback Loop — 主闭环控制器.

将 ExecutionEngine 的输出转化为 Feedback，驱动 Memory 系统更新，
形成完整的 Observe → Understand → Decide → Execute → Learn → Improve 闭环。

核心流程:
  EngineResult + AuditLog + ExecutionContext + SafetyEvaluation
      ↓
  ResultAnalyzer.analyze() → ExecutionFeedback
      ↓
  RewardCalculator.calculate() → RewardSignal
      ↓
  FeedbackProcessor.process() → FeedbackResult
      ↓
  DecisionMemory / ExperienceStore / MemoryEvolution

连接:
  E13.6.3 ExecutionEngine → E13.6.5 FeedbackLoop → E13.5.5 DecisionMemory → E13.4 MemoryEvolution
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..audit_log import AuditLog
from ..execution_context import ExecutionContext
from ..execution_core import EngineResult
from .feedback_processor import FeedbackProcessor
from .models import (
    ExecutionFeedback,
    FeedbackConfig,
    FeedbackResult,
    RewardSignal,
    create_default_config,
)
from .result_analyzer import ResultAnalyzer
from .reward_calculator import RewardCalculator


# ═══════════════════════════════════════════════════════════════
# Feedback Loop
# ═══════════════════════════════════════════════════════════════


class FeedbackLoop:
    """反馈闭环控制器 — 连接 Execution → Reward → Memory.

    用法:
        loop = FeedbackLoop(
            decision_memory=decision_memory,
            experience_store=experience_store,
            memory_evolution=memory_evolution,
        )
        result = loop.run(
            engine_result=engine_result,
            audit_log=audit_log,
            context=execution_context,
            safety_evaluation=safety_eval,
        )
    """

    def __init__(
        self,
        decision_memory: Any = None,
        experience_store: Any = None,
        memory_evolution: Any = None,
        config: FeedbackConfig | None = None,
    ):
        """初始化反馈闭环.

        Args:
            decision_memory: E13.5.5 DecisionMemory 实例
            experience_store: E13.4.1 ExperienceStore 实例
            memory_evolution: E13.4.5 MemoryEvolution 实例
            config: 反馈配置
        """
        self.config = config or create_default_config()
        self._analyzer = ResultAnalyzer()
        self._calculator = RewardCalculator(config=self.config)
        self._processor = FeedbackProcessor(
            decision_memory=decision_memory,
            experience_store=experience_store,
            memory_evolution=memory_evolution,
            config=self.config,
        )
        self._loop_count: int = 0
        self._history: list[FeedbackResult] = []

    # ── 属性 ──────────────────────────────────────────────────

    @property
    def analyzer(self) -> ResultAnalyzer:
        return self._analyzer

    @property
    def calculator(self) -> RewardCalculator:
        return self._calculator

    @property
    def processor(self) -> FeedbackProcessor:
        return self._processor

    # ── 主入口 ────────────────────────────────────────────────

    def run(
        self,
        engine_result: EngineResult,
        audit_log: AuditLog | None = None,
        context: ExecutionContext | None = None,
        safety_evaluation: dict[str, Any] | None = None,
        business_metrics: dict[str, Any] | None = None,
    ) -> FeedbackResult:
        """执行完整的反馈闭环.

        Args:
            engine_result: 执行引擎结果
            audit_log: 审计日志
            context: 执行上下文
            safety_evaluation: 安全评估结果 (dict)
            business_metrics: 业务指标 (ROAS 变化等)

        Returns:
            FeedbackResult: 反馈处理结果
        """
        self._loop_count += 1

        # Step 1: 分析执行结果
        feedback = self._analyzer.analyze(
            engine_result=engine_result,
            audit_log=audit_log,
            context=context,
            safety_evaluation=safety_evaluation,
        )

        # Step 2: 计算 Reward
        reward = self._calculator.calculate(
            feedback=feedback,
            business_metrics=business_metrics,
        )

        # Step 3: 处理反馈 → 写入 Memory
        result = self._processor.process(
            feedback=feedback,
            reward=reward,
        )

        # 记录历史
        self._history.append(result)

        return result

    # ── 简化入口 ──────────────────────────────────────────────

    def run_simple(
        self,
        engine_result: EngineResult,
        context: ExecutionContext | None = None,
    ) -> FeedbackResult:
        """简化版闭环 (无 AuditLog、SafetyEvaluation、BusinessMetrics).

        Args:
            engine_result: 执行引擎结果
            context: 执行上下文

        Returns:
            FeedbackResult: 反馈处理结果
        """
        return self.run(
            engine_result=engine_result,
            audit_log=None,
            context=context,
            safety_evaluation=None,
            business_metrics=None,
        )

    # ── 批量运行 ──────────────────────────────────────────────

    def run_batch(
        self,
        engine_results: list[EngineResult],
        audit_log: AuditLog | None = None,
        context: ExecutionContext | None = None,
        safety_evaluation: dict[str, Any] | None = None,
        business_metrics: dict[str, Any] | None = None,
    ) -> list[FeedbackResult]:
        """批量运行反馈闭环.

        Args:
            engine_results: 执行引擎结果列表
            audit_log: 审计日志
            context: 执行上下文
            safety_evaluation: 安全评估结果
            business_metrics: 业务指标

        Returns:
            list[FeedbackResult]: 反馈结果列表
        """
        return [
            self.run(
                engine_result=result,
                audit_log=audit_log,
                context=context,
                safety_evaluation=safety_evaluation,
                business_metrics=business_metrics,
            )
            for result in engine_results
        ]

    # ── 查询 ──────────────────────────────────────────────────

    def get_history(self, limit: int = 50) -> list[FeedbackResult]:
        """获取最近的反馈历史."""
        return self._history[-limit:]

    def get_by_decision(self, decision_id: str) -> list[FeedbackResult]:
        """按决策 ID 查询反馈."""
        return [r for r in self._history if r.decision_id == decision_id]

    def get_positive_results(self) -> list[FeedbackResult]:
        """获取正向反馈."""
        return [
            r for r in self._history
            if r.reward and r.reward.is_positive
        ]

    def get_negative_results(self) -> list[FeedbackResult]:
        """获取负向反馈."""
        return [
            r for r in self._history
            if r.reward and r.reward.is_negative
        ]

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """获取反馈闭环统计."""
        total = len(self._history)
        if total == 0:
            return {
                "total_loops": 0,
                "positive_rate": 0.0,
                "memory_update_rate": 0.0,
                "evolution_triggered": 0,
                "next_actions": {},
            }

        positive = sum(1 for r in self._history if r.reward and r.reward.is_positive)
        negative = sum(1 for r in self._history if r.reward and r.reward.is_negative)
        memory_updated = sum(1 for r in self._history if r.memory_updated)
        evolution_triggered = sum(1 for r in self._history if r.evolution_triggered)

        actions: dict[str, int] = {}
        for r in self._history:
            actions[r.next_action] = actions.get(r.next_action, 0) + 1

        return {
            "total_loops": total,
            "positive_count": positive,
            "negative_count": negative,
            "neutral_count": total - positive - negative,
            "positive_rate": round(positive / total, 4),
            "memory_update_rate": round(memory_updated / total, 4),
            "evolution_triggered": evolution_triggered,
            "next_actions": actions,
            "analyzer": {"analysis_count": self._analyzer.analysis_count},
            "calculator": {"calculation_count": self._calculator.calculation_count},
            "processor": {
                "process_count": self._processor.process_count,
                "queued_evolution": self._processor.queued_evolution_count,
            },
        }

    def get_trends(self) -> dict[str, Any]:
        """获取 Reward 趋势分析."""
        if not self._history:
            return {"count": 0, "trend": "no_data"}

        rewards = [r.reward for r in self._history if r.reward]
        if not rewards:
            return {"count": 0, "trend": "no_data"}

        return self._calculator.get_reward_distribution(rewards)

    # ── 生命周期 ──────────────────────────────────────────────

    @property
    def loop_count(self) -> int:
        return self._loop_count

    def reset(self) -> None:
        """重置闭环控制器."""
        self._loop_count = 0
        self._history.clear()
        self._analyzer.reset()
        self._calculator.reset()
        self._processor.reset()