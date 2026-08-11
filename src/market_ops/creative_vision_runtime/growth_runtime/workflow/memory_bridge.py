"""E15.1.5 Memory Feedback Bridge — 执行→记忆→智能 闭环桥梁.

将 Execution 结果转换为 GrowthExperience，存入 ExperienceStore，
触发 PatternMiner 更新 PatternMemory，并发布反馈事件。

核心闭环:
  Execution Result
      ↓
  ExperienceBuilder.build() → GrowthExperience
      ↓
  ExperienceStore.store()
      ↓
  PatternMiner.mine() → PatternMemory
      ↓
  PatternStore.store()
      ↓
  MemoryFeedbackEvent → EventBus

用法:
    bridge = MemoryFeedbackBridge(
        experience_store=store,
        pattern_store=patterns,
        event_bus=bus,
    )

    result = ExecutionResult(...)
    experience = bridge.process_execution_result(result)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

from ..memory.models import (
    ExperienceCategory,
    ExperienceContext,
    ExperienceOutcome,
    ExperienceOutcomeLevel,
    GrowthExperience,
    PatternAction,
    PatternCondition,
    PatternMemory,
    PatternMiningDimension,
    PatternPerformance,
    PatternQuality,
)

if TYPE_CHECKING:
    from ..memory.experience_store import ExperienceStore
    from ..memory.pattern_miner import PatternMiner
    from ..memory.pattern_store import PatternStore
    from ..observability.events import EventBus


# ═══════════════════════════════════════════════════════════════
# Execution Result
# ═══════════════════════════════════════════════════════════════


class ExecutionStatus(str, Enum):
    """执行结果状态."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"       # 部分成功 (部分 Task 失败)
    ROLLED_BACK = "rolled_back"  # 已回滚


@dataclass
class ExecutionResult:
    """E15.1.5 执行结果 — 一次 Workflow 执行的完整结果.

    Attributes:
        result_id:         结果唯一标识
        workflow_id:       Workflow ID
        workflow_name:     Workflow 名称
        action_type:       执行的动作类型
        status:            整体执行状态
        context:           执行上下文 (平台、国家、创意类型等)
        metrics_before:    执行前指标
        metrics_after:     执行后指标
        duration_ms:       执行耗时 (毫秒)
        retry_count:       总重试次数
        task_results:      各 Task 的执行结果
        error:             错误信息
        trace_id:          追踪 ID
        timestamp:         时间戳
    """
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    workflow_name: str = ""
    action_type: str = ""
    status: ExecutionStatus = ExecutionStatus.SUCCESS
    context: dict[str, Any] = field(default_factory=dict)
    metrics_before: dict[str, float] = field(default_factory=dict)
    metrics_after: dict[str, float] = field(default_factory=dict)
    duration_ms: float = 0.0
    retry_count: int = 0
    task_results: list[TaskExecutionResult] = field(default_factory=list)
    error: str = ""
    trace_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def metrics_delta(self) -> dict[str, float]:
        """计算指标变化."""
        delta: dict[str, float] = {}
        for key in set(self.metrics_before) | set(self.metrics_after):
            before = self.metrics_before.get(key, 0.0)
            after = self.metrics_after.get(key, 0.0)
            delta[key] = after - before
        return delta

    @property
    def is_success(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS

    @property
    def is_failed(self) -> bool:
        return self.status == ExecutionStatus.FAILED

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "action_type": self.action_type,
            "status": self.status.value,
            "context": self.context,
            "metrics_before": self.metrics_before,
            "metrics_after": self.metrics_after,
            "metrics_delta": self.metrics_delta,
            "duration_ms": self.duration_ms,
            "retry_count": self.retry_count,
            "task_results": [t.to_dict() for t in self.task_results],
            "error": self.error,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
        }


@dataclass
class TaskExecutionResult:
    """单个 Task 的执行结果.

    Attributes:
        task_id:         Task ID
        task_name:       Task 名称
        success:         是否成功
        duration_ms:     执行耗时
        retry_count:     重试次数
        output:          Task 输出
        error:           错误信息
    """
    task_id: str = ""
    task_name: str = ""
    success: bool = True
    duration_ms: float = 0.0
    retry_count: int = 0
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "retry_count": self.retry_count,
            "output": self.output,
            "error": self.error,
        }


