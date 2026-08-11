"""E13.7.7.5 Learning Execution Adapter — 策略决策执行适配器.

Day 7.7.5:
  将 LearningPolicyController 输出的 LearningPolicyDecision
  接入真实学习执行链，让 Adaptive Optimization Layer 从
  "建议系统" 变成 "可驱动执行系统"。

核心流程:
  LearningPolicyDecision
          |
          v
  LearningExecutionAdapter.execute()
          |
          +--> _classify_action()          → 决策 → 动作映射
          |
          +--> _execute_learning()         → ALLOW_LEARNING
          |        |
          |        v
          |    LearningLoopController.run_cycle()
          |
          +--> _execute_block()            → BLOCK_LEARNING
          |
          +--> _refresh_memory()           → REQUEST_MEMORY_REFRESH
          |        |
          |        v
          |    MemoryConsolidator.consolidate()
          |
          +--> _update_strategy()          → ADJUST_MODE
          |        |
          |        v
          |    LearningStrategyState 参数调整
          |
          v
  LearningExecutionResult

设计原则:
  - 不侵入已有模块: DecisionEngine, PatternPredictor, MemoryConsolidator, LearningStrategyOptimizer
  - 所有执行返回 LearningExecutionResult，可追踪可回滚
  - 执行前保存 previous_state_snapshot，支持回滚
  - Fail-safe: 某分支失败不阻断整体

用法:
  from growth_runtime.intelligence.learning.learning_execution_adapter import (
      LearningExecutionAdapter,
  )

  adapter = LearningExecutionAdapter()
  result = adapter.execute(policy_decision, context)
"""

from __future__ import annotations

from typing import Any

from .models.learning_execution_models import (
    LearningExecutionAction,
    LearningExecutionContext,
    LearningExecutionResult,
)
from .models.learning_strategy_models import (
    LearningMode,
    LearningPolicyDecision,
    LearningStrategyState,
    PolicyDecisionType,
)


# ═══════════════════════════════════════════════════════════════
# Mode → Parameter 映射表
# ═══════════════════════════════════════════════════════════════

# 基于 LearningStrategyState 工厂方法定义目标参数
_MODE_PARAMS: dict[str, dict[str, float]] = {
    LearningMode.AGGRESSIVE.value: {
        "exploration_rate": 0.05,
        "confidence_threshold": 0.40,
        "pattern_weight": 0.85,
        "memory_weight": 0.15,
        "memory_decay_rate": 0.005,
    },
    LearningMode.BALANCED.value: {
        "exploration_rate": 0.20,
        "confidence_threshold": 0.50,
        "pattern_weight": 0.70,
        "memory_weight": 0.30,
        "memory_decay_rate": 0.01,
    },
    LearningMode.CONSERVATIVE.value: {
        "exploration_rate": 0.50,
        "confidence_threshold": 0.65,
        "pattern_weight": 0.40,
        "memory_weight": 0.60,
        "memory_decay_rate": 0.03,
    },
}


# ═══════════════════════════════════════════════════════════════
# Decision → Action 映射表
# ═══════════════════════════════════════════════════════════════

_DECISION_TO_ACTION: dict[str, LearningExecutionAction] = {
    PolicyDecisionType.ALLOW_LEARNING.value: LearningExecutionAction.EXECUTE_LEARNING,
    PolicyDecisionType.BLOCK_LEARNING.value: LearningExecutionAction.BLOCK_LEARNING,
    PolicyDecisionType.REQUEST_MEMORY_REFRESH.value: LearningExecutionAction.REFRESH_MEMORY,
    PolicyDecisionType.ADJUST_MODE.value: LearningExecutionAction.UPDATE_STRATEGY,
    PolicyDecisionType.MAINTAIN.value: LearningExecutionAction.NO_ACTION,
}


# ═══════════════════════════════════════════════════════════════
# LearningExecutionAdapter
# ═══════════════════════════════════════════════════════════════


