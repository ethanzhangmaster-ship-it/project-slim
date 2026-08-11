"""Growth Loop V2 — OutcomeEvaluator.

结果评估器：评估执行动作的实际效果，将结果反馈到 Experience Memory，闭合 Growth Loop。

数据流:
  ExecutionAction (已执行的动作)
    + pre_metrics (执行前指标快照)
    + post_metrics (执行后指标快照)
    + observation_window_days (观察周期)
      ↓
  ActionOutcome (评估结果: SUCCESS / MARGINAL / FAILURE / INCONCLUSIVE)
      ↓
  ExperienceRecord (写入 ExperienceStore，增强下一轮假设生成)

闭合链路:
  Signal → Diagnosis → Hypothesis → Strategy → Action → [执行] → Outcome → Experience
                                                                    ↑                ↓
                                                                    └────── 下一轮 ──┘

不是 Agent，是 Engine。与 DiagnosticEngine / HypothesisGenerator / StrategySelector / ActionPlanner 同级。
不新建 Memory，只消费已有 ExperienceStore。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.market_ops.creative_vision_runtime.reality.meta_learning.models import (
    ContextDetail,
    ExperimentDetail,
    ExperienceOutcome,
    ExperienceRecord,
    ExperienceResult,
    MutationDetail,
    MutationType,
)
from src.market_ops.creative_vision_runtime.reality.meta_learning.experience_store import (
    ExperienceStore,
)
from scripts.action_planner import ActionStatus, ActionType, ExecutionAction

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

# Outcome 判定阈值（与 models.py 中 ExperienceOutcome 注释一致）
_IMPROVEMENT_SUCCESS = 0.15   # improvement > 0.15 = SUCCESS
_IMPROVEMENT_MARGINAL = 0.0   # 0 < improvement ≤ 0.15 = MARGINAL

# 回滚检测阈值：目标指标恶化超过此比例 → 触发回滚
_ROLLBACK_DETERIORATION = 0.10  # 10%

# StrategyType → MutationType 映射（从 action.expected_impact.strategy_type 反推）
_STRATEGY_TO_MUTATION: dict[str, tuple[MutationType, list[str]]] = {
    "suppress": (MutationType.REFRESH_HOOK, ["hook", "visual_style"]),
    "scale": (MutationType.VISUAL_VARIATION, ["visual_style"]),
    "refresh": (MutationType.REFRESH_HOOK, ["hook"]),
    "pause": (MutationType.FULL_REBUILD, ["hook", "visual_style", "gameplay", "monetization"]),
    "maintain": (MutationType.REFRESH_HOOK, []),
    "explore": (MutationType.VISUAL_VARIATION, ["visual_style"]),
}

# 产生经验的动作类型（NOOP 不产生经验）
_ACTION_TYPES_WITH_EXPERIENCE: set[ActionType] = {
    ActionType.UPDATE_BUDGET,
    ActionType.PAUSE_CAMPAIGN,
    ActionType.RESUME_CAMPAIGN,
}


# ──────────────────────────────────────────────
# ActionOutcome 数据模型
# ──────────────────────────────────────────────


@dataclass
class ActionOutcome:
    """动作结果评估 — 单个 ExecutionAction 的执行后效果评估。

    评估依据:
      - pre_metrics vs post_metrics 对比
      - action.expected_impact 中的预期指标和方向
      - 目标指标恶化 > 10% → 触发回滚 → 强制 FAILURE

    Attributes:
        outcome:    结果类型 (SUCCESS / MARGINAL / FAILURE / INCONCLUSIVE)
        improvement: 综合改善幅度（正=改善, 负=恶化）
        metrics_delta: 逐指标百分比变化
        target_metric:  评估的目标指标 (roas / ctr / cpi / ...)
        target_direction: 预期方向 (positive=上升好 / negative=下降好 / neutral)
        expected_change: 预期变化幅度
        actual_change:   实际变化幅度
        rollback_triggered: 是否触发回滚条件
    """

    # ── 标识（全链路追溯）──
    outcome_id: str = ""
    action_id: str = ""
    strategy_id: str = ""
    hypothesis_id: str = ""
    diagnosis_id: str = ""
    signal_id: str = ""

    # ── 评估结果 ──
    outcome: ExperienceOutcome = ExperienceOutcome.INCONCLUSIVE
    success: bool = False
    improvement: float = 0.0
    metrics_delta: dict[str, float] = field(default_factory=dict)

    # ── 评估依据 ──
    target_metric: str = ""
    target_direction: str = ""
    expected_change: float = 0.0
    actual_change: float = 0.0
    rollback_triggered: bool = False

    # ── 洞察 ──
    insight: str = ""
    key_finding: str = ""

    # ── 元数据 ──
    observation_window_days: int = 7
    evaluated_at: str = ""

    def __post_init__(self) -> None:
        if not self.outcome_id:
            self.outcome_id = f"outcome_{uuid4().hex[:12]}"
        if not self.evaluated_at:
            self.evaluated_at = datetime.now(timezone.utc).isoformat()

    @property
    def is_actionable(self) -> bool:
        """评估结果是否可指导后续决策。"""
        return self.outcome in (
            ExperienceOutcome.SUCCESS,
            ExperienceOutcome.FAILURE,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "action_id": self.action_id,
            "strategy_id": self.strategy_id,
            "hypothesis_id": self.hypothesis_id,
            "diagnosis_id": self.diagnosis_id,
            "signal_id": self.signal_id,
            "outcome": self.outcome.value,
            "success": self.success,
            "improvement": round(self.improvement, 4),
            "metrics_delta": {k: round(v, 4) for k, v in self.metrics_delta.items()},
            "target_metric": self.target_metric,
            "target_direction": self.target_direction,
            "expected_change": round(self.expected_change, 4),
            "actual_change": round(self.actual_change, 4),
            "rollback_triggered": self.rollback_triggered,
            "insight": self.insight,
            "key_finding": self.key_finding,
            "observation_window_days": self.observation_window_days,
            "evaluated_at": self.evaluated_at,
            "is_actionable": self.is_actionable,
        }


# ──────────────────────────────────────────────
# OutcomeEvaluator
# ──────────────────────────────────────────────


class OutcomeEvaluator:
    """结果评估器 — 评估执行动作效果并写入经验记忆。

    使用方式:
        evaluator = OutcomeEvaluator(store)
        outcome = evaluator.evaluate(action, pre_metrics, post_metrics)
        # ExperienceRecord 已自动写入 store

    闭合 Growth Loop:
        下一轮 HypothesisGenerator 会从 store 中读取本次写入的经验，
        增强假设的置信度和 basis（historical / pattern / mixed）。
    """

    def __init__(
        self,
        store: ExperienceStore | None = None,
    ) -> None:
        """初始化。

        Args:
            store: ExperienceStore 实例。为 None 时只评估不写入经验。
        """
        self._store = store

    def evaluate(
        self,
        action: ExecutionAction,
        pre_metrics: dict[str, float],
        post_metrics: dict[str, float],
        observation_window_days: int = 7,
        context: ContextDetail | None = None,
    ) -> ActionOutcome:
        """评估单个动作的执行效果。

        Args:
            action: 已执行的 ExecutionAction
            pre_metrics: 执行前指标快照 (aggregate_by_creative 输出)
            post_metrics: 执行后指标快照
            observation_window_days: 观察周期（天）
            context: 上下文信息（产品、市场、平台），为 None 时使用默认值

        Returns:
            ActionOutcome 评估结果
        """
        # 1. 计算指标变化
        metrics_delta = self._compute_metrics_delta(pre_metrics, post_metrics)

        # 2. 确定目标指标与预期
        target_metric = self._get_target_metric(action)
        target_direction = self._get_target_direction(action)
        expected_change = self._get_expected_change(action)

        # 3. 计算实际变化
        actual_change = metrics_delta.get(target_metric, 0.0)

        # 4. 计算综合改善幅度
        improvement = self._compute_improvement(
            target_metric, target_direction, actual_change, action
        )

        # 5. 检测回滚条件
        rollback_triggered = self._check_rollback(
            action, pre_metrics, post_metrics, target_metric, target_direction
        )

        # 6. 判定 outcome
        outcome, success = self._determine_outcome(
            improvement, rollback_triggered, pre_metrics, post_metrics, target_metric
        )

        # 7. 生成洞察
        insight = self._build_insight(
            action, outcome, target_metric, actual_change, improvement
        )
        key_finding = self._build_key_finding(action, outcome, target_metric)

        # 8. 构建 ActionOutcome
        result = ActionOutcome(
            action_id=action.action_id,
            strategy_id=action.strategy_id,
            hypothesis_id=action.hypothesis_id,
            diagnosis_id=action.diagnosis_id,
            signal_id=action.signal_id,
            outcome=outcome,
            success=success,
            improvement=improvement,
            metrics_delta=metrics_delta,
            target_metric=target_metric,
            target_direction=target_direction,
            expected_change=expected_change,
            actual_change=actual_change,
            rollback_triggered=rollback_triggered,
            insight=insight,
            key_finding=key_finding,
            observation_window_days=observation_window_days,
        )

        # 9. 写入 ExperienceStore（仅对真实执行的动作）
        if self._store is not None and self._should_write_experience(action):
            self._write_experience(
                action, result, pre_metrics, post_metrics, context
            )

        return result

    def evaluate_batch(
        self,
        actions_with_metrics: list[
            tuple[ExecutionAction, dict[str, float], dict[str, float]]
        ],
        observation_window_days: int = 7,
        context: ContextDetail | None = None,
    ) -> list[ActionOutcome]:
        """批量评估。

        Args:
            actions_with_metrics: (action, pre_metrics, post_metrics) 元组列表
            observation_window_days: 观察周期
            context: 上下文

        Returns:
            ActionOutcome 列表
        """
        return [
            self.evaluate(action, pre, post, observation_window_days, context)
            for action, pre, post in actions_with_metrics
        ]

    # ── 指标计算 ──

    def _compute_metrics_delta(
        self,
        pre: dict[str, float],
        post: dict[str, float],
    ) -> dict[str, float]:
        """计算指标百分比变化。

        pre=0 时用绝对差值代替（避免除零）。
        """
        delta: dict[str, float] = {}
        all_keys = set(pre.keys()) | set(post.keys())
        for key in all_keys:
            pre_val = pre.get(key, 0.0)
            post_val = post.get(key, 0.0)
            if pre_val == 0:
                delta[key] = post_val  # 绝对差值
            else:
                delta[key] = (post_val - pre_val) / abs(pre_val)
        return delta

    def _get_target_metric(self, action: ExecutionAction) -> str:
        """从 action.expected_impact 获取目标指标。"""
        return action.expected_impact.get("metric", "roas")

    def _get_target_direction(self, action: ExecutionAction) -> str:
        """获取预期方向。"""
        return action.expected_impact.get("direction", "positive")

    def _get_expected_change(self, action: ExecutionAction) -> float:
        """获取预期变化幅度。"""
        return action.expected_impact.get("estimated_change", 0.0)

    def _compute_improvement(
        self,
        target_metric: str,
        target_direction: str,
        actual_change: float,
        action: ExecutionAction,
    ) -> float:
        """计算综合改善幅度。

        改善幅度定义:
          - direction=positive: actual_change > 0 为改善（如 ROAS 上升）
          - direction=negative: actual_change < 0 为改善（如 CPI 下降）
          - direction=neutral:  improvement = 0

        PAUSE 动作的改善不低于 0（暂停最多就是没改善）。
        """
        if target_direction == "negative":
            improvement = -actual_change
        elif target_direction == "positive":
            improvement = actual_change
        else:
            improvement = 0.0

        # PAUSE 动作：改善不低于 0
        if action.action_type == ActionType.PAUSE_CAMPAIGN:
            improvement = max(improvement, 0.0)

        return round(improvement, 4)

    # ── 回滚检测 ──

    def _check_rollback(
        self,
        action: ExecutionAction,
        pre: dict[str, float],
        post: dict[str, float],
        target_metric: str,
        target_direction: str,
    ) -> bool:
        """检测是否触发回滚条件。

        简化逻辑：目标指标恶化（与预期方向相反）超过 10% → 触发回滚。
        生产环境应解析 strategy.rollback_condition 字符串，但该字段未传递到
        ExecutionAction，故使用通用阈值近似。
        """
        if target_metric in ("none", "unknown", ""):
            return False

        # 指标必须在 pre 和 post 中都存在
        if target_metric not in pre or target_metric not in post:
            return False

        pre_val = pre.get(target_metric, 0.0)
        post_val = post.get(target_metric, 0.0)

        if pre_val == 0:
            return False

        change = (post_val - pre_val) / abs(pre_val)

        # 指标恶化 = 与预期方向相反且变化 > 阈值
        if target_direction == "positive" and change < -_ROLLBACK_DETERIORATION:
            return True
        if target_direction == "negative" and change > _ROLLBACK_DETERIORATION:
            return True

        return False

    # ── Outcome 判定 ──

    def _determine_outcome(
        self,
        improvement: float,
        rollback_triggered: bool,
        pre_metrics: dict[str, float],
        post_metrics: dict[str, float],
        target_metric: str,
    ) -> tuple[ExperienceOutcome, bool]:
        """判定结果类型。

        Returns:
            (outcome, success)
        """
        # 回滚触发 → 直接失败
        if rollback_triggered:
            return (ExperienceOutcome.FAILURE, False)

        # 数据不足 → 无法判断
        if not self._has_sufficient_data(pre_metrics, post_metrics, target_metric):
            return (ExperienceOutcome.INCONCLUSIVE, False)

        # 按 improvement 判定
        if improvement > _IMPROVEMENT_SUCCESS:
            return (ExperienceOutcome.SUCCESS, True)
        if improvement > _IMPROVEMENT_MARGINAL:
            return (ExperienceOutcome.MARGINAL, False)
        return (ExperienceOutcome.FAILURE, False)

    def _has_sufficient_data(
        self,
        pre: dict[str, float],
        post: dict[str, float],
        target_metric: str,
    ) -> bool:
        """检查是否有足够的数据进行评估。"""
        if target_metric in ("none", "unknown", ""):
            return False
        if target_metric not in pre or target_metric not in post:
            return False
        if pre.get(target_metric, 0.0) == 0:
            return False
        return True

    # ── 洞察生成 ──

    def _build_insight(
        self,
        action: ExecutionAction,
        outcome: ExperienceOutcome,
        target_metric: str,
        actual_change: float,
        improvement: float,
    ) -> str:
        """构建洞察。"""
        outcome_label = {
            ExperienceOutcome.SUCCESS: "成功",
            ExperienceOutcome.MARGINAL: "边际改善",
            ExperienceOutcome.FAILURE: "失败",
            ExperienceOutcome.INCONCLUSIVE: "数据不足",
        }.get(outcome, "未知")

        direction_arrow = "↑" if actual_change >= 0 else "↓"

        return (
            f"动作 {action.action_type.value} {outcome_label}: "
            f"{target_metric} {direction_arrow} {abs(actual_change):.1%}, "
            f"综合改善 {improvement:+.2%}"
        )

    def _build_key_finding(
        self,
        action: ExecutionAction,
        outcome: ExperienceOutcome,
        target_metric: str,
    ) -> str:
        """构建关键发现。"""
        if outcome == ExperienceOutcome.SUCCESS:
            return f"{action.action_type.value} 对 {target_metric} 有效，可继续应用"
        if outcome == ExperienceOutcome.FAILURE:
            return f"{action.action_type.value} 未改善 {target_metric}，需调整策略"
        if outcome == ExperienceOutcome.MARGINAL:
            return f"{action.action_type.value} 对 {target_metric} 效果有限，需观察"
        return f"{action.action_type.value} 评估数据不足，无法判断"

    # ── 经验写入 ──

    def _should_write_experience(self, action: ExecutionAction) -> bool:
        """判断动作是否应该写入经验记忆。

        NOOP / SKIPPED 不写入。
        """
        if action.action_type not in _ACTION_TYPES_WITH_EXPERIENCE:
            return False
        if action.status == ActionStatus.SKIPPED:
            return False
        return True

    def _write_experience(
        self,
        action: ExecutionAction,
        outcome: ActionOutcome,
        pre_metrics: dict[str, float],
        post_metrics: dict[str, float],
        context: ContextDetail | None,
    ) -> ExperienceRecord:
        """将评估结果写入 ExperienceStore。"""
        # 从 expected_impact 反推 mutation_type
        strategy_type_str = action.expected_impact.get("strategy_type", "maintain")
        mutation_type, changed_genes = _STRATEGY_TO_MUTATION.get(
            strategy_type_str, (MutationType.REFRESH_HOOK, [])
        )

        # 构建上下文
        if context is None:
            context = ContextDetail(platform="facebook")

        # 构建经验记录
        record = ExperienceRecord(
            creative_id=action.creative_id,
            mutation=MutationDetail(
                mutation_type=mutation_type,
                changed_genes=changed_genes,
            ),
            experiment=ExperimentDetail(
                baseline_metrics=dict(pre_metrics),
                winner_metrics=dict(post_metrics),
                improvement=outcome.improvement,
                metrics_delta=dict(outcome.metrics_delta),
                confidence=action.confidence,
            ),
            context=context,
            result=ExperienceResult(
                outcome=outcome.outcome,
                success=outcome.success,
                insight=outcome.insight,
                key_finding=outcome.key_finding,
            ),
            related_ids={
                "signal_id": action.signal_id,
                "diagnosis_id": action.diagnosis_id,
                "hypothesis_id": action.hypothesis_id,
                "strategy_id": action.strategy_id,
                "action_id": action.action_id,
                "outcome_id": outcome.outcome_id,
            },
            metadata={
                "action_type": action.action_type.value,
                "budget_impact": action.budget_impact,
                "risk_level": action.risk_level,
                "target_metric": outcome.target_metric,
                "actual_change": outcome.actual_change,
                "rollback_triggered": outcome.rollback_triggered,
                "observation_window_days": outcome.observation_window_days,
            },
        )

        self._store.add(record)
        logger.info(
            "OutcomeEvaluator: wrote experience %s for action %s "
            "(outcome=%s, improvement=%+.2f)",
            record.experience_id,
            action.action_id,
            outcome.outcome.value,
            outcome.improvement,
        )
        return record
