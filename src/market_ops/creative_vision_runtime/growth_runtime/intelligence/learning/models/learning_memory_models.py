"""E13.7.9 Learning Memory Consolidation Models — 学习记忆固化协议.

Day 7.9:
  将 Learning Cycle 的结果沉淀为 Memory System 可用的经验数据，
  实现从「反应式优化器」到「持续进化的 Growth Intelligence Engine」的升级。

核心模型:
  1. ConsolidatedExperience  — 从学习循环提取的固化经验
  2. ExtractionResult        — 经验提取结果与统计

设计原则:
  - 纯数据模型，不包含执行逻辑
  - 可序列化 (to_dict)，支持审计
  - 桥接 Learning System 与 Memory System (GrowthExperience)
  - 不修改已有模块
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ═══════════════════════════════════════════════════════════════
# 1. ConsolidatedExperience
# ═══════════════════════════════════════════════════════════════


@dataclass
class ConsolidatedExperience:
    """固化经验 — 从一次学习循环中提取的结构化经验.

    这是 Learning System → Memory System 的桥接模型。
    每个 ConsolidatedExperience 可被转换为 GrowthExperience 存入 ExperienceStore。

    提取维度:
      - 策略决策: action_type, action_params, decision_type
      - 执行结果: success, metrics_delta, reward
      - 学习效果: learning_gain, effectiveness_score
      - 反馈分类: feedback_classification, gate_decision
      - 策略调整: policy_adjustments applied

    Attributes:
        experience_id: 经验唯一标识
        source_cycle_id: 来源编排周期 ID
        cycle_number: 编排周期编号
        action_type: 执行的动作类型
        action_params: 执行参数
        decision_type: 策略决策类型
        success: 执行是否成功
        metrics_delta: 指标变化 (after - before)
        reward: 综合奖励 [0, 1]
        confidence: 决策置信度 [0, 1]
        category: 经验类别 (对应 ExperienceCategory)
        feedback_classification: 反馈分类 (GOOD_LEARNING / BAD_LEARNING / STAGNANT / INSUFFICIENT_DATA)
        learning_gain: 学习增益 (enhanced - baseline)
        effectiveness_score: 学习有效性评分 [0, 1]
        gate_decision: 门控决策 (continue / pause / rollback / request_more_data)
        policy_adjustments: 应用的策略调整详情
        is_significant: 是否值得记忆 (显著经验)
        significance_score: 显著性评分 [0, 1]
        tags: 标签
        created_at: 创建时间
        metadata: 扩展元数据
    """

    experience_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_cycle_id: str = ""
    cycle_number: int = 0

    # ── 策略决策 ──
    action_type: str = ""
    action_params: dict[str, Any] = field(default_factory=dict)
    decision_type: str = ""

    # ── 执行结果 ──
    success: bool = False
    metrics_delta: dict[str, float] = field(default_factory=dict)

    # ── 奖励与置信度 ──
    reward: float = 0.0
    confidence: float = 0.0

    # ── 分类 ──
    category: str = "creative"  # creative / ua / revenue

    # ── 学习上下文 ──
    feedback_classification: str = ""
    learning_gain: float = 0.0
    effectiveness_score: float = 0.0

    # ── 门控上下文 ──
    gate_decision: str = ""

    # ── 策略调整 ──
    policy_adjustments: list[dict[str, Any]] = field(default_factory=list)

    # ── 显著性 ──
    is_significant: bool = False
    significance_score: float = 0.0

    # ── 元数据 ──
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def has_learning_gain(self) -> bool:
        """是否有正向学习增益."""
        return self.learning_gain > 0

    @property
    def is_effective(self) -> bool:
        """学习是否有效."""
        return self.effectiveness_score >= 0.5

    @property
    def is_gated(self) -> bool:
        """是否被门控阻止."""
        return self.gate_decision in ("pause", "rollback")

    @property
    def has_adjustments(self) -> bool:
        """是否有策略调整."""
        return len(self.policy_adjustments) > 0

    @property
    def adjustment_count(self) -> int:
        """策略调整数量."""
        return len(self.policy_adjustments)

    # ── Factory Methods ─────────────────────────────────────────

    @classmethod
    def from_cycle_result(
        cls,
        cycle_result: Any,  # OrchestrationCycleResult
        significance_threshold: float = 0.3,
    ) -> ConsolidatedExperience:
        """从 OrchestrationCycleResult 创建固化经验.

        Args:
            cycle_result: OrchestrationCycleResult 实例
            significance_threshold: 显著性阈值 (低于此值不标记为 significant)

        Returns:
            ConsolidatedExperience: 固化经验
        """
        exp = cls(
            source_cycle_id=getattr(cycle_result, "cycle_id", ""),
            cycle_number=getattr(cycle_result, "cycle_number", 0),
        )

        # ── 提取策略决策 ──
        policy_decision = getattr(cycle_result, "policy_decision", None)
        if policy_decision is not None:
            exp.action_type = getattr(policy_decision, "action", "") or ""
            exp.decision_type = getattr(policy_decision, "decision_type", "") or ""
            exp.confidence = getattr(policy_decision, "confidence", 0.0) or 0.0
            exp.action_params = cls._extract_action_params(policy_decision)

        # ── 提取执行结果 ──
        execution_result = getattr(cycle_result, "execution_result", None)
        if execution_result is not None:
            exp.success = getattr(execution_result, "success", False)
            exp.action_type = exp.action_type or getattr(execution_result, "action", "") or ""

        # ── 提取有效性 ──
        effectiveness = getattr(cycle_result, "effectiveness", None)
        if effectiveness is not None:
            exp.learning_gain = getattr(effectiveness, "learning_gain", 0.0) or 0.0
            exp.effectiveness_score = getattr(effectiveness, "effectiveness_score", 0.0) or 0.0
            exp.metrics_delta = cls._extract_metrics_delta(effectiveness)

        # ── 提取反馈分类 ──
        if hasattr(cycle_result, "gate_result") and cycle_result.gate_result is not None:
            gate = cycle_result.gate_result
            exp.feedback_classification = getattr(gate, "feedback_classification", "") or ""
            exp.gate_decision = getattr(gate, "decision", "") or ""

        # ── 提取策略调整 ──
        if hasattr(cycle_result, "policy_adjustments") and cycle_result.policy_adjustments is not None:
            adj_set = cycle_result.policy_adjustments
            exp.policy_adjustments = cls._extract_adjustments(adj_set)

        # ── 计算奖励 ──
        exp.reward = cls._compute_reward(exp)

        # ── 推断类别 ──
        exp.category = cls._infer_category(exp.action_type)

        # ── 计算显著性 ──
        exp.significance_score = cls._compute_significance(exp)
        exp.is_significant = exp.significance_score >= significance_threshold

        # ── 生成标签 ──
        exp.tags = cls._generate_tags(exp)

        return exp

    @staticmethod
    def _extract_action_params(policy_decision: Any) -> dict[str, Any]:
        """提取策略决策的动作参数."""
        params: dict[str, Any] = {}
        if hasattr(policy_decision, "adjustments") and policy_decision.adjustments:
            params["adjustments"] = policy_decision.adjustments
        if hasattr(policy_decision, "strategy_mode") and policy_decision.strategy_mode:
            params["strategy_mode"] = policy_decision.strategy_mode
        if hasattr(policy_decision, "expected_impact") and policy_decision.expected_impact is not None:
            params["expected_impact"] = policy_decision.expected_impact
        if hasattr(policy_decision, "priority") and policy_decision.priority:
            params["priority"] = policy_decision.priority
        return params

    @staticmethod
    def _extract_metrics_delta(effectiveness: Any) -> dict[str, float]:
        """从有效性评估中提取指标变化."""
        delta: dict[str, float] = {}
        if hasattr(effectiveness, "baseline_success_rate") and hasattr(effectiveness, "enhanced_success_rate"):
            baseline = effectiveness.baseline_success_rate or 0.0
            enhanced = effectiveness.enhanced_success_rate or 0.0
            if baseline > 0 or enhanced > 0:
                delta["success_rate"] = round(enhanced - baseline, 4)
        if hasattr(effectiveness, "baseline_avg_confidence") and hasattr(effectiveness, "enhanced_avg_confidence"):
            baseline = effectiveness.baseline_avg_confidence or 0.0
            enhanced = effectiveness.enhanced_avg_confidence or 0.0
            if baseline > 0 or enhanced > 0:
                delta["confidence"] = round(enhanced - baseline, 4)
        if hasattr(effectiveness, "learning_gain") and effectiveness.learning_gain is not None:
            delta["learning_gain"] = effectiveness.learning_gain
        return delta

    @staticmethod
    def _extract_adjustments(adj_set: Any) -> list[dict[str, Any]]:
        """提取策略调整详情."""
        adjustments: list[dict[str, Any]] = []
        if hasattr(adj_set, "adjustments") and adj_set.adjustments:
            for adj in adj_set.adjustments:
                adjustments.append({
                    "target_policy": getattr(adj, "target_policy", ""),
                    "current_value": getattr(adj, "current_value", 0.0),
                    "recommended_value": getattr(adj, "recommended_value", 0.0),
                    "adjustment_delta": getattr(adj, "adjustment_delta", 0.0),
                    "direction": getattr(adj, "direction", ""),
                    "reason": getattr(adj, "reason", ""),
                    "confidence": getattr(adj, "confidence", 0.0),
                })
        return adjustments

    @staticmethod
    def _compute_reward(exp: ConsolidatedExperience) -> float:
        """计算综合奖励.

        奖励 = learning_gain_normalized × 0.5 + success × 0.3 + effectiveness × 0.2
        """
        # 学习增益归一化到 [0, 1]
        gain_normalized = max(0.0, min(1.0, (exp.learning_gain + 0.5)))  # [-0.5, 0.5] → [0, 1]
        success_reward = 1.0 if exp.success else 0.0
        reward = round(
            gain_normalized * 0.5 + success_reward * 0.3 + exp.effectiveness_score * 0.2,
            4,
        )
        return reward

    @staticmethod
    def _infer_category(action_type: str) -> str:
        """从 action_type 推断经验类别."""
        creative_actions = {
            "clone_dna", "generate_variants", "mutate_hook", "mutate_visual",
            "create_population", "launch_ab_test", "replace_creative",
            "creative_refresh", "creative_rotation",
        }
        ua_actions = {
            "increase_budget", "reduce_budget", "duplicate_campaign",
            "pause_campaign", "expand_targeting", "reallocate_budget", "adjust_bid",
            "campaign_optimization", "bid_adjustment",
        }
        revenue_actions = {
            "optimize_pricing", "optimize_ad_placement", "increase_retention",
            "create_high_value_audience", "revenue_optimization",
        }
        learning_actions = {
            "execute_learning", "update_learning", "consolidate_memory",
            "optimize_strategy", "refresh_memory",
        }
        if action_type in creative_actions:
            return "creative"
        elif action_type in ua_actions:
            return "ua"
        elif action_type in revenue_actions:
            return "revenue"
        elif action_type in learning_actions:
            return "creative"  # learning actions default to creative
        return "creative"

    @staticmethod
    def _compute_significance(exp: ConsolidatedExperience) -> float:
        """计算经验显著性评分.

        显著性 = abs(learning_gain) × 0.4 + abs(effectiveness_score - 0.5) × 0.3
                + has_adjustments × 0.2 + is_gated × 0.1
        """
        gain_abs = min(abs(exp.learning_gain) * 2.0, 1.0)  # 放大 gain 影响力
        effectiveness_deviation = abs(exp.effectiveness_score - 0.5) * 2.0
        adjustments_bonus = 0.2 if exp.has_adjustments else 0.0
        gated_bonus = 0.1 if exp.is_gated else 0.0
        score = round(
            gain_abs * 0.4 + effectiveness_deviation * 0.3 + adjustments_bonus + gated_bonus,
            4,
        )
        return max(0.0, min(1.0, score))

    @staticmethod
    def _generate_tags(exp: ConsolidatedExperience) -> list[str]:
        """生成经验标签."""
        tags: list[str] = []
        if exp.has_learning_gain:
            tags.append("positive_learning")
        if exp.is_effective:
            tags.append("effective")
        if exp.is_gated:
            tags.append("gated")
        if exp.has_adjustments:
            tags.append("adjusted")
        if exp.success:
            tags.append("success")
        else:
            tags.append("failure" if not exp.success else "neutral")
        if exp.feedback_classification:
            tags.append(exp.feedback_classification.lower())
        if exp.is_significant:
            tags.append("significant")
        return tags

    # ── Serialization ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "experience_id": self.experience_id,
            "source_cycle_id": self.source_cycle_id,
            "cycle_number": self.cycle_number,
            "action_type": self.action_type,
            "action_params": self.action_params,
            "decision_type": self.decision_type,
            "success": self.success,
            "metrics_delta": self.metrics_delta,
            "reward": self.reward,
            "confidence": self.confidence,
            "category": self.category,
            "feedback_classification": self.feedback_classification,
            "learning_gain": self.learning_gain,
            "effectiveness_score": self.effectiveness_score,
            "gate_decision": self.gate_decision,
            "policy_adjustments": self.policy_adjustments,
            "is_significant": self.is_significant,
            "significance_score": self.significance_score,
            "tags": self.tags,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_growth_experience(
        cls,
        growth_exp: Any,  # GrowthExperience
        significance_threshold: float = 0.3,
    ) -> ConsolidatedExperience:
        """从 GrowthExperience 创建 ConsolidatedExperience.

        这是 ExperienceStore → Consolidation Pipeline 的核心转换点，
        允许从已存储的经验直接构建固化经验用于压缩和强化。

        Args:
            growth_exp: GrowthExperience 实例
            significance_threshold: 显著性阈值

        Returns:
            ConsolidatedExperience: 固化经验
        """
        exp = cls(
            source_cycle_id=getattr(growth_exp, "experience_id", ""),
            cycle_number=0,
            action_type=getattr(growth_exp, "action_type", ""),
            action_params=getattr(growth_exp, "action_params", {}) or {},
            success=getattr(growth_exp, "outcome", None) is not None
                and getattr(growth_exp.outcome, "success", False),
            metrics_delta=getattr(growth_exp, "outcome", None) is not None
                and getattr(growth_exp.outcome, "metrics_delta", None) or {},
            reward=getattr(growth_exp, "reward", 0.0) or 0.0,
            confidence=getattr(growth_exp, "confidence", 0.0) or 0.0,
            category=getattr(growth_exp, "category", None) is not None
                and getattr(growth_exp.category, "value", "creative") or "creative",
            tags=list(getattr(growth_exp, "tags", []) or []),
            metadata=getattr(growth_exp, "metadata", {}) or {},
        )

        # 计算 learning_gain (从 reward 推断)
        base_reward = 0.5
        exp.learning_gain = round(max(0.0, exp.reward - base_reward), 4)
        exp.effectiveness_score = round(exp.reward * 0.6 + (1.0 if exp.success else 0.0) * 0.4, 4)

        # 推断决策类型
        exp.decision_type = "allow_learning" if exp.success else "adjust_mode"

        # 反馈分类
        if exp.learning_gain > 0.1:
            exp.feedback_classification = "GOOD_LEARNING"
        elif exp.success:
            exp.feedback_classification = "STAGNANT"
        else:
            exp.feedback_classification = "BAD_LEARNING"

        # 计算显著性
        exp.significance_score = cls._compute_significance(exp)
        exp.is_significant = exp.significance_score >= significance_threshold

        # 生成标签
        exp.tags = cls._generate_tags(exp)

        return exp

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ConsolidatedExperience:
        return cls(
            experience_id=d.get("experience_id", ""),
            source_cycle_id=d.get("source_cycle_id", ""),
            cycle_number=d.get("cycle_number", 0),
            action_type=d.get("action_type", ""),
            action_params=d.get("action_params", {}),
            decision_type=d.get("decision_type", ""),
            success=d.get("success", False),
            metrics_delta=d.get("metrics_delta", {}),
            reward=d.get("reward", 0.0),
            confidence=d.get("confidence", 0.0),
            category=d.get("category", "creative"),
            feedback_classification=d.get("feedback_classification", ""),
            learning_gain=d.get("learning_gain", 0.0),
            effectiveness_score=d.get("effectiveness_score", 0.0),
            gate_decision=d.get("gate_decision", ""),
            policy_adjustments=d.get("policy_adjustments", []),
            is_significant=d.get("is_significant", False),
            significance_score=d.get("significance_score", 0.0),
            tags=d.get("tags", []),
            created_at=d.get("created_at", ""),
            metadata=d.get("metadata", {}),
        )


# ═══════════════════════════════════════════════════════════════
# 2. ExtractionResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class ExtractionResult:
    """经验提取结果 — 一次提取操作的完整输出.

    Attributes:
        extraction_id: 提取操作唯一标识
        source_cycle_id: 来源编排周期 ID
        cycle_number: 编排周期编号
        experiences: 提取的固化经验列表
        total_extracted: 提取总数
        significant_count: 显著经验数
        total_reward: 总奖励
        avg_reward: 平均奖励
        avg_significance: 平均显著性
        category_distribution: 类别分布
        extraction_summary: 提取摘要
        created_at: 创建时间
        metadata: 扩展元数据
    """

    extraction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_cycle_id: str = ""
    cycle_number: int = 0
    experiences: list[ConsolidatedExperience] = field(default_factory=list)
    total_extracted: int = 0
    significant_count: int = 0
    total_reward: float = 0.0
    avg_reward: float = 0.0
    avg_significance: float = 0.0
    category_distribution: dict[str, int] = field(default_factory=dict)
    extraction_summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Factory Methods ─────────────────────────────────────────

    @classmethod
    def from_experiences(
        cls,
        experiences: list[ConsolidatedExperience],
        source_cycle_id: str = "",
        cycle_number: int = 0,
    ) -> ExtractionResult:
        """从经验列表创建提取结果.

        Args:
            experiences: ConsolidatedExperience 列表
            source_cycle_id: 来源周期 ID
            cycle_number: 周期编号

        Returns:
            ExtractionResult: 提取结果
        """
        n = len(experiences)
        significant = [e for e in experiences if e.is_significant]
        total_reward = round(sum(e.reward for e in experiences), 4)
        avg_reward = round(total_reward / n, 4) if n > 0 else 0.0
        avg_significance = round(sum(e.significance_score for e in experiences) / n, 4) if n > 0 else 0.0

        # 类别分布
        cat_dist: dict[str, int] = {}
        for e in experiences:
            cat_dist[e.category] = cat_dist.get(e.category, 0) + 1

        # 生成摘要
        summary = cls._build_summary(n, len(significant), avg_reward, avg_significance, cat_dist)

        return cls(
            source_cycle_id=source_cycle_id,
            cycle_number=cycle_number,
            experiences=experiences,
            total_extracted=n,
            significant_count=len(significant),
            total_reward=total_reward,
            avg_reward=avg_reward,
            avg_significance=avg_significance,
            category_distribution=cat_dist,
            extraction_summary=summary,
        )

    @staticmethod
    def _build_summary(
        total: int,
        significant: int,
        avg_reward: float,
        avg_significance: float,
        cat_dist: dict[str, int],
    ) -> str:
        """构建提取摘要."""
        lines = [
            "-" * 45,
            f"  Experience Extraction Summary",
            "-" * 45,
            f"  Total extracted:    {total:>4d}",
            f"  Significant:        {significant:>4d} ({significant/max(total,1)*100:.0f}%)",
            f"  Avg reward:         {avg_reward:>7.4f}",
            f"  Avg significance:   {avg_significance:>7.4f}",
            "-" * 45,
            f"  Category distribution:",
        ]
        for cat, count in sorted(cat_dist.items()):
            lines.append(f"    {cat}: {count}")
        lines.append("-" * 45)
        return "\n".join(lines)

    # ── Properties ──────────────────────────────────────────────

    @property
    def has_significant(self) -> bool:
        """是否有显著经验."""
        return self.significant_count > 0

    @property
    def is_empty(self) -> bool:
        """是否为空提取."""
        return self.total_extracted == 0

    @property
    def significant_experiences(self) -> list[ConsolidatedExperience]:
        """获取显著经验列表."""
        return [e for e in self.experiences if e.is_significant]

    # ── Serialization ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "extraction_id": self.extraction_id,
            "source_cycle_id": self.source_cycle_id,
            "cycle_number": self.cycle_number,
            "experiences": [e.to_dict() for e in self.experiences],
            "total_extracted": self.total_extracted,
            "significant_count": self.significant_count,
            "total_reward": self.total_reward,
            "avg_reward": self.avg_reward,
            "avg_significance": self.avg_significance,
            "category_distribution": self.category_distribution,
            "extraction_summary": self.extraction_summary,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "ConsolidatedExperience",
    "ExtractionResult",
]