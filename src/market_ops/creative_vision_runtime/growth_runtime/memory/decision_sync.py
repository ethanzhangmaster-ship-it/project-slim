"""E13.6.5 Decision Memory Synchronization — 决策记忆同步.

解决双记忆系统问题 (Decision Memory vs Pattern Memory):

之前:
  Pattern Memory ← Pattern Feedback ← Execution Result
  Decision Memory ← Decision Engine ← Opportunity
  两个系统独立学习，可能产生冲突推荐。

之后:
  Decision Memory ↕ Pattern Memory (双向同步)

模块:
  - DecisionMemoryEvent: 决策执行结果→统一记忆事件
  - DecisionOutcomeBridge: 决策结果→记忆事件转换
  - PatternDecisionReconciler: 预测 vs 实际对齐
  - DecisionPatternSynchronizer: 双向同步编排

同步规则:
  Rule 1 (成功反馈): reward > 0.5 AND success → Pattern confidence↑, avg_reward↑
  Rule 2 (失败反馈): reward < 0 → Pattern confidence↓, risk_score↑
  Rule 3 (连续失败保护): 最近N次失败率 > 80% → ACTIVE → DECAYING
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .models import PatternMemory


# ═══════════════════════════════════════════════════════════════
# DecisionMemoryEvent
# ═══════════════════════════════════════════════════════════════


class SyncEventType(str, Enum):
    """同步事件类型."""
    SUCCESS = "success"             # 成功执行
    FAILURE = "failure"             # 执行失败
    PARTIAL = "partial"             # 部分成功
    PREDICTION_ERROR = "prediction_error"  # 预测偏差
    CONSECUTIVE_FAILURE = "consecutive_failure"  # 连续失败


@dataclass
class DecisionMemoryEvent:
    """决策记忆事件 — 从 Decision Experience 转换的统一事件.

    将 DecisionExperience + ExecutionResult 转换成
    PatternFeedback 可以消费的标准化事件。

    Attributes:
        event_id: 事件唯一标识
        decision_id: 关联决策 ID
        opportunity_type: 机会类型
        action_type: 执行动作类型
        strategy_id: 策略 ID
        pattern_ids: 关联的模式 ID 列表
        result: 执行结果 (success/failure/partial)
        reward: 执行奖励 [-1, 1]
        confidence: 决策时置信度
        risk_score: 决策时风险评分
        metrics: 结果指标 (ROAS change, CTR change, etc.)
        success: 是否成功
        lessons: 经验教训
        timestamp: 事件时间
        metadata: 扩展元数据
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str = ""
    opportunity_type: str = ""
    action_type: str = ""
    strategy_id: str = ""
    strategy_name: str = ""
    pattern_ids: list[str] = field(default_factory=list)
    result: str = "pending"
    reward: float = 0.0
    confidence: float = 0.0
    risk_score: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)
    success: bool = False
    lessons: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.result == "success"

    @property
    def is_failure(self) -> bool:
        return self.result == "failure"

    @property
    def is_partial(self) -> bool:
        return self.result == "partial"

    @property
    def is_resolved(self) -> bool:
        return self.result != "pending"

    @property
    def event_type(self) -> SyncEventType:
        if self.result == "success":
            return SyncEventType.SUCCESS
        elif self.result == "failure":
            return SyncEventType.FAILURE
        elif self.result == "partial":
            return SyncEventType.PARTIAL
        return SyncEventType.FAILURE

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "decision_id": self.decision_id,
            "opportunity_type": self.opportunity_type,
            "action_type": self.action_type,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "pattern_ids": self.pattern_ids,
            "result": self.result,
            "reward": round(self.reward, 4),
            "confidence": round(self.confidence, 4),
            "risk_score": round(self.risk_score, 4),
            "metrics": self.metrics,
            "success": self.success,
            "lessons": self.lessons,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# DecisionOutcomeBridge
# ═══════════════════════════════════════════════════════════════