# ═══════════════════════════════════════════════════════════════
# Reward Calculator
# ═══════════════════════════════════════════════════════════════


class RewardCalculator:
    """E15.1.5 奖励计算器 — 根据执行结果计算综合奖励.

    不同动作类型有不同的权重公式:

    Creative 操作 (replace_creative, launch_ab_test):
      reward = roas_delta × 0.5 + ctr_delta × 0.3 + retention_delta × 0.2

    UA 操作 (adjust_budget, expand_targeting):
      reward = profit_change × 0.6 - spend_risk × 0.4

    Revenue 操作 (optimize_pricing):
      reward = revenue_delta × 0.5 + payer_rate_delta × 0.3 + ltv_delta × 0.2

    通用:
      reward = roas_delta × 0.4 + 成功率 × 0.3 + 效率分 × 0.3
    """

    # Creative 操作权重
    CREATIVE_WEIGHTS = {"roas": 0.5, "ctr": 0.3, "retention": 0.2}

    # UA 操作权重
    UA_WEIGHTS = {"profit": 0.6, "spend_risk": 0.4}

    # Revenue 操作权重
    REVENUE_WEIGHTS = {"revenue": 0.5, "payer_rate": 0.3, "ltv": 0.2}

    def calculate(self, result: ExecutionResult) -> float:
        """根据执行结果计算奖励分数.

        Args:
            result: ExecutionResult

        Returns:
            float: 奖励分数 [0, 1], 裁剪到 [0, 1]
        """
        if result.status == ExecutionStatus.FAILED:
            return 0.0

        if result.status == ExecutionStatus.ROLLED_BACK:
            return 0.05  # 回滚给予微小奖励 (至少识别了风险)

        if not result.metrics_delta:
            # 无指标数据，基于执行质量评分
            return self._execution_quality_score(result)

        category = self._infer_category(result.action_type)
        if category == ExperienceCategory.CREATIVE:
            reward = self._calc_creative(result)
        elif category == ExperienceCategory.UA:
            reward = self._calc_ua(result)
        elif category == ExperienceCategory.REVENUE:
            reward = self._calc_revenue(result)
        else:
            reward = self._calc_generic(result)

        return round(max(0.0, min(1.0, reward)), 4)

    def _calc_creative(self, result: ExecutionResult) -> float:
        """Creative 操作奖励: roas×0.5 + ctr×0.3 + retention×0.2."""
        delta = result.metrics_delta
        roas_delta = self._normalize_delta(delta.get("roas", 0), 0.5)
        ctr_delta = self._normalize_delta(delta.get("ctr", 0), 0.3)
        retention_delta = self._normalize_delta(delta.get("retention", 0), 0.15)
        base = roas_delta * 0.5 + ctr_delta * 0.3 + retention_delta * 0.2
        return self._adjust_by_execution_quality(base, result)

    def _calc_ua(self, result: ExecutionResult) -> float:
        """UA 操作奖励: profit×0.6 - spend_risk×0.4."""
        delta = result.metrics_delta
        profit_delta = self._normalize_delta(delta.get("profit", 0), 0.3)
        # spend_risk: 预算变化越大, 风险越高
        spend_change = delta.get("spend", 0)
        spend_risk = min(1.0, abs(spend_change) / 1000)
        base = profit_delta * 0.6 - spend_risk * 0.4
        return max(0.0, self._adjust_by_execution_quality(base, result))

    def _calc_revenue(self, result: ExecutionResult) -> float:
        """Revenue 操作奖励: revenue×0.5 + payer_rate×0.3 + ltv×0.2."""
        delta = result.metrics_delta
        revenue_delta = self._normalize_delta(delta.get("revenue", 0), 0.3)
        payer_delta = self._normalize_delta(delta.get("payer_rate", 0), 0.1)
        ltv_delta = self._normalize_delta(delta.get("ltv", 0), 0.2)
        base = revenue_delta * 0.5 + payer_delta * 0.3 + ltv_delta * 0.2
        return self._adjust_by_execution_quality(base, result)

    def _calc_generic(self, result: ExecutionResult) -> float:
        """通用奖励: roas×0.4 + 成功率×0.3 + 效率分×0.3."""
        delta = result.metrics_delta
        roas_delta = self._normalize_delta(delta.get("roas", 0), 0.5)
        success_rate = self._success_rate(result)
        efficiency = self._efficiency_score(result)
        base = roas_delta * 0.4 + success_rate * 0.3 + efficiency * 0.3
        return self._adjust_by_execution_quality(base, result)

    def _execution_quality_score(self, result: ExecutionResult) -> float:
        """基于执行质量评分 (无指标数据时)."""
        success_rate = self._success_rate(result)
        efficiency = self._efficiency_score(result)
        return round(success_rate * 0.6 + efficiency * 0.4, 4)

    def _success_rate(self, result: ExecutionResult) -> float:
        """计算 Task 成功率."""
        if not result.task_results:
            return 1.0 if result.is_success else 0.0
        success_count = sum(1 for t in result.task_results if t.success)
        return success_count / len(result.task_results)

    def _efficiency_score(self, result: ExecutionResult) -> float:
        """计算执行效率分 (重试少、耗时短 = 高分)."""
        # 重试惩罚
        retry_penalty = min(0.5, result.retry_count * 0.1)
        # 耗时评分 (3000ms 以下满分, 30000ms 以上 0.3)
        if result.duration_ms <= 3000:
            time_score = 1.0
        elif result.duration_ms >= 30000:
            time_score = 0.3
        else:
            time_score = 1.0 - (result.duration_ms - 3000) / 27000 * 0.7
        # 综合
        return round(max(0.0, min(1.0, (1.0 - retry_penalty) * 0.5 + time_score * 0.5)), 4)

    def _adjust_by_execution_quality(self, base: float, result: ExecutionResult) -> float:
        """用执行质量调整基础奖励."""
        quality = self._execution_quality_score(result)
        return base * 0.7 + quality * 0.3

    @staticmethod
    def _normalize_delta(delta: float, scale: float) -> float:
        """将指标变化归一化到 [0, 1].

        delta > 0 → 正向 → 高分
        delta < 0 → 负向 → 低分
        """
        normalized = delta / scale if scale > 0 else 0.0
        return max(0.0, min(1.0, 0.5 + normalized * 0.5))

    @staticmethod
    def _infer_category(action_type: str) -> ExperienceCategory:
        """从 action_type 推断类别."""
        creative_actions = {
            "clone_dna", "generate_variants", "mutate_hook", "mutate_visual",
            "create_population", "launch_ab_test", "replace_creative",
            "creative_generation", "creative_analysis",
        }
        ua_actions = {
            "increase_budget", "reduce_budget", "duplicate_campaign",
            "pause_campaign", "expand_targeting", "reallocate_budget", "adjust_bid",
            "audience_analysis", "stop_loss", "budget_optimization",
        }
        revenue_actions = {
            "optimize_pricing", "optimize_ad_placement", "increase_retention",
            "create_high_value_audience", "revenue_analysis",
        }
        if action_type in creative_actions:
            return ExperienceCategory.CREATIVE
        elif action_type in ua_actions:
            return ExperienceCategory.UA
        elif action_type in revenue_actions:
            return ExperienceCategory.REVENUE
        return ExperienceCategory.CREATIVE


