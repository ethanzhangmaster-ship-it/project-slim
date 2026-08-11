"""E14.7.1 Growth Action Router — 增长动作路由器.

E14.7「Autonomous Growth Execution Layer」第一层:
  将 E14.6.3 EvolutionSignal + E13 GrowthOpportunity + Reality Context
  路由为统一的 GrowthAction，分配到对应执行系统.

职责:
  1. 将 EvolutionSignal 映射为 GrowthAction (Signal → Action 路由矩阵)
  2. 融合 GrowthOpportunity 的优先级和紧急度
  3. 批量路由与优先级排序
  4. 动作验证 (安全/预算/权限检查)
  5. 统计与监控

核心概念:
  - GrowthActionType: 统一动作类型枚举 (Creative / UA / Experiment / Evolution)
  - GrowthAction: 统一执行命令
  - ActionSource: 动作来源 (evolution_signal / growth_opportunity / manual)
  - GrowthActionRouter: 核心路由器

数据流:
  EvolutionSignal (E14.6.3)
       ↓
  GrowthActionRouter.route()
       ↓
  GrowthAction
       ↓
  ├─ MetaAdsExecutor (scale_campaign, reduce_budget, pause_campaign)
  ├─ CreativeExecutor (create_creative, mutate_creative, promote_winner)
  ├─ ExperimentExecutor (start_experiment, end_experiment)
  └─ EvolutionExecutor (create_variants, diversify_population)

路由矩阵:
  | Evolution Signal | Growth Action      |
  |------------------|--------------------|
  | AMPLIFY          | PROMOTE_WINNER     |
  | SUPPRESS         | REDUCE_BUDGET      |
  | EXPLORE          | CREATE_VARIANTS    |
  | RETEST           | START_EXPERIMENT   |
  | MAINTAIN         | HOLD               |
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
    EvolutionSignal,
    SignalAction,
)


# ═══════════════════════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════════════════════

class GrowthActionType(str, Enum):
    """统一增长动作类型.

    Creative 类:
      CREATE_CREATIVE    — 创建新创意
      MUTATE_CREATIVE    — 变异创意 (DNA 变异)
      PROMOTE_WINNER     — 推广 Winner 创意

    UA 类:
      SCALE_CAMPAIGN     — 放量广告系列
      REDUCE_BUDGET      — 降低预算
      PAUSE_CAMPAIGN     — 暂停广告系列

    Experiment 类:
      START_EXPERIMENT   — 启动实验
      END_EXPERIMENT     — 结束实验

    Evolution 类:
      CREATE_VARIANTS    — 创建变异体
      DIVERSIFY_POPULATION — 多样化种群

    No-op:
      HOLD               — 保持现状
    """
    # Creative
    CREATE_CREATIVE = "create_creative"
    MUTATE_CREATIVE = "mutate_creative"
    PROMOTE_WINNER = "promote_winner"

    # UA
    SCALE_CAMPAIGN = "scale_campaign"
    REDUCE_BUDGET = "reduce_budget"
    PAUSE_CAMPAIGN = "pause_campaign"

    # Experiment
    START_EXPERIMENT = "start_experiment"
    END_EXPERIMENT = "end_experiment"

    # Evolution
    CREATE_VARIANTS = "create_variants"
    DIVERSIFY_POPULATION = "diversify_population"

    # No-op
    HOLD = "hold"


class ActionSource(str, Enum):
    """动作来源."""
    EVOLUTION_SIGNAL = "evolution_signal"       # 来自 E14.6.3 EvolutionSignal
    GROWTH_OPPORTUNITY = "growth_opportunity"   # 来自 E13 GrowthOpportunity
    MANUAL = "manual"                           # 人工触发


class ActionStatus(str, Enum):
    """动作执行状态."""
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ActionPriority(int, Enum):
    """动作优先级 (数值越小越优先)."""
    CRITICAL = 1    # 立即执行 (紧急止损/高收益)
    HIGH = 2        # 高优先级
    MEDIUM = 3      # 中优先级
    LOW = 4         # 低优先级
    OPTIONAL = 5    # 可选


# ═══════════════════════════════════════════════════════════
# 信号 → 动作 路由矩阵
# ═══════════════════════════════════════════════════════════

SIGNAL_TO_ACTION: dict[SignalAction, GrowthActionType] = {
    SignalAction.AMPLIFY: GrowthActionType.PROMOTE_WINNER,
    SignalAction.SUPPRESS: GrowthActionType.REDUCE_BUDGET,
    SignalAction.EXPLORE: GrowthActionType.CREATE_VARIANTS,
    SignalAction.RETEST: GrowthActionType.START_EXPERIMENT,
    SignalAction.MAINTAIN: GrowthActionType.HOLD,
}

# 信号 → 备选动作 (当主动作不可用时)
SIGNAL_TO_FALLBACK: dict[SignalAction, list[GrowthActionType]] = {
    SignalAction.AMPLIFY: [GrowthActionType.SCALE_CAMPAIGN, GrowthActionType.CREATE_VARIANTS],
    SignalAction.SUPPRESS: [GrowthActionType.PAUSE_CAMPAIGN, GrowthActionType.HOLD],
    SignalAction.EXPLORE: [GrowthActionType.DIVERSIFY_POPULATION, GrowthActionType.MUTATE_CREATIVE],
    SignalAction.RETEST: [GrowthActionType.END_EXPERIMENT, GrowthActionType.CREATE_VARIANTS],
    SignalAction.MAINTAIN: [GrowthActionType.HOLD],
}

# 动作类型 → 执行器映射
ACTION_TO_EXECUTOR: dict[GrowthActionType, str] = {
    GrowthActionType.CREATE_CREATIVE: "CreativeExecutor",
    GrowthActionType.MUTATE_CREATIVE: "CreativeExecutor",
    GrowthActionType.PROMOTE_WINNER: "CreativeExecutor",
    GrowthActionType.SCALE_CAMPAIGN: "MetaAdsExecutor",
    GrowthActionType.REDUCE_BUDGET: "BudgetExecutor",
    GrowthActionType.PAUSE_CAMPAIGN: "MetaAdsExecutor",
    GrowthActionType.START_EXPERIMENT: "ExperimentExecutor",
    GrowthActionType.END_EXPERIMENT: "ExperimentExecutor",
    GrowthActionType.CREATE_VARIANTS: "EvolutionExecutor",
    GrowthActionType.DIVERSIFY_POPULATION: "EvolutionExecutor",
    GrowthActionType.HOLD: "NoOpExecutor",
}


# ═══════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════

@dataclass
class GrowthAction:
    """统一增长执行命令.

    代表一个可执行的增长动作，由 Router 根据 EvolutionSignal + GrowthOpportunity + Reality Context 生成.

    例如:
        GrowthAction(
            action_type=GrowthActionType.PROMOTE_WINNER,
            target_id="genome_123",
            priority=ActionPriority.HIGH,
            confidence=0.91,
            payload={"budget_multiplier": 2.0},
            expected_reward=0.15,
        )

    Attributes:
        action_id: 动作 ID
        action_type: 动作类型
        source: 动作来源
        source_signal_id: 来源 EvolutionSignal ID
        source_opportunity_id: 来源 GrowthOpportunity ID
        target_id: 目标 ID (genome_id / campaign_id / experiment_id)
        target_type: 目标类型
        priority: 优先级
        confidence: 置信度
        payload: 执行参数
        expected_reward: 预期奖励
        executor: 目标执行器
        status: 执行状态
        reasoning: 路由决策理由
        created_at: 创建时间
        metadata: 扩展元数据
    """
    action_id: str = field(default_factory=lambda: f"ga_{uuid.uuid4().hex[:8]}")
    action_type: GrowthActionType = GrowthActionType.HOLD
    source: ActionSource = ActionSource.EVOLUTION_SIGNAL
    source_signal_id: str = ""
    source_opportunity_id: str = ""
    target_id: str = ""
    target_type: str = ""
    priority: ActionPriority = ActionPriority.MEDIUM
    confidence: float = 0.0
    payload: dict[str, Any] = field(default_factory=dict)
    expected_reward: float = 0.0
    executor: str = ""
    status: ActionStatus = ActionStatus.PENDING
    reasoning: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.executor:
            self.executor = ACTION_TO_EXECUTOR.get(self.action_type, "NoOpExecutor")

    @property
    def is_critical(self) -> bool:
        return self.priority == ActionPriority.CRITICAL

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.8

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "source": self.source.value,
            "source_signal_id": self.source_signal_id,
            "source_opportunity_id": self.source_opportunity_id,
            "target_id": self.target_id,
            "target_type": self.target_type,
            "priority": self.priority.value,
            "priority_name": self.priority.name,
            "confidence": round(self.confidence, 4),
            "payload": self.payload,
            "expected_reward": round(self.expected_reward, 4),
            "executor": self.executor,
            "status": self.status.value,
            "reasoning": self.reasoning,
            "is_critical": self.is_critical,
            "is_high_confidence": self.is_high_confidence,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GrowthAction:
        return cls(
            action_id=data.get("action_id", ""),
            action_type=GrowthActionType(data.get("action_type", "hold")),
            source=ActionSource(data.get("source", "evolution_signal")),
            source_signal_id=data.get("source_signal_id", ""),
            source_opportunity_id=data.get("source_opportunity_id", ""),
            target_id=data.get("target_id", ""),
            target_type=data.get("target_type", ""),
            priority=ActionPriority(data.get("priority", 3)),
            confidence=data.get("confidence", 0.0),
            payload=data.get("payload", {}),
            expected_reward=data.get("expected_reward", 0.0),
            executor=data.get("executor", ""),
            status=ActionStatus(data.get("status", "pending")),
            reasoning=data.get("reasoning", ""),
            created_at=data.get("created_at", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class RouteResult:
    """路由结果 — 包含动作和路由元数据.

    Attributes:
        action: 生成的动作
        signal_matched: 是否匹配到信号
        opportunity_boosted: 是否被 Opportunity 增强
        fallback_used: 是否使用了备选动作
        validation_passed: 是否通过验证
        route_score: 路由评分
    """
    action: GrowthAction
    signal_matched: bool = True
    opportunity_boosted: bool = False
    fallback_used: bool = False
    validation_passed: bool = True
    route_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.to_dict(),
            "signal_matched": self.signal_matched,
            "opportunity_boosted": self.opportunity_boosted,
            "fallback_used": self.fallback_used,
            "validation_passed": self.validation_passed,
            "route_score": round(self.route_score, 4),
        }


# ═══════════════════════════════════════════════════════════
# GrowthActionRouter — 核心路由器
# ═══════════════════════════════════════════════════════════

class GrowthActionRouter:
    """增长动作路由器 — Signal + Opportunity + Context → GrowthAction.

    核心职责:
      1. 将 EvolutionSignal 映射为 GrowthAction
      2. 融合 GrowthOpportunity 的优先级和紧急度
      3. 批量路由与优先级排序
      4. 动作验证
      5. 统计与监控

    用法:
        router = GrowthActionRouter()
        action = router.route(signal)
        print(f"路由: {signal.action.value} → {action.action_type.value}")
    """

    # 默认配置
    DEFAULT_MIN_CONFIDENCE = 0.3       # 最低置信度阈值
    DEFAULT_AUTO_APPROVE_CONFIDENCE = 0.85  # 自动批准阈值
    DEFAULT_MAX_BUDGET_MULTIPLIER = 3.0    # 最大预算倍数
    DEFAULT_MAX_CONCURRENT_ACTIONS = 10     # 最大并发动作数

    def __init__(
        self,
        min_confidence: float = 0.3,
        auto_approve_confidence: float = 0.85,
        max_budget_multiplier: float = 3.0,
        max_concurrent_actions: int = 10,
    ):
        self._min_confidence = min_confidence
        self._auto_approve_confidence = auto_approve_confidence
        self._max_budget_multiplier = max_budget_multiplier
        self._max_concurrent_actions = max_concurrent_actions
        self._actions: dict[str, GrowthAction] = {}
        self._route_history: list[RouteResult] = []

    # ── 核心: 单信号路由 ─────────────────────────────────

    def route(
        self,
        signal: EvolutionSignal,
        opportunity: Any = None,
        context: dict[str, Any] | None = None,
        target_id: str = "",
        target_type: str = "",
    ) -> RouteResult:
        """将 EvolutionSignal 路由为 GrowthAction.

        Args:
            signal: E14.6.3 进化信号
            opportunity: (可选) E13 GrowthOpportunity
            context: (可选) Reality Context {roas, ctr, fatigue, ...}
            target_id: 目标 ID (genome_id / campaign_id / experiment_id)
            target_type: 目标类型

        Returns:
            RouteResult: 包含 GrowthAction 和路由元数据
        """
        context = context or {}
        fallback_used = False

        # Step 1: 信号 → 动作映射
        action_type = SIGNAL_TO_ACTION.get(signal.action, GrowthActionType.HOLD)

        # Step 2: 置信度低于阈值时降级
        if signal.confidence < self._min_confidence:
            # 尝试备选动作
            fallbacks = SIGNAL_TO_FALLBACK.get(signal.action, [GrowthActionType.HOLD])
            action_type = fallbacks[0] if fallbacks else GrowthActionType.HOLD
            fallback_used = True

        # Step 3: 构建 payload
        payload = self._build_payload(action_type, signal, context)

        # Step 4: 计算优先级
        priority = self._calculate_priority(signal, opportunity, context)

        # Step 5: 计算预期奖励
        expected_reward = self._estimate_reward(signal, action_type, context)

        # Step 6: 生成理由
        reasoning = self._generate_reasoning(signal, action_type, fallback_used)

        # Step 7: 创建动作
        action = GrowthAction(
            action_type=action_type,
            source=ActionSource.EVOLUTION_SIGNAL,
            source_signal_id=signal.signal_id,
            source_opportunity_id=getattr(opportunity, "opportunity_id", ""),
            target_id=target_id or signal.target_value,
            target_type=target_type or "genome",
            priority=priority,
            confidence=signal.confidence,
            payload=payload,
            expected_reward=expected_reward,
            reasoning=reasoning,
            metadata={
                "gene_category": signal.gene_category,
                "source_experiment_id": signal.source_experiment_id,
                "context": context,
            },
        )

        # Step 8: Opportunity 增强
        opportunity_boosted = False
        if opportunity is not None:
            self._apply_opportunity_boost(action, opportunity)
            opportunity_boosted = True

        # Step 9: 验证
        validation_passed = self.validate(action)

        # Step 10: 存储
        self._actions[action.action_id] = action

        route_score = self._calculate_route_score(action, validation_passed)

        result = RouteResult(
            action=action,
            signal_matched=True,
            opportunity_boosted=opportunity_boosted,
            fallback_used=fallback_used,
            validation_passed=validation_passed,
            route_score=route_score,
        )
        self._route_history.append(result)

        return result

    # ── 批量路由 ─────────────────────────────────────────

    def route_batch(
        self,
        signals: list[EvolutionSignal],
        opportunity: Any = None,
        context: dict[str, Any] | None = None,
    ) -> list[RouteResult]:
        """批量路由多个信号.

        Args:
            signals: 多个 EvolutionSignal
            opportunity: 共享的 GrowthOpportunity
            context: 共享的 Reality Context

        Returns:
            list[RouteResult]: 按优先级排序的路由结果
        """
        results: list[RouteResult] = []
        for signal in signals:
            result = self.route(signal, opportunity=opportunity, context=context)
            results.append(result)

        # 按优先级排序 (CRITICAL > HIGH > MEDIUM > LOW > OPTIONAL)
        results.sort(key=lambda r: (r.action.priority.value, -r.action.confidence))

        # 限制并发数
        if len(results) > self._max_concurrent_actions:
            results = results[:self._max_concurrent_actions]

        return results

    # ── 验证 ─────────────────────────────────────────────

    def validate(self, action: GrowthAction) -> bool:
        """验证动作是否合法.

        检查项:
          1. 置信度是否足够
          2. budget_multiplier 是否在合理范围
          3. 动作类型是否合法
          4. 目标 ID 是否非空

        Args:
            action: 待验证动作

        Returns:
            bool: 是否通过验证
        """
        # 1. HOLD 总是合法
        if action.action_type == GrowthActionType.HOLD:
            return True

        # 2. 置信度检查
        if action.confidence < self._min_confidence:
            return False

        # 3. Budget multiplier 检查
        budget_mult = action.payload.get("budget_multiplier", 1.0)
        if budget_mult > self._max_budget_multiplier:
            return False
        if budget_mult <= 0:
            return False

        # 4. 目标 ID 检查 (HOLD 和 DIVERSIFY_POPULATION 可以没有目标)
        actions_requiring_target = {
            GrowthActionType.PROMOTE_WINNER,
            GrowthActionType.SCALE_CAMPAIGN,
            GrowthActionType.REDUCE_BUDGET,
            GrowthActionType.PAUSE_CAMPAIGN,
            GrowthActionType.START_EXPERIMENT,
            GrowthActionType.END_EXPERIMENT,
            GrowthActionType.MUTATE_CREATIVE,
            GrowthActionType.CREATE_CREATIVE,
        }
        if action.action_type in actions_requiring_target and not action.target_id:
            return False

        return True

    # ── 查询 ─────────────────────────────────────────────

    def get_action(self, action_id: str) -> GrowthAction | None:
        """获取动作."""
        return self._actions.get(action_id)

    def get_actions_by_type(self, action_type: GrowthActionType) -> list[GrowthAction]:
        """按类型获取动作."""
        return [a for a in self._actions.values() if a.action_type == action_type]

    def get_actions_by_priority(self, priority: ActionPriority) -> list[GrowthAction]:
        """按优先级获取动作."""
        return [a for a in self._actions.values() if a.priority == priority]

    def get_actions_by_executor(self, executor: str) -> list[GrowthAction]:
        """按执行器获取动作."""
        return [a for a in self._actions.values() if a.executor == executor]

    def get_pending_actions(self) -> list[GrowthAction]:
        """获取待执行动作."""
        return [a for a in self._actions.values() if a.status == ActionStatus.PENDING]

    def get_route_history(self) -> list[RouteResult]:
        """获取路由历史."""
        return list(self._route_history)

    # ── 内部方法 ─────────────────────────────────────────

    def _build_payload(
        self,
        action_type: GrowthActionType,
        signal: EvolutionSignal,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """根据动作类型构建 payload."""
        payload: dict[str, Any] = {
            "signal_action": signal.action.value,
            "gene_category": signal.gene_category,
            "source_experiment_id": signal.source_experiment_id,
        }

        if action_type == GrowthActionType.PROMOTE_WINNER:
            payload["budget_multiplier"] = min(1.0 + signal.confidence * 2.0, self._max_budget_multiplier)
            payload["scale_reason"] = signal.expected_impact

        elif action_type == GrowthActionType.REDUCE_BUDGET:
            payload["budget_multiplier"] = max(0.2, 1.0 - signal.confidence * 0.8)
            payload["reduce_reason"] = signal.expected_impact

        elif action_type == GrowthActionType.PAUSE_CAMPAIGN:
            payload["reason"] = signal.expected_impact
            payload["auto_resume_days"] = 7

        elif action_type == GrowthActionType.START_EXPERIMENT:
            payload["experiment_name"] = f"Retest: {signal.gene_category}"
            payload["hypothesis"] = signal.expected_impact
            payload["duration_days"] = 7
            payload["budget"] = context.get("default_experiment_budget", 100.0)

        elif action_type == GrowthActionType.CREATE_VARIANTS:
            payload["variant_count"] = max(2, int(signal.confidence * 5))
            payload["exploration_direction"] = signal.gene_category
            payload["exploration_reason"] = signal.expected_impact

        elif action_type == GrowthActionType.SCALE_CAMPAIGN:
            payload["budget_multiplier"] = min(1.0 + signal.confidence * 1.5, self._max_budget_multiplier)
            payload["scale_reason"] = signal.expected_impact

        elif action_type == GrowthActionType.DIVERSIFY_POPULATION:
            payload["diversity_target"] = signal.gene_category
            payload["count"] = max(3, int(signal.confidence * 8))

        # 注入 context
        if context:
            payload["context"] = context

        return payload

    def _calculate_priority(
        self,
        signal: EvolutionSignal,
        opportunity: Any,
        context: dict[str, Any],
    ) -> ActionPriority:
        """计算动作优先级.

        优先级 = f(信号置信度, opportunity 紧急度, context 信号)
        """
        score = signal.confidence

        # Opportunity 加成
        if opportunity is not None:
            urgency = getattr(opportunity, "urgency", 0.0)
            opp_priority = getattr(opportunity, "priority", None)
            if opp_priority is not None:
                opp_priority_val = getattr(opp_priority, "value", 3)
                score += (5 - opp_priority_val) * 0.1
            score += urgency * 0.2

        # Context 加成: 高 ROAS 时提升优先级
        if context:
            roas = context.get("roas", 0.0)
            if roas > 2.0:
                score += 0.2
            elif roas > 1.5:
                score += 0.1

        # 信号类型加成
        if signal.action == SignalAction.AMPLIFY:
            score += 0.1
        elif signal.action == SignalAction.SUPPRESS:
            score += 0.15  # 止损优先

        if score >= 0.9:
            return ActionPriority.CRITICAL
        elif score >= 0.7:
            return ActionPriority.HIGH
        elif score >= 0.5:
            return ActionPriority.MEDIUM
        elif score >= 0.3:
            return ActionPriority.LOW
        else:
            return ActionPriority.OPTIONAL

    def _estimate_reward(
        self,
        signal: EvolutionSignal,
        action_type: GrowthActionType,
        context: dict[str, Any],
    ) -> float:
        """估算动作的预期奖励."""
        base_reward = signal.confidence * 0.1

        if action_type == GrowthActionType.PROMOTE_WINNER:
            base_reward *= 1.5
        elif action_type == GrowthActionType.REDUCE_BUDGET:
            base_reward *= 0.8  # 止损也有价值
        elif action_type == GrowthActionType.START_EXPERIMENT:
            base_reward *= 0.6  # 实验价值较不确定
        elif action_type == GrowthActionType.HOLD:
            base_reward = 0.0

        return round(base_reward, 4)

    def _generate_reasoning(
        self,
        signal: EvolutionSignal,
        action_type: GrowthActionType,
        fallback_used: bool,
    ) -> str:
        """生成路由决策理由."""
        reason = f"Signal={signal.action.value}(conf={signal.confidence:.2f})"
        if signal.gene_category:
            reason += f", gene={signal.gene_category}"
        reason += f" → {action_type.value}"
        if fallback_used:
            reason += " (fallback, 置信度不足)"
        return reason

    def _apply_opportunity_boost(self, action: GrowthAction, opportunity: Any) -> None:
        """应用 GrowthOpportunity 增强."""
        urgency = getattr(opportunity, "urgency", 0.0)
        opp_confidence = getattr(opportunity, "confidence", 0.0)

        # 提升置信度
        if opp_confidence > action.confidence:
            action.confidence = min(action.confidence + opp_confidence * 0.2, 1.0)

        # 提升优先级
        if urgency > 0.8:
            if action.priority.value > ActionPriority.HIGH.value:
                action.priority = ActionPriority.HIGH

        # 融合 payload
        opp_impact = getattr(opportunity, "expected_impact", None)
        if opp_impact is not None:
            action.metadata["opportunity_impact"] = opp_impact.to_dict() if hasattr(opp_impact, "to_dict") else str(opp_impact)

        reason = getattr(opportunity, "reason", "")
        if reason:
            action.reasoning += f" | Opportunity: {reason}"

        action.source_opportunity_id = getattr(opportunity, "opportunity_id", "")

    def _calculate_route_score(self, action: GrowthAction, validation_passed: bool) -> float:
        """计算路由评分."""
        if not validation_passed:
            return 0.0
        score = action.confidence * 0.5
        score += (6 - action.priority.value) / 5 * 0.3
        score += action.expected_reward * 2 * 0.2
        return round(min(score, 1.0), 4)

    # ── 统计 ─────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """获取路由器统计."""
        by_type: dict[str, int] = {}
        by_executor: dict[str, int] = {}
        by_priority: dict[str, int] = {}

        for action in self._actions.values():
            t = action.action_type.value
            by_type[t] = by_type.get(t, 0) + 1
            e = action.executor
            by_executor[e] = by_executor.get(e, 0) + 1
            p = action.priority.name
            by_priority[p] = by_priority.get(p, 0) + 1

        return {
            "total_actions": len(self._actions),
            "total_routes": len(self._route_history),
            "pending": len(self.get_pending_actions()),
            "by_type": by_type,
            "by_executor": by_executor,
            "by_priority": by_priority,
            "avg_confidence": round(
                sum(a.confidence for a in self._actions.values()) / max(len(self._actions), 1), 4
            ),
            "fallback_rate": round(
                sum(1 for r in self._route_history if r.fallback_used) / max(len(self._route_history), 1), 4
            ),
            "validation_pass_rate": round(
                sum(1 for r in self._route_history if r.validation_passed) / max(len(self._route_history), 1), 4
            ),
        }

    def reset(self) -> None:
        """重置所有状态."""
        self._actions.clear()
        self._route_history.clear()


# ═══════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════

def create_growth_action_router(
    min_confidence: float = 0.3,
    auto_approve_confidence: float = 0.85,
    max_budget_multiplier: float = 3.0,
    max_concurrent_actions: int = 10,
) -> GrowthActionRouter:
    """创建默认 GrowthActionRouter."""
    return GrowthActionRouter(
        min_confidence=min_confidence,
        auto_approve_confidence=auto_approve_confidence,
        max_budget_multiplier=max_budget_multiplier,
        max_concurrent_actions=max_concurrent_actions,
    )