@dataclass
class BridgeResult:
    """桥接结果.

    Attributes:
        event: 生成的记忆事件
        source: 来源类型 (decision_experience / execution_outcome / raw)
        converted: 是否成功转换
        reason: 转换说明
    """
    event: DecisionMemoryEvent = field(default_factory=DecisionMemoryEvent)
    source: str = ""
    converted: bool = False
    reason: str = ""


class DecisionOutcomeBridge:
    """E13.6.5 DecisionOutcomeBridge — 决策结果→统一记忆事件.

    将不同来源的执行结果转换成标准化的 DecisionMemoryEvent，
    供 PatternDecisionReconciler 和 DecisionPatternSynchronizer 消费。

    支持的输入:
      1. DecisionExperience (from DecisionMemory)
      2. ExperienceOutcome (from Execution Layer)
      3. Raw dict (from external systems)

    用法:
        bridge = DecisionOutcomeBridge()
        event = bridge.from_decision_experience(exp)
        event = bridge.from_execution_outcome(outcome, context)
    """

    def from_decision_experience(
        self,
        exp: Any,  # DecisionExperience
        pattern_ids: list[str] | None = None,
    ) -> BridgeResult:
        """从 DecisionExperience 创建记忆事件.

        Args:
            exp: DecisionExperience 实例
            pattern_ids: 关联的模式 ID 列表

        Returns:
            BridgeResult: 桥接结果
        """
        if not hasattr(exp, "decision_id"):
            return BridgeResult(reason="Not a valid DecisionExperience")

        # 计算 reward
        reward = self._compute_reward_from_metrics(
            exp.result_metrics if hasattr(exp, "result_metrics") else {},
            exp.result if hasattr(exp, "result") else "pending",
        )

        event = DecisionMemoryEvent(
            decision_id=exp.decision_id if hasattr(exp, "decision_id") else "",
            opportunity_type=exp.opportunity_type if hasattr(exp, "opportunity_type") else "",
            action_type=self._extract_action_type(exp),
            strategy_id=exp.strategy_id if hasattr(exp, "strategy_id") else "",
            strategy_name=exp.strategy_name if hasattr(exp, "strategy_name") else "",
            pattern_ids=pattern_ids or exp.pattern_contribution.get("pattern_ids", [])
                if hasattr(exp, "pattern_contribution") and isinstance(exp.pattern_contribution, dict)
                else [],
            result=exp.result if hasattr(exp, "result") else "pending",
            reward=reward,
            confidence=exp.confidence if hasattr(exp, "confidence") else 0.0,
            risk_score=exp.risk_score if hasattr(exp, "risk_score") else 0.0,
            metrics=exp.result_metrics if hasattr(exp, "result_metrics") else {},
            success=exp.is_success if hasattr(exp, "is_success") else (exp.result == "success"),
            lessons=exp.lessons_learned if hasattr(exp, "lessons_learned") else [],
            timestamp=exp.resolved_at if hasattr(exp, "resolved_at") and exp.resolved_at
                else exp.created_at if hasattr(exp, "created_at") else datetime.now(timezone.utc).isoformat(),
        )

        return BridgeResult(
            event=event,
            source="decision_experience",
            converted=True,
            reason=f"Converted DecisionExperience {event.decision_id}",
        )

    def from_execution_outcome(
        self,
        outcome: Any,
        context: dict[str, Any] | None = None,
    ) -> BridgeResult:
        """从执行结果创建记忆事件.

        Args:
            outcome: ExperienceOutcome 或类似对象
            context: 决策上下文 (decision_id, opportunity_type, etc.)

        Returns:
            BridgeResult: 桥接结果
        """
        ctx = context or {}

        metrics = {}
        if hasattr(outcome, "metrics_delta") and isinstance(outcome.metrics_delta, dict):
            metrics = outcome.metrics_delta
        elif hasattr(outcome, "to_dict"):
            d = outcome.to_dict()
            metrics = d.get("metrics_delta", d.get("metrics_after", {}))

        success = outcome.success if hasattr(outcome, "success") else False
        result = "success" if success else "failure"

        reward = self._compute_reward_from_metrics(metrics, result)

        event = DecisionMemoryEvent(
            decision_id=ctx.get("decision_id", ""),
            opportunity_type=ctx.get("opportunity_type", ""),
            action_type=ctx.get("action_type", ""),
            strategy_id=ctx.get("strategy_id", ""),
            strategy_name=ctx.get("strategy_name", ""),
            pattern_ids=ctx.get("pattern_ids", []),
            result=result,
            reward=reward,
            confidence=ctx.get("confidence", 0.0),
            risk_score=ctx.get("risk_score", 0.0),
            metrics=metrics,
            success=success,
            lessons=ctx.get("lessons", []),
        )

        return BridgeResult(
            event=event,
            source="execution_outcome",
            converted=True,
            reason=f"Converted execution outcome (success={success})",
        )

    def from_raw_dict(
        self,
        data: dict[str, Any],
    ) -> BridgeResult:
        """从原始字典创建记忆事件."""
        event = DecisionMemoryEvent(
            decision_id=data.get("decision_id", ""),
            opportunity_type=data.get("opportunity_type", ""),
            action_type=data.get("action_type", ""),
            strategy_id=data.get("strategy_id", ""),
            strategy_name=data.get("strategy_name", ""),
            pattern_ids=data.get("pattern_ids", []),
            result=data.get("result", "pending"),
            reward=data.get("reward", 0.0),
            confidence=data.get("confidence", 0.0),
            risk_score=data.get("risk_score", 0.0),
            metrics=data.get("metrics", {}),
            success=data.get("success", False),
            lessons=data.get("lessons", []),
            metadata=data.get("metadata", {}),
        )

        return BridgeResult(
            event=event,
            source="raw_dict",
            converted=True,
            reason="Converted from raw dict",
        )

    def _compute_reward_from_metrics(
        self,
        metrics: dict[str, Any],
        result: str,
    ) -> float:
        """从指标计算奖励信号."""
        if result == "failure":
            return -1.0

        if not metrics:
            return 0.0

        # 简化版奖励计算
        reward = 0.0
        count = 0

        roas = metrics.get("roas_change", metrics.get("roas", 0))
        if isinstance(roas, (int, float)) and roas != 0:
            reward += 1.0 if roas > 0 else -0.5
            count += 1

        ctr = metrics.get("ctr_change", metrics.get("ctr", 0))
        if isinstance(ctr, (int, float)) and ctr != 0:
            reward += 0.5 if ctr > 0 else -0.3
            count += 1

        return round(reward / max(count, 1), 4)

    def _extract_action_type(self, exp: Any) -> str:
        """从 DecisionExperience 提取动作类型."""
        if hasattr(exp, "action_plan") and isinstance(exp.action_plan, dict):
            return exp.action_plan.get("action_type", "")
        if hasattr(exp, "action_type"):
            return exp.action_type
        return ""


