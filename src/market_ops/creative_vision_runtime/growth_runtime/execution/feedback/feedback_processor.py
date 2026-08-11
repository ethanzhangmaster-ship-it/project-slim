"""E13.6.5 Feedback Processor — 反馈处理器.

将 ExecutionFeedback 和 RewardSignal 写入 Memory 系统:
  - DecisionMemory: 记录决策结果 (record_outcome)
  - ExperienceStore: 添加经验记录
  - MemoryEvolution: 触发记忆进化 (累计足够经验后)

核心设计:
  - 从 Reward 提取经验教训 (lessons)
  - 根据 Reward 方向生成改进建议 (recommendations)
  - 决定后续动作 (reinforce / adjust / abandon / observe)
  - 连接 E13.5.5 DecisionMemory 和 E13.4 MemoryEvolution

连接:
  RewardCalculator → FeedbackProcessor → DecisionMemory / ExperienceStore / MemoryEvolution
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import (
    ExecutionFeedback,
    FeedbackConfig,
    FeedbackResult,
    RewardSignal,
    create_default_config,
)


# ═══════════════════════════════════════════════════════════════
# Feedback Processor
# ═══════════════════════════════════════════════════════════════


class FeedbackProcessor:
    """反馈处理器 — 将 Reward 转化为 Memory 更新.

    用法:
        processor = FeedbackProcessor(
            decision_memory=decision_memory,
            experience_store=experience_store,
            memory_evolution=memory_evolution,
        )
        result = processor.process(feedback, reward)
    """

    def __init__(
        self,
        decision_memory: Any = None,
        experience_store: Any = None,
        memory_evolution: Any = None,
        config: FeedbackConfig | None = None,
    ):
        """初始化反馈处理器.

        Args:
            decision_memory: E13.5.5 DecisionMemory 实例
            experience_store: E13.4.1 ExperienceStore 实例
            memory_evolution: E13.4.5 MemoryEvolution 实例
            config: 反馈配置
        """
        self.decision_memory = decision_memory
        self.experience_store = experience_store
        self.memory_evolution = memory_evolution
        self.config = config or create_default_config()
        self._process_count: int = 0
        self._evolution_queue: list[FeedbackResult] = []

    # ── 主入口 ────────────────────────────────────────────────

    def process(
        self,
        feedback: ExecutionFeedback,
        reward: RewardSignal,
    ) -> FeedbackResult:
        """处理反馈，生成 FeedbackResult 并写入 Memory.

        Args:
            feedback: 执行反馈
            reward: Reward 信号

        Returns:
            FeedbackResult: 处理结果
        """
        self._process_count += 1

        # 提取经验教训
        lessons = self._extract_lessons(feedback, reward)

        # 生成改进建议
        recommendations = self._generate_recommendations(feedback, reward)

        # 决定后续动作
        next_action = self._determine_next_action(feedback, reward)

        result = FeedbackResult(
            feedback_id=feedback.feedback_id,
            decision_id=feedback.decision_id,
            feedback=feedback,
            reward=reward,
            lessons=lessons,
            recommendations=recommendations,
            next_action=next_action,
        )

        # 写入 DecisionMemory
        if self.decision_memory is not None:
            result.memory_updated = self._update_decision_memory(feedback, reward)

        # 写入 ExperienceStore
        if self.experience_store is not None:
            result.experience_stored = self._store_experience(feedback, reward)

        # 触发 MemoryEvolution
        if self.memory_evolution is not None:
            self._evolution_queue.append(result)
            if len(self._evolution_queue) >= self.config.evolution_trigger_threshold:
                result.evolution_triggered = self._trigger_evolution()

        return result

    # ── 经验教训提取 ──────────────────────────────────────────

    def _extract_lessons(
        self,
        feedback: ExecutionFeedback,
        reward: RewardSignal,
    ) -> list[str]:
        """从 Reward 中提取经验教训."""
        lessons: list[str] = []

        # 成功经验
        if reward.is_positive:
            if reward.execution_reward > 0.5:
                lessons.append(f"执行质量优秀 (成功率 {feedback.success_rate:.0%})")
            if reward.safety_reward > 0.5:
                lessons.append("安全规则通过，无拦截无警告")
            if reward.outcome_reward > 0.3:
                lessons.append(f"业务结果正向 (reward={reward.outcome_reward:.2f})")

        # 失败教训
        if feedback.has_failures:
            lessons.append(f"执行失败 {feedback.failure_nodes} 个节点，需排查失败原因")
        if feedback.has_rollbacks:
            lessons.append(f"触发 {feedback.rollback_nodes} 次回滚，需优化执行稳定性")
        if feedback.was_blocked:
            lessons.append("被安全层拦截，策略风险过高需调整")

        # 效率问题
        if feedback.execution_duration_ms > 10000:
            lessons.append(f"执行耗时 {feedback.execution_duration_ms:.0f}ms，效率偏低")

        # 安全警告
        if feedback.safety_evaluation:
            warnings = feedback.safety_evaluation.get("warnings", [])
            if warnings:
                lessons.append(f"安全警告 {len(warnings)} 条，需关注风险点")

        return lessons[:self.config.max_lessons]

    # ── 改进建议生成 ──────────────────────────────────────────

    def _generate_recommendations(
        self,
        feedback: ExecutionFeedback,
        reward: RewardSignal,
    ) -> list[str]:
        """生成改进建议."""
        recommendations: list[str] = []

        if reward.is_positive:
            recommendations.append("当前策略执行效果良好，建议在当前场景下继续使用")
            if reward.outcome_reward > 0.5:
                recommendations.append("业务结果优异，可考虑扩大投放规模")

        if reward.is_negative:
            if feedback.has_failures:
                recommendations.append("建议检查执行失败原因，修复后重新执行")
            if feedback.was_blocked:
                recommendations.append("建议降低策略风险等级或调整参数后重试")
            if reward.safety_reward < -0.3:
                recommendations.append("安全评分过低，建议审查策略安全性")

        if feedback.has_rollbacks:
            recommendations.append("建议增加前置校验，减少回滚发生")

        if reward.execution_reward < -0.3:
            recommendations.append("执行质量偏低，建议简化执行计划或增加重试机制")

        return recommendations[:self.config.max_recommendations]

    # ── 后续动作决策 ──────────────────────────────────────────

    def _determine_next_action(
        self,
        feedback: ExecutionFeedback,
        reward: RewardSignal,
    ) -> str:
        """决定后续动作.

        Returns:
            str: reinforce / adjust / abandon / observe
        """
        # 被拦截 → 放弃
        if feedback.was_blocked:
            return "abandon"

        # 正向 reward + 高置信度 → 强化
        if reward.is_positive and reward.confidence > self.config.min_confidence:
            return "reinforce"

        # 负向 reward → 调整
        if reward.is_negative:
            return "adjust"

        # 中性 → 观察
        return "observe"

    # ── Memory 更新 ───────────────────────────────────────────

    def _update_decision_memory(
        self,
        feedback: ExecutionFeedback,
        reward: RewardSignal,
    ) -> bool:
        """更新 DecisionMemory.

        Args:
            feedback: 执行反馈
            reward: Reward 信号

        Returns:
            bool: 是否成功更新
        """
        try:
            if not feedback.decision_id:
                return False

            # 确定结果
            if reward.is_positive:
                result = "success"
            elif feedback.has_failures:
                result = "failure"
            elif feedback.success_rate >= 0.8:
                result = "partial"
            else:
                result = "failure"

            self.decision_memory.record_outcome(
                decision_id=feedback.decision_id,
                result=result,
                metrics={
                    "total_reward": reward.total_reward,
                    "execution_reward": reward.execution_reward,
                    "safety_reward": reward.safety_reward,
                    "outcome_reward": reward.outcome_reward,
                    "success_rate": feedback.success_rate,
                    "failure_nodes": feedback.failure_nodes,
                    "rollback_nodes": feedback.rollback_nodes,
                },
                reason=self._build_reason(feedback, reward),
                lessons=self._extract_lessons(feedback, reward),
            )
            return True

        except Exception:
            return False

    def _store_experience(
        self,
        feedback: ExecutionFeedback,
        reward: RewardSignal,
    ) -> bool:
        """写入 ExperienceStore.

        Args:
            feedback: 执行反馈
            reward: Reward 信号

        Returns:
            bool: 是否成功写入
        """
        try:
            # 尝试使用 ExperienceStore 的 add 方法
            if hasattr(self.experience_store, "add_experience"):
                self.experience_store.add_experience(
                    decision_id=feedback.decision_id,
                    feedback=feedback.to_dict(),
                    reward=reward.to_dict(),
                )
                return True
            elif hasattr(self.experience_store, "add"):
                self.experience_store.add(
                    data={
                        "type": "execution_feedback",
                        "decision_id": feedback.decision_id,
                        "feedback": feedback.to_dict(),
                        "reward": reward.to_dict(),
                    }
                )
                return True
            return False

        except Exception:
            return False

    def _trigger_evolution(self) -> bool:
        """触发 MemoryEvolution."""
        try:
            if hasattr(self.memory_evolution, "evolve"):
                self.memory_evolution.evolve()
                self._evolution_queue.clear()
                return True
            return False

        except Exception:
            return False

    # ── 辅助 ──────────────────────────────────────────────────

    def _build_reason(
        self,
        feedback: ExecutionFeedback,
        reward: RewardSignal,
    ) -> str:
        """构建结果原因描述."""
        parts = []
        if reward.is_positive:
            parts.append(f"执行成功 (reward={reward.total_reward:.2f})")
        elif reward.is_negative:
            parts.append(f"执行效果不佳 (reward={reward.total_reward:.2f})")
        else:
            parts.append(f"执行效果中性 (reward={reward.total_reward:.2f})")

        if feedback.has_failures:
            parts.append(f"{feedback.failure_nodes}个节点失败")
        if feedback.has_rollbacks:
            parts.append(f"{feedback.rollback_nodes}次回滚")
        if feedback.was_blocked:
            parts.append("被安全层拦截")

        return "; ".join(parts)

    # ── 统计 ──────────────────────────────────────────────────

    @property
    def process_count(self) -> int:
        return self._process_count

    @property
    def queued_evolution_count(self) -> int:
        return len(self._evolution_queue)

    def reset(self) -> None:
        """重置处理器."""
        self._process_count = 0
        self._evolution_queue.clear()