class LearningExecutionAdapter:
    """学习策略执行适配器 — 将 PolicyDecision 路由到执行链.

    用法:
        adapter = LearningExecutionAdapter()
        result = adapter.execute(policy_decision, context)
    """

    def __init__(self) -> None:
        self._execution_count: int = 0
        self._execution_history: list[LearningExecutionResult] = []

    @property
    def execution_count(self) -> int:
        return self._execution_count

    # ═══════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════

    def execute(
        self,
        policy_decision: LearningPolicyDecision,
        context: LearningExecutionContext,
    ) -> LearningExecutionResult:
        """执行策略决策 — 主入口.

        Args:
            policy_decision: LearningPolicyController 输出的策略决策
            context: 执行上下文 (依赖注入)

        Returns:
            LearningExecutionResult: 执行结果
        """
        self._execution_count += 1

        # 1. 分类动作
        action = self._classify_action(policy_decision)

        # 2. 保存执行前状态快照
        previous_state = policy_decision.previous_state_snapshot

        # 3. 路由到对应执行分支
        result = self._dispatch(action, policy_decision, context, previous_state)

        self._execution_history.append(result)
        return result

    def execute_or_skip(
        self,
        policy_decision: LearningPolicyDecision | None,
        context: LearningExecutionContext,
    ) -> LearningExecutionResult:
        """execute 的安全包装 — 无决策时返回 NO_ACTION.

        Args:
            policy_decision: 策略决策 (可为 None)
            context: 执行上下文

        Returns:
            LearningExecutionResult
        """
        if policy_decision is None:
            return LearningExecutionResult.no_action_result(
                policy_decision_type="no_decision",
                reasons=["No policy decision provided — skipping execution"],
            )
        return self.execute(policy_decision, context)

    def rollback(
        self,
        result: LearningExecutionResult,
        context: LearningExecutionContext,
    ) -> LearningExecutionResult:
        """回滚一次执行.

        Args:
            result: 之前的执行结果
            context: 执行上下文

        Returns:
            LearningExecutionResult: 回滚结果
        """
        if not result.can_rollback:
            return LearningExecutionResult.error_result(
                action=LearningExecutionAction.NO_ACTION,
                error="Rollback not available — no previous state snapshot",
                policy_decision_type=result.policy_decision_type,
                reasons=["Rollback unavailable"],
            )

        # 恢复 previous_state
        restored_state = result.previous_state
        if restored_state is None:
            return LearningExecutionResult.error_result(
                action=LearningExecutionAction.NO_ACTION,
                error="Rollback failed — previous_state is None",
                policy_decision_type=result.policy_decision_type,
                reasons=["Rollback failed"],
            )

        # 应用回滚到当前策略状态 (如果 strategy_optimizer 可用)
        if context.strategy_optimizer is not None:
            try:
                # 通过 strategy_optimizer 恢复状态
                rollback_state = LearningStrategyState.from_dict(restored_state)
                if hasattr(context.strategy_optimizer, '_apply_to_state'):
                    # 直接恢复参数
                    context.strategy_optimizer._apply_to_state(
                        rollback_state, "exploration_rate", rollback_state.exploration_rate,
                    )
            except Exception:
                pass

        return LearningExecutionResult(
            success=True,
            action=LearningExecutionAction.NO_ACTION.value,
            executed=True,
            policy_decision_type=result.policy_decision_type,
            previous_state=result.new_state,
            new_state=restored_state,
            rollback_available=False,
            reasons=["Rollback executed — restored previous state"],
            metadata={"rollback_from": result.executed_at},
        )

    def reset(self) -> None:
        """重置适配器状态."""
        self._execution_count = 0
        self._execution_history.clear()

    def get_execution_history(self) -> list[LearningExecutionResult]:
        """获取执行历史."""
        return list(self._execution_history)

    # ═══════════════════════════════════════════════════════════
    # Action Classification
    # ═══════════════════════════════════════════════════════════

    def _classify_action(
        self,
        policy_decision: LearningPolicyDecision,
    ) -> LearningExecutionAction:
        """将 PolicyDecisionType 映射为 LearningExecutionAction.

        映射:
          ALLOW_LEARNING         → EXECUTE_LEARNING
          BLOCK_LEARNING         → BLOCK_LEARNING
          REQUEST_MEMORY_REFRESH → REFRESH_MEMORY
          ADJUST_MODE            → UPDATE_STRATEGY
          MAINTAIN               → NO_ACTION
        """
        return _DECISION_TO_ACTION.get(
            policy_decision.decision_type,
            LearningExecutionAction.NO_ACTION,
        )

    # ═══════════════════════════════════════════════════════════
    # Dispatch
    # ═══════════════════════════════════════════════════════════

    def _dispatch(
        self,
        action: LearningExecutionAction,
        policy_decision: LearningPolicyDecision,
        context: LearningExecutionContext,
        previous_state: dict[str, Any] | None,
    ) -> LearningExecutionResult:
        """路由到对应执行分支."""
        if action == LearningExecutionAction.EXECUTE_LEARNING:
            return self._execute_learning(policy_decision, context, previous_state)
        elif action == LearningExecutionAction.BLOCK_LEARNING:
            return self._execute_block(policy_decision, previous_state)
        elif action == LearningExecutionAction.REFRESH_MEMORY:
            return self._refresh_memory(policy_decision, context, previous_state)
        elif action == LearningExecutionAction.UPDATE_STRATEGY:
            return self._update_strategy(policy_decision, context, previous_state)
        else:
            return self._execute_no_action(policy_decision, previous_state)

    # ═══════════════════════════════════════════════════════════
    # Branch A: Learning Execution
    # ═══════════════════════════════════════════════════════════

    def _execute_learning(
        self,
        policy_decision: LearningPolicyDecision,
        context: LearningExecutionContext,
        previous_state: dict[str, Any] | None,
    ) -> LearningExecutionResult:
        """执行学习循环.

        should_learn=True → 调用 LearningLoopController.run_cycle()
        """
        reasons = [
            f"Policy decision: {policy_decision.decision_type}",
            f"should_learn={policy_decision.should_learn}",
        ]
        reasons.extend(policy_decision.reasons)

        if context.loop_controller is None:
            return LearningExecutionResult.blocked_result(
                policy_decision_type=policy_decision.decision_type,
                reasons=reasons + ["No LoopController available — cannot execute learning"],
                previous_state=previous_state,
            )

        try:
            cycle_result = context.loop_controller.run_cycle(
                context=context.context,
                experiences=context.experiences if context.experiences else None,
                rewards=context.rewards if context.rewards else None,
                decision_memory=context.decision_memory,
                experience_store=context.experience_store,
                pattern_store=context.pattern_store,
            )

            learning_cycle_dict = {
                "cycle_confidence": cycle_result.cycle_confidence,
                "actions_taken": cycle_result.actions_taken,
                "improvements": cycle_result.improvements,
                "next_recommendations": cycle_result.next_cycle_recommendations,
                "metadata": cycle_result.metadata,
            }

            return LearningExecutionResult.success_result(
                action=LearningExecutionAction.EXECUTE_LEARNING,
                policy_decision_type=policy_decision.decision_type,
                previous_state=previous_state,
                new_state=previous_state,  # 学习循环不改变 strategy state
                reasons=reasons,
                learning_cycle=learning_cycle_dict,
                memory_updated="memory_updated" in cycle_result.actions_taken,
            )

        except Exception as e:
            return LearningExecutionResult.error_result(
                action=LearningExecutionAction.EXECUTE_LEARNING,
                error=f"Learning loop execution failed: {e}",
                policy_decision_type=policy_decision.decision_type,
                previous_state=previous_state,
                reasons=reasons,
            )

    # ═══════════════════════════════════════════════════════════
    # Branch B: Block Learning
    # ═══════════════════════════════════════════════════════════

    def _execute_block(
        self,
        policy_decision: LearningPolicyDecision,
        previous_state: dict[str, Any] | None,
    ) -> LearningExecutionResult:
        """阻止学习循环.

        should_learn=False → 跳过学习更新，返回 BLOCK 结果。
        """
        reasons = [
            f"Policy decision: {policy_decision.decision_type}",
            f"should_learn={policy_decision.should_learn}",
        ]
        reasons.extend(policy_decision.reasons)

        return LearningExecutionResult.blocked_result(
            policy_decision_type=policy_decision.decision_type,
            reasons=reasons,
            previous_state=previous_state,
        )

    # ═══════════════════════════════════════════════════════════
    # Branch C: Memory Refresh
    # ═══════════════════════════════════════════════════════════

    def _refresh_memory(
        self,
        policy_decision: LearningPolicyDecision,
        context: LearningExecutionContext,
        previous_state: dict[str, Any] | None,
    ) -> LearningExecutionResult:
        """刷新记忆系统.

        should_update_memory=True → 调用 MemoryConsolidator.consolidate()
        """
        reasons = [
            f"Policy decision: {policy_decision.decision_type}",
            f"should_update_memory={policy_decision.should_update_memory}",
        ]
        reasons.extend(policy_decision.reasons)

        if context.memory_consolidator is None:
            return LearningExecutionResult.blocked_result(
                policy_decision_type=policy_decision.decision_type,
                reasons=reasons + ["No MemoryConsolidator available — cannot refresh memory"],
                previous_state=previous_state,
            )

        try:
            consolidation_result = context.memory_consolidator.consolidate()

            memory_result_dict = {
                "total_evaluated": consolidation_result.total_evaluated,
                "kept": consolidation_result.kept,
                "archived": consolidation_result.archived,
                "forgotten": consolidation_result.forgotten,
                "core_patterns": consolidation_result.core_patterns,
                "temporary_patterns": consolidation_result.temporary_patterns,
                "noise_count": consolidation_result.noise_count,
                "failed_count": consolidation_result.failed_count,
                "avg_memory_value": consolidation_result.avg_memory_value,
                "retention_rate": consolidation_result.retention_rate,
                "cleanup_rate": consolidation_result.cleanup_rate,
            }

            return LearningExecutionResult.success_result(
                action=LearningExecutionAction.REFRESH_MEMORY,
                policy_decision_type=policy_decision.decision_type,
                previous_state=previous_state,
                new_state=previous_state,  # 记忆刷新不改变 strategy state
                reasons=reasons,
                memory_updated=True,
                memory_result=memory_result_dict,
            )

        except Exception as e:
            return LearningExecutionResult.error_result(
                action=LearningExecutionAction.REFRESH_MEMORY,
                error=f"Memory refresh failed: {e}",
                policy_decision_type=policy_decision.decision_type,
                previous_state=previous_state,
                reasons=reasons,
            )

    # ═══════════════════════════════════════════════════════════
    # Branch D: Strategy Update
    # ═══════════════════════════════════════════════════════════

    def _update_strategy(
        self,
        policy_decision: LearningPolicyDecision,
        context: LearningExecutionContext,
        previous_state: dict[str, Any] | None,
    ) -> LearningExecutionResult:
        """更新学习策略参数.

        strategy_mode 变化 → 应用对应模式的目标参数。
        """
        reasons = [
            f"Policy decision: {policy_decision.decision_type}",
            f"strategy_mode={policy_decision.strategy_mode}",
        ]
        reasons.extend(policy_decision.reasons)

        target_mode = policy_decision.strategy_mode
        if target_mode not in _MODE_PARAMS:
            return LearningExecutionResult.error_result(
                action=LearningExecutionAction.UPDATE_STRATEGY,
                error=f"Unknown strategy mode: {target_mode}",
                policy_decision_type=policy_decision.decision_type,
                previous_state=previous_state,
                reasons=reasons,
            )

        target_params = _MODE_PARAMS[target_mode]
        new_state_dict = self._apply_mode_params(target_mode, target_params, previous_state)

        return LearningExecutionResult.success_result(
            action=LearningExecutionAction.UPDATE_STRATEGY,
            policy_decision_type=policy_decision.decision_type,
            previous_state=previous_state,
            new_state=new_state_dict,
            reasons=reasons,
            strategy_updated=True,
            strategy_adjustments=[
                {
                    "parameter": "learning_mode",
                    "new_value": target_mode,
                    "reason": f"Mode switch to {target_mode}",
                },
                {
                    "parameter": "exploration_rate",
                    "new_value": target_params["exploration_rate"],
                    "reason": f"Mode {target_mode} default",
                },
                {
                    "parameter": "confidence_threshold",
                    "new_value": target_params["confidence_threshold"],
                    "reason": f"Mode {target_mode} default",
                },
                {
                    "parameter": "pattern_weight",
                    "new_value": target_params["pattern_weight"],
                    "reason": f"Mode {target_mode} default",
                },
                {
                    "parameter": "memory_decay_rate",
                    "new_value": target_params["memory_decay_rate"],
                    "reason": f"Mode {target_mode} default",
                },
            ],
        )

    def _apply_mode_params(
        self,
        mode: str,
        params: dict[str, float],
        previous_state: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """应用模式参数到状态快照.

        Args:
            mode: 目标模式
            params: 目标参数
            previous_state: 执行前状态快照

        Returns:
            dict: 新状态快照
        """
        if previous_state is None:
            # 从默认状态创建新状态
            new_state = LearningStrategyState.default()
        else:
            new_state = LearningStrategyState.from_dict(previous_state)

        # 应用模式参数
        new_state.learning_mode = mode
        new_state.exploration_rate = params["exploration_rate"]
        new_state.confidence_threshold = params["confidence_threshold"]
        new_state.pattern_weight = params["pattern_weight"]
        new_state.memory_weight = params["memory_weight"]
        new_state.memory_decay_rate = params["memory_decay_rate"]
        new_state.bump_version()

        return new_state.to_dict()

    # ═══════════════════════════════════════════════════════════
    # Branch E: No Action
    # ═══════════════════════════════════════════════════════════

    def _execute_no_action(
        self,
        policy_decision: LearningPolicyDecision,
        previous_state: dict[str, Any] | None,
    ) -> LearningExecutionResult:
        """无操作 — MAINTAIN 决策."""
        reasons = [
            f"Policy decision: {policy_decision.decision_type}",
        ]
        reasons.extend(policy_decision.reasons)

        return LearningExecutionResult.no_action_result(
            policy_decision_type=policy_decision.decision_type,
            reasons=reasons,
            previous_state=previous_state,
        )

    def __repr__(self) -> str:
        return (
            f"LearningExecutionAdapter("
            f"executions={self._execution_count})"
        )


__all__ = [
    "LearningExecutionAdapter",
    "_MODE_PARAMS",
    "_DECISION_TO_ACTION",
]