# ═══════════════════════════════════════════════════════════════
# PatternDecisionReconciler
# ═══════════════════════════════════════════════════════════════


@dataclass
class PredictionGap:
    """预测差距 — 模式预测 vs 实际结果.

    Attributes:
        pattern_id: 模式ID
        expected_success_rate: 模式预测成功率
        actual_success_rate: 实际成功率
        gap: 预测差距 (expected - actual)
        gap_severity: 差距严重程度 (low/medium/high/critical)
        recent_samples: 最近样本数
        recommendation: 建议动作 (penalty/boost/noop)
    """
    pattern_id: str = ""
    expected_success_rate: float = 0.0
    actual_success_rate: float = 0.0
    gap: float = 0.0
    gap_severity: str = "low"
    recent_samples: int = 0
    recommendation: str = "noop"


@dataclass
class ReconciliationAction:
    """对齐动作 — 对 Pattern 的调整建议.

    Attributes:
        pattern_id: 模式ID
        action_type: 动作类型 (boost/penalty/decay/noop)
        confidence_adjustment: 置信度调整
        success_rate_adjustment: 成功率调整
        reward_adjustment: 奖励调整
        reason: 调整原因
        severity: 严重程度
    """
    pattern_id: str = ""
    action_type: str = "noop"
    confidence_adjustment: float = 0.0
    success_rate_adjustment: float = 0.0
    reward_adjustment: float = 0.0
    reason: str = ""
    severity: str = "low"