# ═══════════════════════════════════════════════════════════════
# Experience Builder
# ═══════════════════════════════════════════════════════════════


class ExperienceBuilder:
    """E15.1.5 经验构建器 — 将 ExecutionResult 转换为 GrowthExperience.

    用法:
        builder = ExperienceBuilder()
        result = ExecutionResult(action_type="replace_creative", ...)
        experience = builder.build(result)
    """

    def __init__(self, reward_calculator: RewardCalculator | None = None):
        self.reward_calculator = reward_calculator or RewardCalculator()

    def build(self, result: ExecutionResult) -> GrowthExperience:
        """将 ExecutionResult 构建为 GrowthExperience.

        Args:
            result: ExecutionResult

        Returns:
            GrowthExperience: 完整的增长经验
        """
        # 计算奖励
        reward = self.reward_calculator.calculate(result)

        # 构建上下文
        context = ExperienceContext(
            product_id=result.context.get("product_id", ""),
            date=result.timestamp[:10] if result.timestamp else "",
            opportunity_type=result.context.get("opportunity_type", ""),
            opportunity_id=result.context.get("opportunity_id", ""),
            action_type=result.action_type,
            entity_id=result.context.get("entity_id", ""),
            entity_type=result.context.get("entity_type", "creative"),
            market_conditions=result.metrics_before,
            dna_genes=result.context.get("dna_genes", {}),
            audience_segment=result.context.get("audience_segment", ""),
        )

        # 构建结果
        outcome_level = self._determine_outcome_level(result, reward)
        outcome = ExperienceOutcome(
            success=result.is_success,
            outcome_level=outcome_level,
            metrics_before=result.metrics_before,
            metrics_after=result.metrics_after,
            metrics_delta=result.metrics_delta,
            actual_impact=self._build_impact_description(result),
            actual_reward=reward,
            error=result.error,
            rolled_back=result.status == ExecutionStatus.ROLLED_BACK,
            time_to_outcome_hours=result.duration_ms / 3600000.0 if result.duration_ms else 0,
        )

        # 推断类别
        category = self.reward_calculator._infer_category(result.action_type)

        # 构建标签
        tags = self._build_tags(result)

        return GrowthExperience(
            experience_id=result.result_id,
            context=context,
            action_id=result.workflow_id,
            action_type=result.action_type,
            action_params=result.context,
            outcome=outcome,
            reward=reward,
            confidence=self._calculate_confidence(result),
            category=category,
            tags=tags,
            timestamp=result.timestamp,
            metadata={
                "workflow_name": result.workflow_name,
                "duration_ms": result.duration_ms,
                "retry_count": result.retry_count,
                "task_count": len(result.task_results),
                "trace_id": result.trace_id,
            },
        )

    def _determine_outcome_level(
        self, result: ExecutionResult, reward: float
    ) -> ExperienceOutcomeLevel:
        """根据结果和奖励确定结果等级."""
        if result.status == ExecutionStatus.FAILED:
            return ExperienceOutcomeLevel.STRONG_FAILURE
        if result.status == ExecutionStatus.ROLLED_BACK:
            return ExperienceOutcomeLevel.FAILURE
        if reward >= 0.8:
            return ExperienceOutcomeLevel.STRONG_SUCCESS
        if reward >= 0.55:
            return ExperienceOutcomeLevel.SUCCESS
        if reward >= 0.35:
            return ExperienceOutcomeLevel.NEUTRAL
        if reward >= 0.15:
            return ExperienceOutcomeLevel.FAILURE
        return ExperienceOutcomeLevel.STRONG_FAILURE

    def _build_impact_description(self, result: ExecutionResult) -> str:
        """构建影响描述."""
        delta = result.metrics_delta
        if not delta:
            return result.status.value
        parts = []
        for key, val in delta.items():
            direction = "+" if val > 0 else ""
            parts.append(f"{key}: {direction}{val:.2f}")
        return "; ".join(parts)

    def _build_tags(self, result: ExecutionResult) -> list[str]:
        """构建标签."""
        tags = [result.action_type, result.status.value]
        platform = result.context.get("platform", "")
        country = result.context.get("country", "")
        creative_type = result.context.get("creative_type", "")
        if platform:
            tags.append(platform)
        if country:
            tags.append(country)
        if creative_type:
            tags.append(creative_type)
        if result.retry_count > 0:
            tags.append("retried")
        return tags

    def _calculate_confidence(self, result: ExecutionResult) -> float:
        """计算经验置信度."""
        if result.status == ExecutionStatus.FAILED:
            return 0.0
        # 基于 Task 成功率和重试次数
        success_rate = self.reward_calculator._success_rate(result)
        retry_factor = max(0.3, 1.0 - result.retry_count * 0.15)
        return round(success_rate * retry_factor, 4)


