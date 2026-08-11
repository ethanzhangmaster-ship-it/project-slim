"""E14.7.3 Execution Feedback Collector — 执行反馈收集器.

E14.7「Autonomous Growth Execution Layer」第三层:
  将 ExecutionOutcome 转化为 GrowthExperience，接入 E13.4 记忆系统.

职责:
  1. 收集执行结果 (ExecutionOutcome → ExecutionFeedback)
  2. 评估执行效果 (RewardCalculator)
  3. 转化为 GrowthExperience (对接 E13.4.1 ExperienceStore)
  4. 反馈管道 (FeedbackPipeline)

核心概念:
  - ExecutionFeedback: 执行反馈 (含评估结果)
  - RewardMetrics: 奖励指标 (ROAS / CPI / CTR / CVR / retention / payer_rate)
  - RewardCalculator: 奖励计算器
  - ExecutionFeedbackCollector: 反馈收集器
  - FeedbackPipeline: 完整反馈管道

数据流:
  ExecutionOutcome (E14.7.2)
       ↓
  ExecutionFeedbackCollector.collect()
       ↓
  ExecutionFeedback
       ↓
  RewardCalculator.calculate()
       ↓
  GrowthExperience (E13.4.1)
       ↓
  ExperienceStore.store()
       ↓
  PatternMiner.mine() → PatternMemory (E13.4.2)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
    ExecutionOutcome,
    ExecutionStatus,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
    ExperienceCategory,
    ExperienceContext,
    ExperienceOutcome as E13ExperienceOutcome,
    ExperienceOutcomeLevel,
    GrowthExperience,
)


# ═══════════════════════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════════════════════

class FeedbackQuality(str, Enum):
    """反馈质量等级."""
    STRONG = "strong"
    RELIABLE = "reliable"
    WEAK = "weak"
    INCONCLUSIVE = "inconclusive"


# ═══════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════

@dataclass
class RewardMetrics:
    """奖励指标 — 评估执行效果的核心指标.

    Attributes:
        roas_delta: ROAS 变化 (after - before)
        cpi_delta: CPI 变化 (负值=改善)
        ctr_delta: CTR 变化
        cvr_delta: CVR 变化
        retention_d3_delta: D3 留存变化
        retention_d7_delta: D7 留存变化
        payer_rate_delta: 付费率变化
        ltv_d30_delta: D30 LTV 变化
    """
    roas_delta: float = 0.0
    cpi_delta: float = 0.0
    ctr_delta: float = 0.0
    cvr_delta: float = 0.0
    retention_d3_delta: float = 0.0
    retention_d7_delta: float = 0.0
    payer_rate_delta: float = 0.0
    ltv_d30_delta: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "roas_delta": self.roas_delta,
            "cpi_delta": self.cpi_delta,
            "ctr_delta": self.ctr_delta,
            "cvr_delta": self.cvr_delta,
            "retention_d3_delta": self.retention_d3_delta,
            "retention_d7_delta": self.retention_d7_delta,
            "payer_rate_delta": self.payer_rate_delta,
            "ltv_d30_delta": self.ltv_d30_delta,
        }

    @classmethod
    def from_dict(cls, d: dict[str, float]) -> "RewardMetrics":
        return cls(
            roas_delta=d.get("roas_delta", 0.0),
            cpi_delta=d.get("cpi_delta", 0.0),
            ctr_delta=d.get("ctr_delta", 0.0),
            cvr_delta=d.get("cvr_delta", 0.0),
            retention_d3_delta=d.get("retention_d3_delta", 0.0),
            retention_d7_delta=d.get("retention_d7_delta", 0.0),
            payer_rate_delta=d.get("payer_rate_delta", 0.0),
            ltv_d30_delta=d.get("ltv_d30_delta", 0.0),
        )


@dataclass
class ExecutionFeedback:
    """执行反馈 — 对一次 ExecutionOutcome 的评估结果.

    Attributes:
        feedback_id: 反馈 ID
        execution_id: 对应的执行 ID
        action_id: 对应的动作 ID
        action_type: 动作类型
        success: 是否成功
        outcome_level: 结果等级
        reward: 综合奖励 [0, 1]
        metrics: 奖励指标
        quality: 反馈质量
        insights: 洞察列表
        error: 错误信息
        created_at: 创建时间
        metadata: 扩展元数据
    """
    feedback_id: str = field(default_factory=lambda: f"fb_{uuid.uuid4().hex[:8]}")
    execution_id: str = ""
    action_id: str = ""
    action_type: str = ""
    success: bool = False
    outcome_level: ExperienceOutcomeLevel = ExperienceOutcomeLevel.NEUTRAL
    reward: float = 0.0
    metrics: RewardMetrics = field(default_factory=RewardMetrics)
    quality: FeedbackQuality = FeedbackQuality.INCONCLUSIVE
    insights: list[str] = field(default_factory=list)
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "execution_id": self.execution_id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "success": self.success,
            "outcome_level": self.outcome_level.value,
            "reward": self.reward,
            "metrics": self.metrics.to_dict(),
            "quality": self.quality.value,
            "insights": self.insights,
            "error": self.error,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    def to_experience_outcome(self) -> E13ExperienceOutcome:
        """转化为 E13.4.1 ExperienceOutcome."""
        return E13ExperienceOutcome(
            success=self.success,
            outcome_level=self.outcome_level,
            metrics_delta=self.metrics.to_dict(),
            actual_impact="; ".join(self.insights) if self.insights else "",
            actual_reward=self.reward,
            error=self.error,
        )


# ═══════════════════════════════════════════════════════════
# RewardCalculator
# ═══════════════════════════════════════════════════════════

class RewardCalculator:
    """奖励计算器 — 根据执行结果指标计算综合奖励.

    使用加权公式 (与 E14.6.3 对齐):
      reward = roas×0.4 + (ctr+cvr)×0.15 + payer_rate×0.3

    指标归一化:
      使用 sigmoid 将 delta 值映射到 [0, 1]
    """

    # 默认权重 (与 E14.6.3 一致)
    DEFAULT_WEIGHTS: dict[str, float] = {
        "roas": 0.40,
        "ctr": 0.075,
        "cvr": 0.075,
        "payer_rate": 0.30,
        "retention_d7": 0.075,
        "cpi": 0.075,
    }

    def __init__(self, weights: dict[str, float] | None = None):
        self._weights = weights or dict(self.DEFAULT_WEIGHTS)
        self._calculation_count: int = 0

    def calculate(self, metrics: RewardMetrics) -> float:
        """计算综合奖励.

        Args:
            metrics: 奖励指标

        Returns:
            float: 综合奖励 [0, 1]
        """
        self._calculation_count += 1

        reward = (
            self._weights["roas"] * self._normalize_delta(metrics.roas_delta, scale=0.5)
            + self._weights["ctr"] * self._normalize_delta(metrics.ctr_delta, scale=0.3)
            + self._weights["cvr"] * self._normalize_delta(metrics.cvr_delta, scale=0.3)
            + self._weights["payer_rate"] * self._normalize_delta(metrics.payer_rate_delta, scale=0.2)
            + self._weights["retention_d7"] * self._normalize_delta(metrics.retention_d7_delta, scale=0.2)
            + self._weights["cpi"] * self._normalize_delta(-metrics.cpi_delta, scale=0.3)
        )

        return round(max(0.0, min(1.0, reward)), 4)

    def _normalize_delta(self, delta: float, scale: float = 0.5) -> float:
        """Sigmoid 归一化 delta 到 [0, 1].

        Args:
            delta: 指标变化值
            scale: 缩放因子 (控制灵敏度)

        Returns:
            float: 归一化值 [0, 1]
        """
        import math
        return 1.0 / (1.0 + math.exp(-delta / max(scale, 0.01)))

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    @property
    def calculation_count(self) -> int:
        return self._calculation_count


# ═══════════════════════════════════════════════════════════
# ExecutionFeedbackCollector
# ═══════════════════════════════════════════════════════════

class ExecutionFeedbackCollector:
    """执行反馈收集器 — 收集 ExecutionOutcome 并生成反馈.

    核心职责:
      1. 从 ExecutionOutcome 提取指标
      2. 计算奖励
      3. 生成 ExecutionFeedback
      4. 转化为 GrowthExperience 并存入 ExperienceStore

    用法:
        collector = ExecutionFeedbackCollector()
        feedback = collector.collect(outcome)
        experience = collector.to_experience(feedback, context)
        collector.store(experience, store)
    """

    def __init__(self, reward_calculator: RewardCalculator | None = None):
        self._reward_calculator = reward_calculator or RewardCalculator()
        self._feedback_history: list[ExecutionFeedback] = []
        self._collection_count: int = 0

    # ── 核心: 收集 ────────────────────────────────────────

    def collect(self, outcome: ExecutionOutcome) -> ExecutionFeedback:
        """收集执行结果并生成反馈.

        Args:
            outcome: E14.7.2 执行结果

        Returns:
            ExecutionFeedback: 执行反馈
        """
        self._collection_count += 1

        # 提取指标
        metrics = self._extract_metrics(outcome)

        # 计算奖励
        reward = self._reward_calculator.calculate(metrics)

        # 判断成功/失败
        success = outcome.status == ExecutionStatus.SUCCESS

        # 确定结果等级
        outcome_level = self._determine_outcome_level(success, reward)

        # 确定反馈质量
        quality = self._determine_quality(outcome, metrics)

        # 生成洞察
        insights = self._generate_insights(metrics, reward)

        feedback = ExecutionFeedback(
            execution_id=outcome.execution_id,
            action_id=outcome.action_id,
            action_type=outcome.action_type,
            success=success,
            outcome_level=outcome_level,
            reward=reward,
            metrics=metrics,
            quality=quality,
            insights=insights,
            error=outcome.error,
        )

        self._feedback_history.append(feedback)
        return feedback

    def collect_batch(self, outcomes: list[ExecutionOutcome]) -> list[ExecutionFeedback]:
        """批量收集反馈."""
        return [self.collect(o) for o in outcomes]

    # ── 指标提取 ──────────────────────────────────────────

    def _extract_metrics(self, outcome: ExecutionOutcome) -> RewardMetrics:
        """从 ExecutionOutcome 提取指标."""
        output = outcome.output
        meta = outcome.metadata

        # 优先从 metadata 读取，其次从 output 读取
        metrics_delta = meta.get("metrics_delta", output.get("metrics_delta", {}))

        def _safe_float(value: Any, default: float = 0.0) -> float:
            """安全转换为 float，非数值类型返回默认值."""
            if isinstance(value, (int, float)):
                return float(value)
            return default

        return RewardMetrics(
            roas_delta=_safe_float(metrics_delta.get("roas_delta", output.get("roas_delta", 0.0))),
            cpi_delta=_safe_float(metrics_delta.get("cpi_delta", output.get("cpi_delta", 0.0))),
            ctr_delta=_safe_float(metrics_delta.get("ctr_delta", output.get("ctr_delta", 0.0))),
            cvr_delta=_safe_float(metrics_delta.get("cvr_delta", output.get("cvr_delta", 0.0))),
            retention_d3_delta=_safe_float(metrics_delta.get("retention_d3_delta", output.get("retention_d3_delta", 0.0))),
            retention_d7_delta=_safe_float(metrics_delta.get("retention_d7_delta", output.get("retention_d7_delta", 0.0))),
            payer_rate_delta=_safe_float(metrics_delta.get("payer_rate_delta", output.get("payer_rate_delta", 0.0))),
            ltv_d30_delta=_safe_float(metrics_delta.get("ltv_d30_delta", output.get("ltv_d30_delta", 0.0))),
        )

    # ── 结果评估 ──────────────────────────────────────────

    def _determine_outcome_level(self, success: bool, reward: float) -> ExperienceOutcomeLevel:
        """确定结果等级."""
        if not success:
            return ExperienceOutcomeLevel.FAILURE
        if reward >= 0.7:
            return ExperienceOutcomeLevel.STRONG_SUCCESS
        elif reward >= 0.5:
            return ExperienceOutcomeLevel.SUCCESS
        elif reward >= 0.3:
            return ExperienceOutcomeLevel.NEUTRAL
        else:
            return ExperienceOutcomeLevel.FAILURE

    def _determine_quality(self, outcome: ExecutionOutcome, metrics: RewardMetrics) -> FeedbackQuality:
        """确定反馈质量."""
        # 有完整指标数据 = 强信号
        has_metrics = any([
            metrics.roas_delta != 0.0,
            metrics.cpi_delta != 0.0,
            metrics.ctr_delta != 0.0,
            metrics.payer_rate_delta != 0.0,
        ])

        if outcome.metadata.get("reality_data", False):
            return FeedbackQuality.STRONG
        elif has_metrics:
            return FeedbackQuality.RELIABLE
        elif outcome.status == ExecutionStatus.SUCCESS:
            return FeedbackQuality.WEAK
        else:
            return FeedbackQuality.INCONCLUSIVE

    def _generate_insights(self, metrics: RewardMetrics, reward: float) -> list[str]:
        """生成洞察."""
        insights: list[str] = []

        if metrics.roas_delta > 0.1:
            insights.append(f"ROAS improved by {metrics.roas_delta:+.2f}")
        elif metrics.roas_delta < -0.1:
            insights.append(f"ROAS declined by {metrics.roas_delta:+.2f}")

        if metrics.payer_rate_delta > 0.01:
            insights.append(f"Payer rate increased by {metrics.payer_rate_delta:+.2%}")
        elif metrics.payer_rate_delta < -0.01:
            insights.append(f"Payer rate decreased by {metrics.payer_rate_delta:+.2%}")

        if metrics.cpi_delta < -0.05:
            insights.append(f"CPI improved by {metrics.cpi_delta:+.2f}")
        elif metrics.cpi_delta > 0.05:
            insights.append(f"CPI worsened by {metrics.cpi_delta:+.2f}")

        if metrics.retention_d7_delta > 0.02:
            insights.append(f"D7 retention improved by {metrics.retention_d7_delta:+.2%}")

        if reward >= 0.7:
            insights.append("High reward action — consider amplifying")
        elif reward < 0.3:
            insights.append("Low reward action — consider suppressing")

        if not insights:
            insights.append("No significant metric changes detected")

        return insights

    # ── 转化为 Experience ─────────────────────────────────

    def to_experience(
        self,
        feedback: ExecutionFeedback,
        context: ExperienceContext | None = None,
    ) -> GrowthExperience:
        """将 ExecutionFeedback 转化为 GrowthExperience.

        Args:
            feedback: 执行反馈
            context: 决策上下文 (可选)

        Returns:
            GrowthExperience: E13.4.1 增长经验
        """
        ctx = context or ExperienceContext(
            action_type=feedback.action_type,
            entity_id=feedback.action_id,
        )

        # 推断类别
        category = self._infer_category(feedback.action_type)

        return GrowthExperience(
            context=ctx,
            action_id=feedback.action_id,
            action_type=feedback.action_type,
            outcome=feedback.to_experience_outcome(),
            reward=feedback.reward,
            confidence=feedback.metadata.get("confidence", 0.5),
            category=category,
            tags=self._generate_tags(feedback),
            metadata={
                "feedback_id": feedback.feedback_id,
                "execution_id": feedback.execution_id,
                "quality": feedback.quality.value,
                "insights": feedback.insights,
            },
        )

    def to_experience_batch(
        self,
        feedbacks: list[ExecutionFeedback],
        context: ExperienceContext | None = None,
    ) -> list[GrowthExperience]:
        """批量转化."""
        return [self.to_experience(f, context) for f in feedbacks]

    # ── 存储 ──────────────────────────────────────────────

    def store(self, experience: GrowthExperience, store: Any) -> str:
        """将 GrowthExperience 存入 ExperienceStore.

        Args:
            experience: 增长经验
            store: ExperienceStore 实例

        Returns:
            str: experience_id
        """
        return store.store(experience)

    def store_batch(
        self,
        experiences: list[GrowthExperience],
        store: Any,
    ) -> list[str]:
        """批量存储."""
        return store.store_batch(experiences)

    # ── 便捷方法: 一步完成收集+存储 ──────────────────────

    def collect_and_store(
        self,
        outcome: ExecutionOutcome,
        context: ExperienceContext | None,
        store: Any,
    ) -> GrowthExperience:
        """收集反馈并存储经验.

        Args:
            outcome: 执行结果
            context: 决策上下文
            store: ExperienceStore 实例

        Returns:
            GrowthExperience: 已存储的经验
        """
        feedback = self.collect(outcome)
        experience = self.to_experience(feedback, context)
        self.store(experience, store)
        return experience

    def collect_and_store_batch(
        self,
        outcomes: list[ExecutionOutcome],
        context: ExperienceContext | None,
        store: Any,
    ) -> list[GrowthExperience]:
        """批量收集反馈并存储经验."""
        feedbacks = self.collect_batch(outcomes)
        experiences = self.to_experience_batch(feedbacks, context)
        self.store_batch(experiences, store)
        return experiences

    # ── 辅助 ──────────────────────────────────────────────

    def _infer_category(self, action_type: str) -> ExperienceCategory:
        """从动作类型推断经验类别."""
        creative_actions = {"create_creative", "mutate_creative", "create_variants"}
        ua_actions = {"promote_winner", "scale_campaign", "reduce_budget", "pause_campaign"}
        experiment_actions = {"start_experiment", "end_experiment"}

        if action_type in creative_actions:
            return ExperienceCategory.CREATIVE
        elif action_type in ua_actions:
            return ExperienceCategory.UA
        elif action_type in experiment_actions:
            return ExperienceCategory.CREATIVE
        elif action_type == "diversify_population":
            return ExperienceCategory.CREATIVE
        return ExperienceCategory.CREATIVE

    def _generate_tags(self, feedback: ExecutionFeedback) -> list[str]:
        """生成标签."""
        tags = [feedback.action_type]
        if feedback.success:
            tags.append("success")
        else:
            tags.append("failure")
        if feedback.reward >= 0.6:
            tags.append("high_reward")
        elif feedback.reward <= 0.3 or not feedback.success:
            tags.append("low_reward")
        tags.append(feedback.quality.value)
        return tags

    # ── 查询 ──────────────────────────────────────────────

    def get_feedback_history(self) -> list[ExecutionFeedback]:
        """获取反馈历史."""
        return list(self._feedback_history)

    def get_successful_feedbacks(self) -> list[ExecutionFeedback]:
        """获取成功反馈."""
        return [f for f in self._feedback_history if f.success]

    def get_failed_feedbacks(self) -> list[ExecutionFeedback]:
        """获取失败反馈."""
        return [f for f in self._feedback_history if not f.success]

    def stats(self) -> dict[str, Any]:
        """获取收集器统计."""
        total = len(self._feedback_history)
        success = sum(1 for f in self._feedback_history if f.success)
        failed = total - success
        avg_reward = round(sum(f.reward for f in self._feedback_history) / max(total, 1), 4)

        by_quality: dict[str, int] = {}
        for f in self._feedback_history:
            q = f.quality.value
            by_quality[q] = by_quality.get(q, 0) + 1

        return {
            "total_collected": self._collection_count,
            "total_feedbacks": total,
            "success": success,
            "failed": failed,
            "success_rate": round(success / max(total, 1), 4),
            "avg_reward": avg_reward,
            "by_quality": by_quality,
            "reward_calculations": self._reward_calculator.calculation_count,
        }

    def reset(self) -> None:
        """重置所有状态."""
        self._feedback_history.clear()
        self._collection_count = 0

    @property
    def reward_calculator(self) -> RewardCalculator:
        return self._reward_calculator


# ═══════════════════════════════════════════════════════════
# FeedbackPipeline
# ═══════════════════════════════════════════════════════════

class FeedbackPipeline:
    """反馈管道 — 完整的 ExecutionOutcome → GrowthExperience → Pattern 管道.

    将收集、转化、存储、挖掘整合为单一管道.

    用法:
        pipeline = FeedbackPipeline(experience_store, pattern_store)
        pipeline.feed(outcome, context)
        pipeline.feed_batch(outcomes, context)
    """

    def __init__(
        self,
        experience_store: Any,
        pattern_store: Any | None = None,
        collector: ExecutionFeedbackCollector | None = None,
    ):
        self._experience_store = experience_store
        self._pattern_store = pattern_store
        self._collector = collector or ExecutionFeedbackCollector()
        self._pipeline_count: int = 0

    def feed(
        self,
        outcome: ExecutionOutcome,
        context: ExperienceContext | None = None,
    ) -> GrowthExperience:
        """将执行结果输入管道.

        Outcome → Feedback → Experience → Store.

        Args:
            outcome: E14.7.2 执行结果
            context: 决策上下文

        Returns:
            GrowthExperience: 已存储的经验
        """
        self._pipeline_count += 1
        return self._collector.collect_and_store(outcome, context, self._experience_store)

    def feed_batch(
        self,
        outcomes: list[ExecutionOutcome],
        context: ExperienceContext | None = None,
    ) -> list[GrowthExperience]:
        """批量输入管道."""
        self._pipeline_count += len(outcomes)
        return self._collector.collect_and_store_batch(outcomes, context, self._experience_store)

    def mine_patterns(self, dimension: str = "opportunity_action") -> list[Any]:
        """从经验库挖掘模式.

        Args:
            dimension: 挖掘维度

        Returns:
            list[PatternMemory]: 挖掘出的模式
        """
        if self._pattern_store is None:
            return []

        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import PatternMiner
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternMiningDimension

        dim = PatternMiningDimension(dimension)
        miner = PatternMiner()
        patterns = miner.mine(self._experience_store, dimension=dim)
        self._pattern_store.store_batch(patterns)
        return patterns

    def stats(self) -> dict[str, Any]:
        """获取管道统计."""
        return {
            "pipeline_count": self._pipeline_count,
            "collector_stats": self._collector.stats(),
            "experience_store_count": getattr(self._experience_store, "count", 0),
            "pattern_store_count": getattr(self._pattern_store, "count", 0) if self._pattern_store else 0,
        }

    def reset(self) -> None:
        """重置管道."""
        self._collector.reset()
        self._pipeline_count = 0

    @property
    def collector(self) -> ExecutionFeedbackCollector:
        return self._collector


# ═══════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════

def create_feedback_collector(
    weights: dict[str, float] | None = None,
) -> ExecutionFeedbackCollector:
    """创建默认 ExecutionFeedbackCollector.

    Args:
        weights: 自定义奖励权重

    Returns:
        ExecutionFeedbackCollector: 配置好的反馈收集器
    """
    calculator = RewardCalculator(weights=weights) if weights else RewardCalculator()
    return ExecutionFeedbackCollector(reward_calculator=calculator)


def create_feedback_pipeline(
    experience_store: Any,
    pattern_store: Any | None = None,
    weights: dict[str, float] | None = None,
) -> FeedbackPipeline:
    """创建默认 FeedbackPipeline.

    Args:
        experience_store: ExperienceStore 实例
        pattern_store: PatternStore 实例 (可选)
        weights: 自定义奖励权重

    Returns:
        FeedbackPipeline: 配置好的反馈管道
    """
    collector = create_feedback_collector(weights=weights)
    return FeedbackPipeline(
        experience_store=experience_store,
        pattern_store=pattern_store,
        collector=collector,
    )