@dataclass
class ReconciliationResult:
    """对齐结果.

    Attributes:
        events_processed: 处理的事件数
        gaps: 预测差距列表
        actions: 对齐动作列表
        summary: 结果摘要
    """
    events_processed: int = 0
    gaps: list[PredictionGap] = field(default_factory=list)
    actions: list[ReconciliationAction] = field(default_factory=list)
    summary: str = ""


class PatternDecisionReconciler:
    """E13.6.5 PatternDecisionReconciler — 预测 vs 实际对齐.

    比较 Pattern 预测与真实决策结果，计算预测差距，
    生成对齐动作 (对 Pattern 的调整建议)。

    核心逻辑:
      1. 从 DecisionMemoryEvent 收集实际结果
      2. 与 Pattern 的 expected_success_rate 比较
      3. 计算预测差距
      4. 生成 boost/penalty/decay 动作

    差距严重程度:
      gap < 0.15 → low
      gap < 0.30 → medium
      gap < 0.50 → high
      gap >= 0.50 → critical

    用法:
        reconciler = PatternDecisionReconciler()
        result = reconciler.reconcile(pattern, events)
        for action in result.actions:
            pattern.confidence += action.confidence_adjustment
    """

    # 差距阈值
    LOW_GAP = 0.15
    MEDIUM_GAP = 0.30
    HIGH_GAP = 0.50

    # 调整参数
    LOW_PENALTY = -0.05
    MEDIUM_PENALTY = -0.10
    HIGH_PENALTY = -0.20
    CRITICAL_PENALTY = -0.35

    LOW_BOOST = +0.03
    MEDIUM_BOOST = +0.06
    HIGH_BOOST = +0.10

    # 连续失败阈值
    CONSECUTIVE_FAILURE_WINDOW = 10
    CONSECUTIVE_FAILURE_THRESHOLD = 0.80  # 80% 失败率

    def __init__(self):
        pass

    def reconcile(
        self,
        pattern: PatternMemory,
        events: list[DecisionMemoryEvent],
    ) -> ReconciliationResult:
        """对齐单个模式与实际结果.

        Args:
            pattern: 模式
            events: 与该模式相关的决策记忆事件

        Returns:
            ReconciliationResult: 对齐结果
        """
        result = ReconciliationResult()

        if not events:
            result.summary = "No events to reconcile."
            return result

        # 过滤已决事件
        resolved = [e for e in events if e.is_resolved]
        if not resolved:
            result.summary = "No resolved events to reconcile."
            return result

        result.events_processed = len(resolved)

        # 计算实际成功率
        actual_successes = sum(1 for e in resolved if e.is_success)
        actual_rate = actual_successes / len(resolved) if resolved else 0.0

        # 计算预测差距
        expected_rate = pattern.performance.success_rate
        gap = expected_rate - actual_rate

        # 评估差距严重程度
        severity = self._assess_severity(abs(gap))

        prediction_gap = PredictionGap(
            pattern_id=pattern.pattern_id,
            expected_success_rate=round(expected_rate, 4),
            actual_success_rate=round(actual_rate, 4),
            gap=round(gap, 4),
            gap_severity=severity,
            recent_samples=len(resolved),
            recommendation="noop",
        )
        result.gaps.append(prediction_gap)

        # 生成对齐动作
        action = self._generate_action(pattern, prediction_gap, resolved)
        if action is not None:
            result.actions.append(action)
            prediction_gap.recommendation = action.action_type

        # 检查连续失败
        consecutive_failure_action = self._check_consecutive_failures(
            pattern, resolved,
        )
        if consecutive_failure_action is not None:
            result.actions.append(consecutive_failure_action)

        result.summary = self._generate_summary(result)
        return result

    def evaluate_prediction_gap(
        self,
        pattern: PatternMemory,
        actual_success_rate: float,
        sample_count: int,
    ) -> PredictionGap:
        """评估单个模式的预测差距.

        Args:
            pattern: 模式
            actual_success_rate: 实际成功率
            sample_count: 样本数

        Returns:
            PredictionGap: 预测差距
        """
        expected = pattern.performance.success_rate
        gap = expected - actual_success_rate
        severity = self._assess_severity(abs(gap))

        rec = "noop"
        if gap > 0.15:
            rec = "penalty"
        elif gap < -0.10:
            rec = "boost"

        return PredictionGap(
            pattern_id=pattern.pattern_id,
            expected_success_rate=round(expected, 4),
            actual_success_rate=round(actual_success_rate, 4),
            gap=round(gap, 4),
            gap_severity=severity,
            recent_samples=sample_count,
            recommendation=rec,
        )

    def apply_feedback(
        self,
        pattern: PatternMemory,
        action: ReconciliationAction,
    ) -> PatternMemory:
        """将对齐动作应用到模式上.

        Args:
            pattern: 模式
            action: 对齐动作

        Returns:
            PatternMemory: 更新后的模式
        """
        if action.action_type == "noop":
            return pattern

        # 更新置信度
        pattern.confidence = round(
            max(0.0, min(1.0, pattern.confidence + action.confidence_adjustment)),
            4,
        )

        # 更新成功率
        if action.success_rate_adjustment != 0.0:
            pattern.performance.success_rate = round(
                max(0.0, min(1.0, pattern.performance.success_rate + action.success_rate_adjustment)),
                4,
            )

        # 更新奖励
        if action.reward_adjustment != 0.0:
            pattern.performance.avg_reward = round(
                max(-1.0, min(1.0, pattern.performance.avg_reward + action.reward_adjustment)),
                4,
            )

        # 重新计算评分
        pattern.compute_score()

        # 记录对齐历史
        pattern.metadata["last_reconciliation"] = {
            "action_type": action.action_type,
            "confidence_adjustment": action.confidence_adjustment,
            "reason": action.reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return pattern

    def generate_sync_actions(
        self,
        patterns: list[PatternMemory],
        event_groups: dict[str, list[DecisionMemoryEvent]],
    ) -> list[ReconciliationAction]:
        """为多个模式批量生成对齐动作.

        Args:
            patterns: 模式列表
            event_groups: pattern_id → events 映射

        Returns:
            list[ReconciliationAction]: 对齐动作列表
        """
        actions: list[ReconciliationAction] = []
        for pattern in patterns:
            events = event_groups.get(pattern.pattern_id, [])
            if events:
                result = self.reconcile(pattern, events)
                actions.extend(result.actions)
        return actions

    def _assess_severity(self, abs_gap: float) -> str:
        """评估差距严重程度."""
        if abs_gap >= self.HIGH_GAP:
            return "critical"
        elif abs_gap >= self.MEDIUM_GAP:
            return "high"
        elif abs_gap >= self.LOW_GAP:
            return "medium"
        return "low"

    def _generate_action(
        self,
        pattern: PatternMemory,
        gap: PredictionGap,
        events: list[DecisionMemoryEvent],
    ) -> ReconciliationAction | None:
        """根据预测差距生成对齐动作."""
        if abs(gap.gap) < self.LOW_GAP:
            return None  # 差距太小，不需要调整

        # 模式预测过高 (过度乐观)
        if gap.gap > 0:
            penalty = self._get_penalty(gap.gap_severity)
            return ReconciliationAction(
                pattern_id=pattern.pattern_id,
                action_type="penalty",
                confidence_adjustment=penalty,
                success_rate_adjustment=-abs(gap.gap) * 0.3,
                reward_adjustment=penalty * 0.5,
                reason=f"Pattern over-predicted: expected {gap.expected_success_rate:.2%}, "
                       f"actual {gap.actual_success_rate:.2%}, gap={gap.gap:.2%}",
                severity=gap.gap_severity,
            )

        # 模式预测过低 (过于保守) → boost
        boost = self._get_boost(gap.gap_severity)
        return ReconciliationAction(
            pattern_id=pattern.pattern_id,
            action_type="boost",
            confidence_adjustment=boost,
            success_rate_adjustment=abs(gap.gap) * 0.2,
            reward_adjustment=boost * 0.5,
            reason=f"Pattern under-predicted: expected {gap.expected_success_rate:.2%}, "
                   f"actual {gap.actual_success_rate:.2%}, gap={gap.gap:.2%}",
            severity=gap.gap_severity,
        )

    def _check_consecutive_failures(
        self,
        pattern: PatternMemory,
        events: list[DecisionMemoryEvent],
    ) -> ReconciliationAction | None:
        """检查连续失败 (Rule 3)."""
        recent = events[-self.CONSECUTIVE_FAILURE_WINDOW:]
        if len(recent) < self.CONSECUTIVE_FAILURE_WINDOW:
            return None

        failures = sum(1 for e in recent if e.is_failure)
        failure_rate = failures / len(recent)

        if failure_rate >= self.CONSECUTIVE_FAILURE_THRESHOLD:
            return ReconciliationAction(
                pattern_id=pattern.pattern_id,
                action_type="decay",
                confidence_adjustment=-0.30,
                success_rate_adjustment=-0.15,
                reward_adjustment=-0.30,
                reason=f"Consecutive failure: {failures}/{len(recent)} failures "
                       f"({failure_rate:.0%}) in last {len(recent)} executions",
                severity="high",
            )

        return None

    def _get_penalty(self, severity: str) -> float:
        return {
            "low": self.LOW_PENALTY,
            "medium": self.MEDIUM_PENALTY,
            "high": self.HIGH_PENALTY,
            "critical": self.CRITICAL_PENALTY,
        }.get(severity, self.LOW_PENALTY)

    def _get_boost(self, severity: str) -> float:
        return {
            "low": self.LOW_BOOST,
            "medium": self.MEDIUM_BOOST,
            "high": self.HIGH_BOOST,
            "critical": self.HIGH_BOOST,
        }.get(severity, self.LOW_BOOST)

    def _generate_summary(self, result: ReconciliationResult) -> str:
        lines = [
            f"Reconciliation: {result.events_processed} events processed",
        ]
        if result.gaps:
            for g in result.gaps:
                lines.append(
                    f"  {g.pattern_id[:8]}: expected={g.expected_success_rate:.2%} "
                    f"actual={g.actual_success_rate:.2%} "
                    f"gap={g.gap:+.2%} [{g.gap_severity}]"
                )
        if result.actions:
            for a in result.actions:
                lines.append(
                    f"  Action: {a.action_type} | "
                    f"conf={a.confidence_adjustment:+.2%} "
                    f"({a.severity})"
                )
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# DecisionPatternSynchronizer
# ═══════════════════════════════════════════════════════════════


@dataclass
class SyncResult:
    """同步结果.

    Attributes:
        sync_id: 同步批次ID
        events_processed: 处理的事件数
        patterns_updated: 更新的模式数
        gaps: 预测差距
        actions: 对齐动作
        confidence_enhancements: 置信度增强结果
        summary: 摘要
    """
    sync_id: str = ""
    events_processed: int = 0
    patterns_updated: int = 0
    gaps: list[PredictionGap] = field(default_factory=list)
    actions: list[ReconciliationAction] = field(default_factory=list)
    confidence_enhancements: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""


class DecisionPatternSynchronizer:
    """E13.6.5 DecisionPatternSynchronizer — 双向同步编排.

    编排 DecisionOutcomeBridge + PatternDecisionReconciler 的完整同步流程。

    同步流程:
      1. Bridge: DecisionExperience → DecisionMemoryEvent
      2. Match: 将事件匹配到对应的 Pattern
      3. Reconcile: 比较预测 vs 实际
      4. Apply: 将对齐动作应用到 Pattern
      5. Enhance: 增强 DecisionEngine 的 confidence

    用法:
        sync = DecisionPatternSynchronizer(decision_memory, pattern_store)
        result = sync.sync_execution_result(decision_id, outcome)
        # 或批量
        result = sync.sync_batch_results(decision_experiences)
    """

    def __init__(
        self,
        decision_memory: Any = None,  # DecisionMemory
        pattern_store: Any = None,    # PatternStore
        evaluator: Any = None,        # PatternEvaluator
        lifecycle_manager: Any = None, # PatternLifecycleManager
    ):
        self._decision_memory = decision_memory
        self._pattern_store = pattern_store
        self._evaluator = evaluator
        self._lifecycle = lifecycle_manager
        self._bridge = DecisionOutcomeBridge()
        self._reconciler = PatternDecisionReconciler()

    def sync_execution_result(
        self,
        decision_id: str,
        outcome: Any,
        context: dict[str, Any] | None = None,
    ) -> SyncResult:
        """同步单个执行结果.

        Args:
            decision_id: 决策 ID
            outcome: 执行结果 (ExperienceOutcome)
            context: 决策上下文

        Returns:
            SyncResult: 同步结果
        """
        ctx = context or {}
        ctx["decision_id"] = decision_id

        # 1. 从 DecisionMemory 获取决策经验
        decision_exp = None
        if self._decision_memory:
            decision_exp = self._decision_memory.get_by_decision(decision_id)

        # 2. 创建事件
        if decision_exp and decision_exp.is_resolved:
            bridge_result = self._bridge.from_decision_experience(decision_exp)
        else:
            bridge_result = self._bridge.from_execution_outcome(outcome, ctx)

        if not bridge_result.converted:
            return SyncResult(summary=f"Failed to convert: {bridge_result.reason}")

        event = bridge_result.event

        # 3. 匹配 Pattern
        patterns = self._find_matching_patterns(event)

        # 4. 对每个匹配的 Pattern 进行 reconcile
        result = SyncResult(
            sync_id=str(uuid.uuid4())[:8],
            events_processed=1,
        )

        for pattern in patterns:
            rec_result = self._reconciler.reconcile(pattern, [event])
            result.gaps.extend(rec_result.gaps)
            result.actions.extend(rec_result.actions)

            # 应用对齐动作
            for action in rec_result.actions:
                self._reconciler.apply_feedback(pattern, action)

            # 生命周期检查
            if self._lifecycle and rec_result.actions:
                for action in rec_result.actions:
                    if action.action_type == "decay":
                        from .pattern_feedback import EvaluationResult, PatternEffectiveness
                        eval_result = EvaluationResult(
                            pattern_id=pattern.pattern_id,
                            effectiveness=PatternEffectiveness.FAILING,
                            reason=action.reason,
                        )
                        self._lifecycle.check_pattern(pattern, eval_result)

            result.patterns_updated += 1

        result.summary = (
            f"Synced decision {decision_id}: "
            f"{result.patterns_updated} patterns updated, "
            f"{len(result.actions)} actions applied"
        )
        return result

    def sync_batch_results(
        self,
        events: list[DecisionMemoryEvent],
    ) -> SyncResult:
        """批量同步执行结果.

        Args:
            events: 决策记忆事件列表

        Returns:
            SyncResult: 同步结果
        """
        result = SyncResult(
            sync_id=str(uuid.uuid4())[:8],
            events_processed=len(events),
        )

        if not events or not self._pattern_store:
            result.summary = "No events or no pattern store."
            return result

        patterns = self._pattern_store.get_all()
        if not patterns:
            result.summary = "No patterns to reconcile."
            return result

        # 按 pattern 分组事件
        event_groups = self._group_events_by_pattern(events, patterns)

        for pattern in patterns:
            pattern_events = event_groups.get(pattern.pattern_id, [])
            if not pattern_events:
                continue

            rec_result = self._reconciler.reconcile(pattern, pattern_events)
            result.gaps.extend(rec_result.gaps)
            result.actions.extend(rec_result.actions)

            for action in rec_result.actions:
                self._reconciler.apply_feedback(pattern, action)

            result.patterns_updated += 1

        result.summary = (
            f"Batch sync: {result.events_processed} events → "
            f"{result.patterns_updated} patterns updated, "
            f"{len(result.actions)} actions applied"
        )
        return result

    def enhance_decision_confidence(
        self,
        opportunity_type: str,
        action_type: str,
        base_confidence: float = 0.0,
    ) -> dict[str, Any]:
        """增强决策置信度 — 结合 Decision Memory + Pattern Memory.

        公式:
          enhanced = base_confidence × 0.4
                   + pattern_confidence × 0.35
                   + decision_history_factor × 0.25

        Args:
            opportunity_type: 机会类型
            action_type: 动作类型
            base_confidence: 基础置信度

        Returns:
            dict: {
                "enhanced_confidence": 增强后的置信度,
                "pattern_confidence": 模式置信度,
                "decision_history_factor": 决策历史因子,
                "recommendation": 建议,
            }
        """
        enhanced = base_confidence
        pattern_conf = 0.0
        decision_factor = 0.5  # 默认中性

        # 1. 从 PatternStore 获取模式置信度
        if self._pattern_store:
            pattern = self._pattern_store.get_best_pattern(
                opportunity_type=opportunity_type,
                action_type=action_type,
            )
            if pattern and pattern.confidence > 0:
                pattern_conf = pattern.confidence

        # 2. 从 DecisionMemory 获取历史决策因子
        if self._decision_memory:
            similar = self._decision_memory.find_similar(
                opportunity_type=opportunity_type,
                limit=20,
            )
            resolved = [e for e in similar if e.is_resolved]
            if resolved:
                successes = sum(1 for e in resolved if e.is_success)
                decision_factor = successes / len(resolved)

        # 3. 综合计算
        enhanced = round(
            base_confidence * 0.4
            + pattern_conf * 0.35
            + decision_factor * 0.25,
            4,
        )

        # 推荐级别
        if enhanced >= 0.8:
            recommendation = "strong_recommend"
        elif enhanced >= 0.6:
            recommendation = "recommend"
        elif enhanced >= 0.4:
            recommendation = "suggest"
        else:
            recommendation = "caution"

        return {
            "enhanced_confidence": enhanced,
            "base_confidence": round(base_confidence, 4),
            "pattern_confidence": round(pattern_conf, 4),
            "decision_history_factor": round(decision_factor, 4),
            "recommendation": recommendation,
        }

    def _find_matching_patterns(
        self,
        event: DecisionMemoryEvent,
    ) -> list[PatternMemory]:
        """查找与事件匹配的模式."""
        if not self._pattern_store:
            return []

        # 优先按 pattern_ids 查找
        if event.pattern_ids:
            patterns = []
            for pid in event.pattern_ids:
                for p in self._pattern_store.get_all():
                    if p.pattern_id == pid:
                        patterns.append(p)
            if patterns:
                return patterns

        # 按条件匹配
        matches = []
        for p in self._pattern_store.get_all():
            if (event.opportunity_type
                    and p.condition.opportunity_type == event.opportunity_type):
                matches.append(p)
            elif (event.action_type
                    and p.action.action_type == event.action_type):
                matches.append(p)

        return matches

    def _group_events_by_pattern(
        self,
        events: list[DecisionMemoryEvent],
        patterns: list[PatternMemory],
    ) -> dict[str, list[DecisionMemoryEvent]]:
        """将事件按匹配模式分组."""
        groups: dict[str, list[DecisionMemoryEvent]] = {}

        for event in events:
            matched = self._find_matching_patterns(event)
            for pattern in matched:
                if pattern.pattern_id not in groups:
                    groups[pattern.pattern_id] = []
                groups[pattern.pattern_id].append(event)

        return groups