# ═══════════════════════════════════════════════════════════════
# Pattern Updater
# ═══════════════════════════════════════════════════════════════


class PatternUpdater:
    """E15.1.5 模式更新器 — 从单个经验更新/创建 PatternMemory.

    用法:
        updater = PatternUpdater(pattern_store)
        updater.update_from_experience(experience)
    """

    def __init__(self, pattern_store: PatternStore):
        self._store = pattern_store

    def update_from_experience(self, experience: GrowthExperience) -> PatternMemory | None:
        """从一条经验更新模式记忆.

        Args:
            experience: GrowthExperience

        Returns:
            PatternMemory | None: 更新/创建的模式
        """
        condition = self._extract_condition(experience)
        action = PatternAction(
            action_type=experience.action_type,
            params_template=experience.action_params,
            expected_impact=experience.outcome.actual_impact,
            approval_level="auto" if experience.reward > 0.5 else "review",
        )

        performance = PatternPerformance(
            samples=1,
            success_count=1 if experience.is_successful() else 0,
            success_rate=1.0 if experience.is_successful() else 0.0,
            avg_reward=experience.reward,
            avg_confidence=experience.confidence,
            avg_metrics_delta=experience.outcome.metrics_delta,
            first_seen=experience.timestamp,
            last_seen=experience.timestamp,
            trend=[experience.reward],
        )

        pattern = PatternMemory(
            dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
            condition=condition,
            action=action,
            performance=performance,
            source_experience_ids=[experience.experience_id],
            tags=experience.tags,
        )
        pattern.compute_score()
        self._store.store(pattern)
        return pattern

    def _extract_condition(self, experience: GrowthExperience) -> PatternCondition:
        """从经验提取模式条件."""
        ctx = experience.context
        market = ctx.market_conditions
        return PatternCondition(
            opportunity_type=ctx.opportunity_type,
            action_type=experience.action_type,
            category=experience.category.value,
            audience_segment=ctx.audience_segment,
            dna_genes=ctx.dna_genes,
            product_category=ctx.product_id,
            entity_type=ctx.entity_type,
        )


