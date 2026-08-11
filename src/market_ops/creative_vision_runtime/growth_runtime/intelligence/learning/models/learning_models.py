"""E13.7.4 Decision Learning Loop — 核心数据模型.

Day 7.4 学习闭环模型:
  将 Decision → Execution → Outcome → Reward → Attribution → Memory 统一为
  单一学习事件，建立完整的 Observe → Decide → Execute → Measure → Learn → Optimize 闭环。

7 个核心模型:
  1. LearningOutcome       — 执行结果 (嵌套在 LearningExperience 中)
  2. LearningExperience    — 统一学习事件 (决策→执行→结果)
  3. RewardWeights         — 可配置的奖励权重
  4. LearningReward        — 统一奖励 (合并 RewardSignal + BridgeResult)
  5. AttributionEvidence   — 归因证据 (可追溯的数据来源)
  6. AttributionResult     — 归因分解 (Strategy/Creative/Audience/Timing)
  7. LearningResult        — 学习闭环输出 (学到什么×更新了什么×下一步)

与现有模块的关系:
  - 不修改 FeedbackLoop / ExecutionResultBridge / DecisionMemory / PatternStore
  - 提供 from_* 工厂方法从现有模型转换
  - LearningCoordinator 作为新入口，内部编排现有组件

设计原则:
  - reward 和 attribution 均为 Optional — 支持延迟归因 (T+7 数据成熟后计算)
  - RewardWeights 可配置 — 不同 Agent 使用不同权重
  - AttributionEvidence 可追溯 — 每个归因维度都有明确数据来源
  - LearningResult 轻量 — 不内嵌完整 Experience，通过 learning_id 引用
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ═══════════════════════════════════════════════════════════════
# 1. LearningOutcome
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearningOutcome:
    """执行结果 — 嵌套在 LearningExperience 中的业务结果.

    统一 ExecutionFeedback + BridgeResult 中的业务指标，
    记录执行前后的指标变化和执行质量。

    Attributes:
        success: 业务是否成功
        outcome_level: 结果等级 (strong_success/success/neutral/failure/strong_failure)
        metrics_before: 执行前业务指标 (ROAS, CTR, CVR, CPI 等)
        metrics_after: 执行后业务指标
        metrics_delta: 指标变化率 ((after - before) / before)
        improvement_score: 综合改善分数 [-1, 1]
        execution_success_rate: 执行成功率 [0, 1]
        execution_duration_ms: 执行耗时 (毫秒)
        failure_nodes: 失败节点数
        rollback_nodes: 回滚节点数
        was_blocked: 是否被安全拦截
        needed_approval: 是否需要审批
        learning_summary: 可读学习摘要
    """

    # ── 业务结果 ──
    success: bool = False
    outcome_level: str = "neutral"  # strong_success / success / neutral / failure / strong_failure
    metrics_before: dict[str, float] = field(default_factory=dict)
    metrics_after: dict[str, float] = field(default_factory=dict)
    metrics_delta: dict[str, float] = field(default_factory=dict)
    improvement_score: float = 0.0

    # ── 执行质量 ──
    execution_success_rate: float = 1.0
    execution_duration_ms: float = 0.0
    failure_nodes: int = 0
    rollback_nodes: int = 0
    was_blocked: bool = False
    needed_approval: bool = False

    # ── 摘要 ──
    learning_summary: str = ""

    @property
    def is_successful(self) -> bool:
        """业务结果是否正向."""
        return self.improvement_score > 0.05

    @property
    def is_significant(self) -> bool:
        """是否有显著改善 (>15%)."""
        return self.improvement_score > 0.15

    @property
    def is_degradation(self) -> bool:
        """是否有退化."""
        return self.improvement_score < -0.05

    @property
    def has_metrics(self) -> bool:
        """是否有完整业务指标."""
        return len(self.metrics_before) > 0 and len(self.metrics_after) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "outcome_level": self.outcome_level,
            "metrics_before": self.metrics_before,
            "metrics_after": self.metrics_after,
            "metrics_delta": {k: round(v, 4) for k, v in self.metrics_delta.items()},
            "improvement_score": round(self.improvement_score, 4),
            "execution_success_rate": round(self.execution_success_rate, 4),
            "execution_duration_ms": self.execution_duration_ms,
            "failure_nodes": self.failure_nodes,
            "rollback_nodes": self.rollback_nodes,
            "was_blocked": self.was_blocked,
            "needed_approval": self.needed_approval,
            "learning_summary": self.learning_summary,
            "is_successful": self.is_successful,
            "is_significant": self.is_significant,
            "is_degradation": self.is_degradation,
        }


# ═══════════════════════════════════════════════════════════════
# 2. LearningExperience
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearningExperience:
    """统一学习事件 — 一次决策→执行→结果的完整记录.

    设计原则:
      - reward 和 attribution 均为 Optional — 支持延迟计算
      - T+0: 执行完成 → outcome 可用
      - T+0: reward 可同步计算
      - T+7: attribution 可在数据成熟后补充

    Attributes:
        learning_id: 学习记录唯一标识
        decision_id: 关联的决策 ID
        execution_id: 关联的执行 ID
        opportunity_id: 触发机会 ID
        opportunity_type: 机会类型 (creative_fatigue / scale / budget / bid)
        strategy_id: 执行的策略 ID
        strategy_name: 策略名称
        action_type: 动作类型 (replace_creative / scale / bid_adjust / mutate)
        decision_type: 决策类型 (EXECUTE / TEST / HOLD / BLOCK / ESCALATE)
        context: 决策上下文 (product, platform, audience, market)
        outcome: 执行结果
        reward: 统一奖励 (Optional — 支持延迟计算)
        attribution: 归因分解 (Optional — T+7 数据成熟后补充)
        confidence: 决策置信度 [0, 1]
        risk_score: 决策风险 [0, 1]
        created_at: 学习记录创建时间
        tags: 可检索标签
        metadata: 扩展元数据
    """

    learning_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str = ""
    execution_id: str = ""
    opportunity_id: str = ""
    opportunity_type: str = ""
    strategy_id: str = ""
    strategy_name: str = ""
    action_type: str = ""
    decision_type: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    outcome: LearningOutcome = field(default_factory=LearningOutcome)
    reward: LearningReward | None = None          # Optional — 延迟计算
    attribution: AttributionResult | None = None  # Optional — T+7 补充
    confidence: float = 0.0
    risk_score: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_reward(self) -> bool:
        """是否已计算奖励."""
        return self.reward is not None

    @property
    def has_attribution(self) -> bool:
        """是否已完成归因."""
        return self.attribution is not None

    @property
    def is_learning_complete(self) -> bool:
        """学习是否完整 (reward + attribution 均已计算)."""
        return self.has_reward and self.has_attribution

    def to_dict(self) -> dict[str, Any]:
        return {
            "learning_id": self.learning_id,
            "decision_id": self.decision_id,
            "execution_id": self.execution_id,
            "opportunity_id": self.opportunity_id,
            "opportunity_type": self.opportunity_type,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "action_type": self.action_type,
            "decision_type": self.decision_type,
            "context": self.context,
            "outcome": self.outcome.to_dict(),
            "reward": self.reward.to_dict() if self.reward else None,
            "attribution": self.attribution.to_dict() if self.attribution else None,
            "confidence": round(self.confidence, 4),
            "risk_score": round(self.risk_score, 4),
            "created_at": self.created_at,
            "tags": self.tags,
            "has_reward": self.has_reward,
            "has_attribution": self.has_attribution,
            "is_learning_complete": self.is_learning_complete,
        }

    def __repr__(self) -> str:
        return (
            f"LearningExperience(id={self.learning_id[:8]}..., "
            f"decision={self.decision_id[:8]}..., "
            f"action={self.action_type}, "
            f"reward={'yes' if self.has_reward else 'no'}, "
            f"attr={'yes' if self.has_attribution else 'no'})"
        )


# ═══════════════════════════════════════════════════════════════
# 3. RewardWeights
# ═══════════════════════════════════════════════════════════════


@dataclass
class RewardWeights:
    """可配置的奖励权重 — 支持不同 Agent 使用不同权重.

    默认权重 (Growth Agent):
      business:   0.50  — 业务结果最重要
      execution:  0.20  — 执行质量
      safety:     0.20  — 安全合规
      efficiency: 0.10  — 执行效率

    UA Agent 建议:
      business:   0.70
      execution:  0.10
      safety:     0.15
      efficiency: 0.05

    Creative Agent 建议:
      business:    0.30
      execution:   0.20
      safety:      0.15
      efficiency:  0.05
      creative:    0.30  — 素材质量 (扩展维度)

    Attributes:
        business: 业务结果权重
        execution: 执行质量权重
        safety: 安全合规权重
        efficiency: 执行效率权重
        extra: 扩展维度权重 (如 creative_quality)
    """

    business: float = 0.50
    execution: float = 0.20
    safety: float = 0.20
    efficiency: float = 0.10
    extra: dict[str, float] = field(default_factory=dict)

    def validate(self) -> bool:
        """验证权重和是否为 1.0."""
        total = (
            self.business
            + self.execution
            + self.safety
            + self.efficiency
            + sum(self.extra.values())
        )
        return abs(total - 1.0) < 0.001

    @property
    def total_weight(self) -> float:
        return (
            self.business
            + self.execution
            + self.safety
            + self.efficiency
            + sum(self.extra.values())
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "business": self.business,
            "execution": self.execution,
            "safety": self.safety,
            "efficiency": self.efficiency,
            "extra": self.extra,
            "total": round(self.total_weight, 4),
            "valid": self.validate(),
        }

    @classmethod
    def default(cls) -> RewardWeights:
        """默认 Growth Agent 权重."""
        return cls()

    @classmethod
    def ua_agent(cls) -> RewardWeights:
        """UA Agent 权重 (业务导向)."""
        return cls(business=0.70, execution=0.10, safety=0.15, efficiency=0.05)

    @classmethod
    def creative_agent(cls) -> RewardWeights:
        """Creative Agent 权重 (素材质量导向)."""
        return cls(
            business=0.30, execution=0.20, safety=0.15, efficiency=0.05,
            extra={"creative_quality": 0.30},
        )

    @classmethod
    def conservative(cls) -> RewardWeights:
        """保守权重 (安全优先)."""
        return cls(business=0.30, execution=0.15, safety=0.45, efficiency=0.10)


# ═══════════════════════════════════════════════════════════════
# 4. LearningReward
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearningReward:
    """统一奖励 — 合并 RewardSignal + BridgeResult 的奖励标准.

    公式:
      total_reward = business_reward × weights.business
                   + execution_reward × weights.execution
                   + safety_reward × weights.safety
                   + efficiency_reward × weights.efficiency
                   + Σ extra_rewards × weights.extra

    Attributes:
        total_reward: 综合奖励 [-1, 1]
        business_reward: 业务结果奖励 (ROAS/CTR/CVR/CPI 变化)
        execution_reward: 执行质量奖励 (成功率)
        safety_reward: 安全合规奖励
        efficiency_reward: 执行效率奖励
        confidence: 奖励置信度 [0, 1]
        reward_level: 奖励等级 (positive / neutral / negative)
        weights: 使用的权重配置
        calculation_method: 计算方法 (unified / feedback_loop / bridge)
        source_rewards: 来源奖励引用 (用于追溯)
        components: 各维度详细分解
        created_at: 计算时间
    """

    total_reward: float = 0.0
    business_reward: float = 0.0
    execution_reward: float = 0.0
    safety_reward: float = 0.0
    efficiency_reward: float = 0.0
    confidence: float = 0.5
    reward_level: str = "neutral"  # positive / neutral / negative
    weights: RewardWeights = field(default_factory=RewardWeights)
    calculation_method: str = "unified"
    source_rewards: dict[str, Any] = field(default_factory=dict)
    components: dict[str, float] = field(default_factory=dict)
    extra_rewards: dict[str, float] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # ── 判断属性 ──

    @property
    def is_positive(self) -> bool:
        """正向学习."""
        return self.total_reward > 0.15

    @property
    def is_negative(self) -> bool:
        """负向学习."""
        return self.total_reward < -0.15

    @property
    def is_neutral(self) -> bool:
        """中性."""
        return -0.15 <= self.total_reward <= 0.15

    @property
    def is_strong_positive(self) -> bool:
        """强正向."""
        return self.total_reward > 0.5

    @property
    def is_strong_negative(self) -> bool:
        """强负向."""
        return self.total_reward < -0.5

    @property
    def is_high_confidence(self) -> bool:
        """高置信度."""
        return self.confidence >= 0.7

    # ── 工厂方法 ──

    @classmethod
    def from_business_metrics(
        cls,
        metrics_delta: dict[str, float],
        execution_success_rate: float = 1.0,
        execution_duration_ms: float = 0.0,
        was_blocked: bool = False,
        needed_approval: bool = False,
        weights: RewardWeights | None = None,
        confidence: float = 0.5,
    ) -> LearningReward:
        """从业务指标计算统一奖励.

        business_reward = tanh(roas_delta×5)×0.35 + tanh(ctr_delta×5)×0.25
                        + tanh(cvr_delta×5)×0.20 + tanh(-cpi_delta×5)×0.20

        Args:
            metrics_delta: 指标变化率 (roas_change, ctr_change, cvr_change, cpi_change)
            execution_success_rate: 执行成功率
            execution_duration_ms: 执行耗时
            was_blocked: 是否被拦截
            needed_approval: 是否需要审批
            weights: 权重配置 (默认使用标准权重)
            confidence: 奖励置信度

        Returns:
            LearningReward
        """
        w = weights or RewardWeights.default()

        # ── 业务奖励 ──
        business = 0.0
        business_count = 0
        business_components: dict[str, float] = {}

        roas_delta = metrics_delta.get("roas_change", 0.0)
        if roas_delta != 0.0:
            business += math.tanh(roas_delta * 5.0) * 0.35
            business_components["roas"] = round(math.tanh(roas_delta * 5.0), 4)
            business_count += 1

        ctr_delta = metrics_delta.get("ctr_change", 0.0)
        if ctr_delta != 0.0:
            business += math.tanh(ctr_delta * 5.0) * 0.25
            business_components["ctr"] = round(math.tanh(ctr_delta * 5.0), 4)
            business_count += 1

        cvr_delta = metrics_delta.get("cvr_change", 0.0)
        if cvr_delta != 0.0:
            business += math.tanh(cvr_delta * 5.0) * 0.20
            business_components["cvr"] = round(math.tanh(cvr_delta * 5.0), 4)
            business_count += 1

        cpi_delta = metrics_delta.get("cpi_change", 0.0)
        if cpi_delta != 0.0:
            business += math.tanh(-cpi_delta * 5.0) * 0.20
            business_components["cpi"] = round(math.tanh(-cpi_delta * 5.0), 4)
            business_count += 1

        if business_count == 0:
            business = 0.0
        business_reward = round(max(-1.0, min(1.0, business)), 4)

        # ── 执行奖励 ──
        execution_reward = round(2.0 * execution_success_rate - 1.0, 4)

        # ── 安全奖励 ──
        if was_blocked:
            safety_reward = -1.0
        elif needed_approval:
            safety_reward = -0.5
        else:
            safety_reward = 1.0

        # ── 效率奖励 ──
        if execution_duration_ms <= 0:
            efficiency_reward = 0.0
        else:
            speed_score = 1.0 / (1.0 + math.exp((execution_duration_ms - 5000) / 10000))
            efficiency_reward = round(2.0 * speed_score - 1.0, 4)

        # ── 加权总奖励 ──
        extra_reward = sum(
            w.extra.get(k, 0.0) * 0.0  # 扩展维度默认为 0
            for k in w.extra
        )
        total = (
            business_reward * w.business
            + execution_reward * w.execution
            + safety_reward * w.safety
            + efficiency_reward * w.efficiency
            + extra_reward
        )
        total_reward = round(max(-1.0, min(1.0, total)), 4)

        # ── 等级判定 ──
        if total_reward > 0.15:
            level = "positive"
        elif total_reward < -0.15:
            level = "negative"
        else:
            level = "neutral"

        return cls(
            total_reward=total_reward,
            business_reward=business_reward,
            execution_reward=execution_reward,
            safety_reward=safety_reward,
            efficiency_reward=efficiency_reward,
            confidence=confidence,
            reward_level=level,
            weights=w,
            calculation_method="unified",
            components={
                **business_components,
                "execution_raw": execution_reward,
                "safety_raw": safety_reward,
                "efficiency_raw": efficiency_reward,
            },
            extra_rewards={},
        )

    @classmethod
    def from_reward_signal(
        cls,
        signal: Any,  # RewardSignal
        weights: RewardWeights | None = None,
    ) -> LearningReward:
        """从现有 RewardSignal 转换.

        Args:
            signal: feedback.models.RewardSignal 实例
            weights: 权重配置

        Returns:
            LearningReward
        """
        w = weights or RewardWeights.default()
        total = (
            signal.outcome_reward * w.business
            + signal.execution_reward * w.execution
            + signal.safety_reward * w.safety
            + signal.efficiency_reward * w.efficiency
        )
        total_reward = round(max(-1.0, min(1.0, total)), 4)

        level = "neutral"
        if total_reward > 0.15:
            level = "positive"
        elif total_reward < -0.15:
            level = "negative"

        return cls(
            total_reward=total_reward,
            business_reward=round(signal.outcome_reward, 4),
            execution_reward=round(signal.execution_reward, 4),
            safety_reward=round(signal.safety_reward, 4),
            efficiency_reward=round(signal.efficiency_reward, 4),
            confidence=round(signal.confidence, 4),
            reward_level=level,
            weights=w,
            calculation_method="feedback_loop",
            source_rewards={"reward_id": signal.reward_id, "source": "RewardSignal"},
            components=dict(signal.components) if signal.components else {},
        )

    @classmethod
    def from_bridge_result(
        cls,
        result: Any,  # BridgeResult
        weights: RewardWeights | None = None,
    ) -> LearningReward:
        """从现有 BridgeResult 转换.

        Args:
            result: execution_result_bridge.BridgeResult 实例
            weights: 权重配置

        Returns:
            LearningReward
        """
        w = weights or RewardWeights.default()
        business_reward = round(2.0 * result.reward - 1.0, 4)  # [0,1] → [-1,1]
        execution_reward = 0.0  # BridgeResult 没有分离执行质量
        safety_reward = 0.0
        efficiency_reward = 0.0

        total = (
            business_reward * w.business
            + execution_reward * w.execution
            + safety_reward * w.safety
            + efficiency_reward * w.efficiency
        )
        total_reward = round(max(-1.0, min(1.0, total)), 4)

        level = "neutral"
        if total_reward > 0.15:
            level = "positive"
        elif total_reward < -0.15:
            level = "negative"

        return cls(
            total_reward=total_reward,
            business_reward=business_reward,
            execution_reward=execution_reward,
            safety_reward=safety_reward,
            efficiency_reward=efficiency_reward,
            confidence=0.5,
            reward_level=level,
            weights=w,
            calculation_method="bridge",
            source_rewards={
                "bridge_id": result.bridge_id,
                "improvement_score": result.improvement_score,
                "source": "BridgeResult",
            },
            components={
                "improvement_score": round(result.improvement_score, 4),
                "metrics_delta": {k: round(v, 4) for k, v in result.metrics_delta.items()},
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_reward": round(self.total_reward, 4),
            "business_reward": round(self.business_reward, 4),
            "execution_reward": round(self.execution_reward, 4),
            "safety_reward": round(self.safety_reward, 4),
            "efficiency_reward": round(self.efficiency_reward, 4),
            "confidence": round(self.confidence, 4),
            "reward_level": self.reward_level,
            "weights": self.weights.to_dict(),
            "calculation_method": self.calculation_method,
            "source_rewards": self.source_rewards,
            "components": {k: round(v, 4) for k, v in self.components.items()},
            "extra_rewards": {k: round(v, 4) for k, v in self.extra_rewards.items()},
            "is_positive": self.is_positive,
            "is_negative": self.is_negative,
            "is_neutral": self.is_neutral,
            "is_strong_positive": self.is_strong_positive,
            "is_strong_negative": self.is_strong_negative,
            "is_high_confidence": self.is_high_confidence,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"LearningReward(total={self.total_reward:+.2f}, "
            f"level={self.reward_level}, "
            f"business={self.business_reward:+.2f}, "
            f"conf={self.confidence:.2f})"
        )


# ═══════════════════════════════════════════════════════════════
# 5. AttributionEvidence
# ═══════════════════════════════════════════════════════════════


@dataclass
class AttributionEvidence:
    """归因证据 — 可追溯的数据来源.

    设计原则:
      增长系统必须可解释。每个归因维度都有明确的数据来源、
      窗口期和置信度，确保可以回答"为什么认为素材贡献 60%？"

    例如:
      AttributionEvidence(
        metric_source="adjust",
        source_ids=["campaign_123", "adset_456"],
        data_window="2026-07-01~2026-07-07",
        confidence=0.82,
        description="CTR 从 1.8% 提升到 3.1%，来源 Adjust + Meta，7天窗口",
      )

    Attributes:
        metric_source: 指标来源 (adjust / meta_ads / google_play / max)
        source_ids: 来源标识列表 (campaign_id, adset_id, creative_id)
        data_window: 数据窗口 (如 "2026-07-01~2026-07-07")
        confidence: 证据置信度 [0, 1]
        description: 可读描述
        raw_data: 原始数据引用
    """

    metric_source: str = ""  # adjust / meta_ads / google_play / max
    source_ids: list[str] = field(default_factory=list)
    data_window: str = ""  # "2026-07-01~2026-07-07"
    confidence: float = 0.5
    description: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_source": self.metric_source,
            "source_ids": self.source_ids,
            "data_window": self.data_window,
            "confidence": round(self.confidence, 4),
            "description": self.description,
            "raw_data": self.raw_data,
        }

    def __repr__(self) -> str:
        return (
            f"AttributionEvidence(source={self.metric_source}, "
            f"ids={len(self.source_ids)}, "
            f"window={self.data_window}, "
            f"conf={self.confidence:.2f})"
        )


# ═══════════════════════════════════════════════════════════════
# 6. AttributionResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class AttributionResult:
    """归因分解 — 将 reward 分解为 Strategy/Creative/Audience/Timing 贡献.

    核心公式:
      total_reward ≈ strategy_contribution + creative_contribution
                    + audience_contribution + timing_contribution
                    + unexplained

    启发式归因规则 (Phase 1):
      - strategy_contribution:  策略置信度 × 历史成功率
      - creative_contribution:  CTR 变化 × 0.6 + CVR 变化 × 0.4
      - audience_contribution:  受众匹配度 × 历史受众表现
      - timing_contribution:    市场窗口评分 × 时间因子
      - unexplained:            残差 (无法归因到以上四维)

    Attributes:
        attribution_id: 归因唯一标识
        decision_id: 关联的决策 ID
        total_reward: 被分解的总 reward
        strategy_contribution: 策略贡献 (选对策略)
        creative_contribution: 素材贡献 (创意质量)
        audience_contribution: 受众贡献 (定向准确)
        timing_contribution: 时机贡献 (市场窗口)
        unexplained: 未解释残差
        primary_factor: 主要成功/失败因素
        confidence: 归因置信度 [0, 1]
        attribution_method: 归因方法 (heuristic / causal / shapley)
        evidence: 归因证据列表
        created_at: 归因时间
    """

    attribution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str = ""
    total_reward: float = 0.0
    strategy_contribution: float = 0.0
    creative_contribution: float = 0.0
    audience_contribution: float = 0.0
    timing_contribution: float = 0.0
    unexplained: float = 0.0
    primary_factor: str = ""  # strategy / creative / audience / timing / unexplained
    confidence: float = 0.5
    attribution_method: str = "heuristic"
    evidence: list[AttributionEvidence] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # ── 判断属性 ──

    @property
    def is_creative_driven(self) -> bool:
        """素材驱动."""
        return self.creative_contribution > 0.3

    @property
    def is_strategy_driven(self) -> bool:
        """策略驱动."""
        return self.strategy_contribution > 0.3

    @property
    def is_audience_driven(self) -> bool:
        """受众驱动."""
        return self.audience_contribution > 0.3

    @property
    def is_timing_driven(self) -> bool:
        """时机驱动."""
        return self.timing_contribution > 0.3

    @property
    def contribution_sum(self) -> float:
        """贡献总和."""
        return (
            self.strategy_contribution
            + self.creative_contribution
            + self.audience_contribution
            + self.timing_contribution
        )

    @property
    def residual(self) -> float:
        """残差 (total_reward - contribution_sum)."""
        return round(self.total_reward - self.contribution_sum, 4)

    # ── 工厂方法 ──

    @classmethod
    def from_heuristic(
        cls,
        decision_id: str,
        total_reward: float,
        metrics_delta: dict[str, float],
        strategy_confidence: float = 0.5,
        strategy_success_rate: float = 0.5,
        audience_match: float = 0.5,
        timing_factor: float = 0.0,
        evidence: list[AttributionEvidence] | None = None,
    ) -> AttributionResult:
        """从启发式规则创建归因结果.

        Args:
            decision_id: 决策 ID
            total_reward: 总奖励
            metrics_delta: 指标变化 (ctr_change, cvr_change)
            strategy_confidence: 策略置信度
            strategy_success_rate: 策略历史成功率
            audience_match: 受众匹配度
            timing_factor: 时机因子 (市场窗口评分)
            evidence: 归因证据

        Returns:
            AttributionResult
        """
        # 策略贡献: 策略置信度 × 历史成功率
        strategy_contrib = round(
            strategy_confidence * strategy_success_rate * total_reward, 4
        )

        # 素材贡献: CTR 变化 × 0.6 + CVR 变化 × 0.4
        ctr_change = metrics_delta.get("ctr_change", 0.0)
        cvr_change = metrics_delta.get("cvr_change", 0.0)
        creative_contrib = round(
            math.tanh(ctr_change * 5.0) * 0.6 + math.tanh(cvr_change * 5.0) * 0.4, 4
        )
        # 素材贡献不超过 total_reward
        creative_contrib = round(
            max(-abs(total_reward), min(abs(total_reward), creative_contrib)), 4
        )

        # 受众贡献: 受众匹配度 × 剩余 reward
        remaining = total_reward - strategy_contrib - creative_contrib
        audience_contrib = round(audience_match * remaining * 0.6, 4)

        # 时机贡献: 时间因子 × 剩余 reward
        timing_contrib = round(timing_factor * remaining * 0.4, 4)

        # 残差
        unexplained = round(
            total_reward
            - strategy_contrib
            - creative_contrib
            - audience_contrib
            - timing_contrib,
            4,
        )

        # 主因判定
        contributions = {
            "strategy": strategy_contrib,
            "creative": creative_contrib,
            "audience": audience_contrib,
            "timing": timing_contrib,
        }
        primary = max(contributions, key=lambda k: abs(contributions[k]))
        if abs(contributions[primary]) < 0.05:
            primary = "unexplained"

        return cls(
            decision_id=decision_id,
            total_reward=total_reward,
            strategy_contribution=strategy_contrib,
            creative_contribution=creative_contrib,
            audience_contribution=audience_contrib,
            timing_contribution=timing_contrib,
            unexplained=unexplained,
            primary_factor=primary,
            confidence=0.5,
            attribution_method="heuristic",
            evidence=evidence or [],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "attribution_id": self.attribution_id,
            "decision_id": self.decision_id,
            "total_reward": round(self.total_reward, 4),
            "strategy_contribution": round(self.strategy_contribution, 4),
            "creative_contribution": round(self.creative_contribution, 4),
            "audience_contribution": round(self.audience_contribution, 4),
            "timing_contribution": round(self.timing_contribution, 4),
            "unexplained": round(self.unexplained, 4),
            "primary_factor": self.primary_factor,
            "confidence": round(self.confidence, 4),
            "attribution_method": self.attribution_method,
            "evidence": [e.to_dict() for e in self.evidence],
            "is_creative_driven": self.is_creative_driven,
            "is_strategy_driven": self.is_strategy_driven,
            "is_audience_driven": self.is_audience_driven,
            "is_timing_driven": self.is_timing_driven,
            "contribution_sum": round(self.contribution_sum, 4),
            "residual": self.residual,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"AttributionResult(primary={self.primary_factor}, "
            f"creative={self.creative_contribution:+.2f}, "
            f"strategy={self.strategy_contribution:+.2f}, "
            f"audience={self.audience_contribution:+.2f}, "
            f"timing={self.timing_contribution:+.2f})"
        )


# ═══════════════════════════════════════════════════════════════
# 7. LearningResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearningResult:
    """学习闭环输出 — 一次学习周期的完整结果.

    设计原则:
      - 轻量: 不内嵌完整 LearningExperience，通过 learning_id 引用
      - 可操作: lessons + recommendations 直接指导下一步动作
      - 可度量: learning_quality 量化本次学习效果

    Attributes:
        learning_id: 关联的 LearningExperience ID
        decision_id: 关联的决策 ID
        memory_updated: 是否更新 DecisionMemory
        experience_stored: 是否写入 ExperienceStore
        pattern_updated: 是否更新 PatternStore
        evolution_triggered: 是否触发 MemoryEvolution
        consolidation_triggered: 是否触发 MemoryConsolidation
        lessons: 经验教训 (可读)
        recommendations: 改进建议 (可读)
        next_action: 下一步动作 (reinforce / adjust / abandon / observe)
        pattern_impact: 对 Pattern 的影响描述
        learning_quality: 本次学习质量评分 [0, 1]
        cycle_duration_ms: 学习周期耗时
        created_at: 学习时间
        metadata: 扩展数据
    """

    learning_id: str = ""
    decision_id: str = ""
    memory_updated: bool = False
    experience_stored: bool = False
    pattern_updated: bool = False
    evolution_triggered: bool = False
    consolidation_triggered: bool = False
    lessons: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    next_action: str = "observe"  # reinforce / adjust / abandon / observe
    pattern_impact: dict[str, Any] = field(default_factory=dict)
    learning_quality: float = 0.0
    cycle_duration_ms: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── 判断属性 ──

    @property
    def is_successful_loop(self) -> bool:
        """学习闭环是否成功 (至少更新了 Memory)."""
        return self.memory_updated

    @property
    def should_reinforce(self) -> bool:
        """是否应该强化该策略."""
        return self.next_action == "reinforce"

    @property
    def should_adjust(self) -> bool:
        """是否应该调整策略."""
        return self.next_action == "adjust"

    @property
    def should_abandon(self) -> bool:
        """是否应该放弃策略."""
        return self.next_action == "abandon"

    @property
    def is_high_quality(self) -> bool:
        """学习质量是否高."""
        return self.learning_quality >= 0.7

    # ── 工厂方法 ──

    @classmethod
    def from_learning_experience(
        cls,
        experience: LearningExperience,
        memory_updated: bool = False,
        experience_stored: bool = False,
        pattern_updated: bool = False,
        evolution_triggered: bool = False,
        consolidation_triggered: bool = False,
        cycle_duration_ms: float = 0.0,
    ) -> LearningResult:
        """从 LearningExperience 创建 LearningResult.

        根据 reward 自动判定 next_action 和计算 learning_quality。

        Args:
            experience: 学习经验
            memory_updated: 是否更新 DecisionMemory
            experience_stored: 是否写入 ExperienceStore
            pattern_updated: 是否更新 PatternStore
            evolution_triggered: 是否触发 MemoryEvolution
            consolidation_triggered: 是否触发 MemoryConsolidation
            cycle_duration_ms: 学习周期耗时

        Returns:
            LearningResult
        """
        # ── next_action 判定 ──
        if experience.has_reward:
            reward = experience.reward.total_reward  # type: ignore[union-attr]
            if reward > 0.5:
                next_action = "reinforce"
            elif reward > 0.15:
                next_action = "adjust"
            elif reward >= -0.15:
                next_action = "observe"
            elif reward >= -0.5:
                next_action = "adjust"
            else:
                next_action = "abandon"
        else:
            next_action = "observe"

        # ── lessons ──
        lessons: list[str] = []
        if experience.outcome.is_successful:
            lessons.append(
                f"Strategy '{experience.strategy_name}' was effective: "
                f"improvement {experience.outcome.improvement_score:+.1%}"
            )
        elif experience.outcome.is_degradation:
            lessons.append(
                f"Strategy '{experience.strategy_name}' caused degradation: "
                f"{experience.outcome.improvement_score:+.1%}"
            )

        if experience.has_attribution:
            attr = experience.attribution  # type: ignore[union-attr]
            lessons.append(
                f"Primary factor: {attr.primary_factor} "
                f"(creative={attr.creative_contribution:+.2f}, "
                f"strategy={attr.strategy_contribution:+.2f})"
            )

        if experience.outcome.was_blocked:
            lessons.append("Decision was blocked by safety layer")
        if experience.outcome.rollback_nodes > 0:
            lessons.append(f"Rollback occurred: {experience.outcome.rollback_nodes} nodes")

        # ── recommendations ──
        recommendations: list[str] = []
        if next_action == "reinforce":
            recommendations.append(
                f"Reinforce strategy '{experience.strategy_name}' — "
                f"increase budget allocation"
            )
        elif next_action == "adjust":
            if experience.outcome.is_successful:
                recommendations.append(
                    f"Adjust strategy '{experience.strategy_name}' — "
                    f"minor optimization before scaling"
                )
            else:
                recommendations.append(
                    f"Adjust strategy '{experience.strategy_name}' — "
                    f"modify parameters before retry"
                )
        elif next_action == "abandon":
            recommendations.append(
                f"Abandon strategy '{experience.strategy_name}' — "
                f"negative reward {experience.reward.total_reward if experience.has_reward else 'N/A'}"
            )

        if experience.has_attribution and experience.attribution.is_creative_driven:  # type: ignore[union-attr]
            recommendations.append(
                "Creative is the primary driver — consider expanding creative variants"
            )
        if experience.has_attribution and experience.attribution.is_audience_driven:  # type: ignore[union-attr]
            recommendations.append(
                "Audience is the primary driver — consider refining targeting"
            )

        # ── learning_quality ──
        quality = cls._compute_learning_quality(experience)

        # ── pattern_impact ──
        pattern_impact: dict[str, Any] = {}
        if experience.has_reward and experience.has_attribution:
            pattern_impact = {
                "impact_type": "reinforce" if experience.reward.is_positive else "weaken",  # type: ignore[union-attr]
                "primary_factor": experience.attribution.primary_factor,  # type: ignore[union-attr]
                "evidence_summary": f"Reward {experience.reward.total_reward:+.2f}, "  # type: ignore[union-attr]
                f"driven by {experience.attribution.primary_factor}",  # type: ignore[union-attr]
            }

        return cls(
            learning_id=experience.learning_id,
            decision_id=experience.decision_id,
            memory_updated=memory_updated,
            experience_stored=experience_stored,
            pattern_updated=pattern_updated,
            evolution_triggered=evolution_triggered,
            consolidation_triggered=consolidation_triggered,
            lessons=lessons,
            recommendations=recommendations,
            next_action=next_action,
            pattern_impact=pattern_impact,
            learning_quality=quality,
            cycle_duration_ms=cycle_duration_ms,
        )

    @staticmethod
    def _compute_learning_quality(experience: LearningExperience) -> float:
        """计算学习质量.

        learning_quality = confidence × 0.4
                         + (1 - |unexplained|) × 0.3
                         + sample_completeness × 0.3

        Args:
            experience: 学习经验

        Returns:
            float: 学习质量 [0, 1]
        """
        # 置信度
        confidence = 0.5
        if experience.has_reward:
            confidence = experience.reward.confidence  # type: ignore[union-attr]

        # 未解释残差
        unexplained = 0.5
        if experience.has_attribution:
            unexplained = abs(experience.attribution.unexplained)  # type: ignore[union-attr]

        # 样本完整性
        sample_completeness = 0.0
        if experience.outcome.has_metrics:
            sample_completeness = 1.0
        elif experience.outcome.metrics_before or experience.outcome.metrics_after:
            sample_completeness = 0.5

        quality = (
            confidence * 0.4
            + (1.0 - unexplained) * 0.3
            + sample_completeness * 0.3
        )
        return round(max(0.0, min(1.0, quality)), 4)

    # ── 工厂方法: 从现有 FeedbackResult 转换 ──

    @classmethod
    def from_feedback_result(
        cls,
        feedback_result: Any,  # FeedbackResult
        learning_id: str = "",
        decision_id: str = "",
    ) -> LearningResult:
        """从现有 FeedbackResult 转换.

        Args:
            feedback_result: feedback.models.FeedbackResult 实例
            learning_id: 学习记录 ID
            decision_id: 决策 ID

        Returns:
            LearningResult
        """
        # next_action 映射
        action_map = {
            "reinforce": "reinforce",
            "adjust": "adjust",
            "abandon": "abandon",
            "observe": "observe",
        }
        next_action = action_map.get(feedback_result.next_action, "observe")

        return cls(
            learning_id=learning_id,
            decision_id=decision_id or feedback_result.decision_id,
            memory_updated=feedback_result.memory_updated,
            experience_stored=feedback_result.experience_stored,
            evolution_triggered=feedback_result.evolution_triggered,
            lessons=list(feedback_result.lessons),
            recommendations=list(feedback_result.recommendations),
            next_action=next_action,
            learning_quality=0.5,
            metadata={"source": "FeedbackResult", "feedback_id": feedback_result.feedback_id},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "learning_id": self.learning_id,
            "decision_id": self.decision_id,
            "memory_updated": self.memory_updated,
            "experience_stored": self.experience_stored,
            "pattern_updated": self.pattern_updated,
            "evolution_triggered": self.evolution_triggered,
            "consolidation_triggered": self.consolidation_triggered,
            "lessons": self.lessons,
            "recommendations": self.recommendations,
            "next_action": self.next_action,
            "pattern_impact": self.pattern_impact,
            "learning_quality": round(self.learning_quality, 4),
            "cycle_duration_ms": self.cycle_duration_ms,
            "is_successful_loop": self.is_successful_loop,
            "is_high_quality": self.is_high_quality,
            "should_reinforce": self.should_reinforce,
            "should_adjust": self.should_adjust,
            "should_abandon": self.should_abandon,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"LearningResult(id={self.learning_id[:8]}..., "
            f"action={self.next_action}, "
            f"quality={self.learning_quality:.2f}, "
            f"lessons={len(self.lessons)})"
        )


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_learning_experience(
    decision_id: str,
    execution_id: str = "",
    opportunity_id: str = "",
    opportunity_type: str = "",
    strategy_id: str = "",
    strategy_name: str = "",
    action_type: str = "",
    decision_type: str = "",
    context: dict[str, Any] | None = None,
    metrics_before: dict[str, float] | None = None,
    metrics_after: dict[str, float] | None = None,
    improvement_score: float = 0.0,
    success: bool = False,
    execution_success_rate: float = 1.0,
    execution_duration_ms: float = 0.0,
    confidence: float = 0.5,
    risk_score: float = 0.0,
    tags: list[str] | None = None,
) -> LearningExperience:
    """快速创建 LearningExperience 的工厂函数.

    Args:
        decision_id: 决策 ID
        execution_id: 执行 ID
        opportunity_id: 机会 ID
        opportunity_type: 机会类型
        strategy_id: 策略 ID
        strategy_name: 策略名称
        action_type: 动作类型
        decision_type: 决策类型
        context: 决策上下文
        metrics_before: 执行前指标
        metrics_after: 执行后指标
        improvement_score: 改善分数
        success: 是否成功
        execution_success_rate: 执行成功率
        execution_duration_ms: 执行耗时
        confidence: 决策置信度
        risk_score: 决策风险
        tags: 标签

    Returns:
        LearningExperience
    """
    # 计算 metrics_delta
    metrics_delta: dict[str, float] = {}
    before = metrics_before or {}
    after = metrics_after or {}
    all_metrics = set(before.keys()) | set(after.keys())
    for metric in all_metrics:
        b = before.get(metric, 0.0)
        a = after.get(metric, 0.0)
        if b != 0.0:
            metrics_delta[metric] = (a - b) / abs(b)
        elif a != 0.0:
            metrics_delta[metric] = 1.0

    # 判定 outcome_level
    if improvement_score > 0.30:
        outcome_level = "strong_success"
    elif improvement_score > 0.05:
        outcome_level = "success"
    elif improvement_score < -0.30:
        outcome_level = "strong_failure"
    elif improvement_score < -0.05:
        outcome_level = "failure"
    else:
        outcome_level = "neutral"

    outcome = LearningOutcome(
        success=success,
        outcome_level=outcome_level,
        metrics_before=before,
        metrics_after=after,
        metrics_delta=metrics_delta,
        improvement_score=improvement_score,
        execution_success_rate=execution_success_rate,
        execution_duration_ms=execution_duration_ms,
    )

    return LearningExperience(
        decision_id=decision_id,
        execution_id=execution_id,
        opportunity_id=opportunity_id,
        opportunity_type=opportunity_type,
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        action_type=action_type,
        decision_type=decision_type,
        context=context or {},
        outcome=outcome,
        confidence=confidence,
        risk_score=risk_score,
        tags=tags or [],
    )


# ═══════════════════════════════════════════════════════════════
# Day 7.5 — Adaptive Learning Intelligence Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearnedPattern:
    """从历史经验中提取的学习模式.

    Attributes:
        pattern_id: 模式唯一标识
        dimension: 模式维度 (creative/strategy/audience/timing)
        condition: 触发条件描述
        impact: 影响方向 (positive/negative/neutral)
        avg_reward: 平均奖励
        sample_count: 样本数
        confidence: 置信度 [0, 1]
        success_rate: 成功率
        source_experience_ids: 来源经验 ID 列表
        created_at: 创建时间
        metadata: 扩展元数据
    """

    pattern_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    dimension: str = ""  # creative / strategy / audience / timing
    condition: str = ""  # 触发条件描述 (如 "fantasy_character")
    impact: str = "neutral"  # positive / negative / neutral
    avg_reward: float = 0.0
    sample_count: int = 0
    confidence: float = 0.0
    success_rate: float = 0.0
    source_experience_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_strong(self) -> bool:
        return self.confidence >= 0.7 and self.sample_count >= 10

    @property
    def is_reliable(self) -> bool:
        return self.confidence >= 0.5 and self.sample_count >= 5

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "dimension": self.dimension,
            "condition": self.condition,
            "impact": self.impact,
            "avg_reward": round(self.avg_reward, 4),
            "sample_count": self.sample_count,
            "confidence": round(self.confidence, 4),
            "success_rate": round(self.success_rate, 4),
            "source_experience_ids": self.source_experience_ids,
            "is_strong": self.is_strong,
            "is_reliable": self.is_reliable,
            "created_at": self.created_at,
        }


@dataclass
class StrategyInsight:
    """策略洞察 — 从历史学习中提取的策略级知识.

    Attributes:
        insight_id: 洞察唯一标识
        strategy_name: 策略名称
        action_type: 动作类型
        avg_effectiveness: 平均有效性
        success_count: 成功次数
        total_count: 总次数
        best_context: 最佳适用上下文
        warnings: 风险提示
        confidence: 置信度 [0, 1]
        created_at: 创建时间
    """

    insight_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_name: str = ""
    action_type: str = ""
    avg_effectiveness: float = 0.0
    success_count: int = 0
    total_count: int = 0
    best_context: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    confidence: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def success_rate(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.success_count / self.total_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "strategy_name": self.strategy_name,
            "action_type": self.action_type,
            "avg_effectiveness": round(self.avg_effectiveness, 4),
            "success_count": self.success_count,
            "total_count": self.total_count,
            "success_rate": round(self.success_rate, 4),
            "best_context": self.best_context,
            "warnings": self.warnings,
            "confidence": round(self.confidence, 4),
            "created_at": self.created_at,
        }


@dataclass
class RiskSignal:
    """风险信号 — 从历史学习中识别的风险模式.

    Attributes:
        signal_id: 信号唯一标识
        signal_type: 信号类型 (creative_fatigue/audience_saturation/budget_inefficiency/strategy_decay)
        risk_level: 风险等级 (low/medium/high/critical)
        condition: 触发条件
        frequency: 出现频率
        avg_impact: 平均影响
        last_seen_at: 最近出现时间
        confidence: 置信度 [0, 1]
        recommendations: 建议措施
        created_at: 创建时间
    """

    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    signal_type: str = ""  # creative_fatigue / audience_saturation / budget_inefficiency / strategy_decay
    risk_level: str = "low"  # low / medium / high / critical
    condition: str = ""
    frequency: float = 0.0
    avg_impact: float = 0.0
    last_seen_at: str = ""
    confidence: float = 0.0
    recommendations: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type,
            "risk_level": self.risk_level,
            "condition": self.condition,
            "frequency": round(self.frequency, 4),
            "avg_impact": round(self.avg_impact, 4),
            "last_seen_at": self.last_seen_at,
            "confidence": round(self.confidence, 4),
            "recommendations": self.recommendations,
            "created_at": self.created_at,
        }


@dataclass
class LearningKnowledge:
    """学习知识 — 从历史经验中提取的结构化知识.

    聚合输出:
      - patterns: 发现的行为模式
      - strategies: 策略洞察
      - warnings: 风险信号
      - confidence: 整体知识置信度

    Attributes:
        knowledge_id: 知识唯一标识
        patterns: 发现的行为模式列表
        strategies: 策略洞察列表
        warnings: 风险信号列表
        confidence: 整体知识置信度 [0, 1]
        total_experiences: 分析的总经验数
        extraction_method: 提取方法 (statistical / causal / hybrid)
        created_at: 创建时间
        metadata: 扩展元数据
    """

    knowledge_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    patterns: list[LearnedPattern] = field(default_factory=list)
    strategies: list[StrategyInsight] = field(default_factory=list)
    warnings: list[RiskSignal] = field(default_factory=list)
    confidence: float = 0.0
    total_experiences: int = 0
    extraction_method: str = "statistical"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def pattern_count(self) -> int:
        return len(self.patterns)

    @property
    def strategy_count(self) -> int:
        return len(self.strategies)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def has_strong_patterns(self) -> bool:
        return any(p.is_strong for p in self.patterns)

    @property
    def has_critical_risks(self) -> bool:
        return any(w.risk_level == "critical" for w in self.warnings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "patterns": [p.to_dict() for p in self.patterns],
            "strategies": [s.to_dict() for s in self.strategies],
            "warnings": [w.to_dict() for w in self.warnings],
            "confidence": round(self.confidence, 4),
            "total_experiences": self.total_experiences,
            "extraction_method": self.extraction_method,
            "pattern_count": self.pattern_count,
            "strategy_count": self.strategy_count,
            "warning_count": self.warning_count,
            "has_strong_patterns": self.has_strong_patterns,
            "has_critical_risks": self.has_critical_risks,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# Day 7.5.2 — PatternPrediction
# ═══════════════════════════════════════════════════════════════


@dataclass
class PatternPrediction:
    """模式预测 — 给定上下文预测最佳模式.

    Attributes:
        prediction_id: 预测唯一标识
        recommended_pattern: 推荐模式描述
        expected_roas: 预期ROAS
        expected_success_rate: 预期成功率
        confidence: 预测置信度 [0, 1]
        matched_patterns: 匹配到的模式列表
        context_match_score: 上下文匹配度 [0, 1]
        risk_level: 预测风险等级
        recommendations: 执行建议
        created_at: 创建时间
        metadata: 扩展元数据
    """

    prediction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    recommended_pattern: str = ""
    expected_roas: float = 0.0
    expected_success_rate: float = 0.0
    confidence: float = 0.0
    matched_patterns: list[LearnedPattern] = field(default_factory=list)
    context_match_score: float = 0.0
    risk_level: str = "medium"  # low / medium / high
    recommendations: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_strong(self) -> bool:
        return self.confidence >= 0.7 and bool(self.matched_patterns)

    @property
    def is_actionable(self) -> bool:
        return self.confidence >= 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "recommended_pattern": self.recommended_pattern,
            "expected_roas": round(self.expected_roas, 4),
            "expected_success_rate": round(self.expected_success_rate, 4),
            "confidence": round(self.confidence, 4),
            "matched_pattern_count": len(self.matched_patterns),
            "context_match_score": round(self.context_match_score, 4),
            "risk_level": self.risk_level,
            "recommendations": self.recommendations,
            "is_strong": self.is_strong,
            "is_actionable": self.is_actionable,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# Day 7.5.3 — DecisionLearningResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecisionLearningResult:
    """决策学习结果 — 基于历史决策反馈的增强建议.

    Attributes:
        result_id: 结果唯一标识
        recommendation: 推荐动作 (approve/approve_with_condition/deny/adjust)
        condition: 附带条件 (条件通过时描述)
        confidence: 推荐置信度 [0, 1]
        similar_decisions: 相似历史决策数
        success_count: 成功次数
        failure_count: 失败次数
        success_rate: 历史成功率
        failure_reasons: 失败原因分析
        risk_signals: 检测到的风险信号
        adjustments: 建议调整项
        created_at: 创建时间
        metadata: 扩展元数据
    """

    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    recommendation: str = "approve"  # approve / approve_with_condition / deny / adjust
    condition: str = ""
    confidence: float = 0.0
    similar_decisions: int = 0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    failure_reasons: list[str] = field(default_factory=list)
    risk_signals: list[str] = field(default_factory=list)
    adjustments: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_safe(self) -> bool:
        return self.confidence >= 0.7 and self.success_rate >= 0.6

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "recommendation": self.recommendation,
            "condition": self.condition,
            "confidence": round(self.confidence, 4),
            "similar_decisions": self.similar_decisions,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": round(self.success_rate, 4),
            "failure_reasons": self.failure_reasons,
            "risk_signals": self.risk_signals,
            "adjustments": self.adjustments,
            "is_safe": self.is_safe,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# Day 7.5.4 — LearningCycleResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearningCycleResult:
    """学习循环结果 — 一次完整学习闭环的输出.

    Attributes:
        cycle_id: 循环唯一标识
        knowledge: 提取的知识
        prediction: 模式预测结果
        decision_learning: 决策学习结果
        cycle_confidence: 循环整体置信度
        actions_taken: 执行的动作列表
        memory_updates: 记忆更新记录
        improvements: 识别的改进点
        next_cycle_recommendations: 下一轮循环建议
        created_at: 创建时间
        metadata: 扩展元数据
    """

    cycle_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    knowledge: LearningKnowledge | None = None
    prediction: PatternPrediction | None = None
    decision_learning: DecisionLearningResult | None = None
    cycle_confidence: float = 0.0
    actions_taken: list[str] = field(default_factory=list)
    memory_updates: dict[str, Any] = field(default_factory=dict)
    improvements: list[str] = field(default_factory=list)
    next_cycle_recommendations: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        return self.knowledge is not None and self.cycle_confidence > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "knowledge": self.knowledge.to_dict() if self.knowledge else None,
            "prediction": self.prediction.to_dict() if self.prediction else None,
            "decision_learning": self.decision_learning.to_dict() if self.decision_learning else None,
            "cycle_confidence": round(self.cycle_confidence, 4),
            "actions_taken": self.actions_taken,
            "memory_updates": self.memory_updates,
            "improvements": self.improvements,
            "next_cycle_recommendations": self.next_cycle_recommendations,
            "is_complete": self.is_complete,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════


__all__ = [
    "LearningOutcome",
    "LearningExperience",
    "RewardWeights",
    "LearningReward",
    "AttributionEvidence",
    "AttributionResult",
    "LearningResult",
    "create_learning_experience",
    # Day 7.5.1
    "LearnedPattern",
    "StrategyInsight",
    "RiskSignal",
    "LearningKnowledge",
    # Day 7.5.2-7.5.4
    "PatternPrediction",
    "DecisionLearningResult",
    "LearningCycleResult",
]