# ═══════════════════════════════════════════════════════════════
# Memory Feedback Bridge
# ═══════════════════════════════════════════════════════════════


@dataclass
class MemoryFeedbackEvent:
    """E15.1.5 记忆反馈事件 — 桥接层发布的事件.

    Attributes:
        event_id:       事件唯一标识
        event_type:     事件类型
        experience_id:  经验 ID
        workflow_id:    Workflow ID
        action_type:    动作类型
        reward:         奖励分数
        pattern_id:     关联模式 ID (如有)
        timestamp:      时间戳
        payload:        扩展负载
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    experience_id: str = ""
    workflow_id: str = ""
    action_type: str = ""
    reward: float = 0.0
    pattern_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "experience_id": self.experience_id,
            "workflow_id": self.workflow_id,
            "action_type": self.action_type,
            "reward": self.reward,
            "pattern_id": self.pattern_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }


class MemoryFeedbackEventType(str, Enum):
    """E15.1.5 记忆反馈事件类型."""
    EXPERIENCE_STORED = "experience_stored"
    PATTERN_UPDATED = "pattern_updated"
    PATTERN_CREATED = "pattern_created"
    KNOWLEDGE_UPDATED = "knowledge_updated"
    FEEDBACK_LOOP_CLOSED = "feedback_loop_closed"


class MemoryFeedbackBridge:
    """E15.1.5 记忆反馈桥 — Execution → Memory → Intelligence 闭环.

    核心流程:
      1. process_execution_result() 接收 ExecutionResult
      2. ExperienceBuilder 构建 GrowthExperience
      3. ExperienceStore 存储经验
      4. PatternUpdater 更新 PatternMemory
      5. 发布 MemoryFeedbackEvent 事件

    用法:
        bridge = MemoryFeedbackBridge(
            experience_store=store,
            pattern_store=patterns,
            event_bus=bus,
        )
        experience = bridge.process_execution_result(result)
    """

    def __init__(
        self,
        experience_store: ExperienceStore,
        pattern_store: PatternStore,
        event_bus: EventBus | None = None,
        reward_calculator: RewardCalculator | None = None,
    ):
        self._experience_store = experience_store
        self._pattern_store = pattern_store
        self._event_bus = event_bus
        self._builder = ExperienceBuilder(reward_calculator)
        self._pattern_updater = PatternUpdater(pattern_store)
        self._processed_count: int = 0
        self._feedback_events: list[MemoryFeedbackEvent] = []

    # ── Core API ──────────────────────────────────────────────

    def process_execution_result(self, result: ExecutionResult) -> GrowthExperience:
        """处理执行结果，完成完整反馈闭环.

        Args:
            result: ExecutionResult

        Returns:
            GrowthExperience: 创建的经验
        """
        self._processed_count += 1

        # 1. 构建经验
        experience = self._builder.build(result)

        # 2. 存储经验
        self._experience_store.store(experience)
        self._emit_event(
            MemoryFeedbackEventType.EXPERIENCE_STORED,
            experience,
            result,
        )

        # 3. 更新模式
        pattern = self._pattern_updater.update_from_experience(experience)
        if pattern is not None:
            event_type = MemoryFeedbackEventType.PATTERN_UPDATED if pattern.performance.samples > 1 else MemoryFeedbackEventType.PATTERN_CREATED
            self._emit_event(event_type, experience, result, pattern_id=pattern.pattern_id)

        # 4. 闭环完成
        self._emit_event(
            MemoryFeedbackEventType.FEEDBACK_LOOP_CLOSED,
            experience,
            result,
            pattern_id=pattern.pattern_id if pattern else "",
        )

        return experience

    def process_batch(self, results: list[ExecutionResult]) -> list[GrowthExperience]:
        """批量处理执行结果.

        Args:
            results: ExecutionResult 列表

        Returns:
            list[GrowthExperience]: 创建的经验列表
        """
        return [self.process_execution_result(r) for r in results]

    # ── Query ─────────────────────────────────────────────────

    def get_processed_count(self) -> int:
        """获取已处理结果数量."""
        return self._processed_count

    def get_feedback_events(self, limit: int = 50) -> list[MemoryFeedbackEvent]:
        """获取反馈事件."""
        return self._feedback_events[-limit:]

    def get_recent_experiences(self, n: int = 10) -> list[GrowthExperience]:
        """获取最近 N 条经验."""
        return self._experience_store.get_recent(n)

    def get_patterns(self) -> list[PatternMemory]:
        """获取所有模式."""
        return self._pattern_store.get_all()

    def get_stats(self) -> dict[str, Any]:
        """获取反馈桥统计."""
        exp_stats = self._experience_store.get_stats()
        return {
            "processed_count": self._processed_count,
            "total_experiences": exp_stats.total_experiences,
            "success_rate": exp_stats.success_rate,
            "avg_reward": exp_stats.avg_reward,
            "total_patterns": self._pattern_store.count,
            "event_count": len(self._feedback_events),
        }

    # ── Internal ──────────────────────────────────────────────

    def _emit_event(
        self,
        event_type: MemoryFeedbackEventType,
        experience: GrowthExperience,
        result: ExecutionResult,
        pattern_id: str = "",
    ) -> None:
        event = MemoryFeedbackEvent(
            event_type=event_type.value,
            experience_id=experience.experience_id,
            workflow_id=result.workflow_id,
            action_type=result.action_type,
            reward=experience.reward,
            pattern_id=pattern_id,
            payload={
                "status": result.status.value,
                "duration_ms": result.duration_ms,
                "retry_count": result.retry_count,
            },
        )
        self._feedback_events.append(event)

        # 发布到外部 EventBus
        if self._event_bus is not None:
            from ..observability.events import ExecutionEvent, ExecutionEventType

            obs_event = ExecutionEvent(
                event_type=ExecutionEventType.EXECUTION_SUCCESS
                if result.is_success
                else ExecutionEventType.EXECUTION_FAILED,
                action_id=result.workflow_id,
                payload={
                    "feedback_event": event.to_dict(),
                    "experience_id": experience.experience_id,
                    "reward": experience.reward,
                },
            )
            self._event_bus.emit(obs_event)


__all__ = [
    "ExecutionStatus",
    "ExecutionResult",
    "TaskExecutionResult",
    "RewardCalculator",
    "ExperienceBuilder",
    "PatternUpdater",
    "MemoryFeedbackEventType",
    "MemoryFeedbackEvent",
    "MemoryFeedbackBridge",
]