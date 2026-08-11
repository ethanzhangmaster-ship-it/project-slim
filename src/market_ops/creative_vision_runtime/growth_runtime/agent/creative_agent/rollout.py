"""E14.4.3.4 Rollout Controller — Winner → Scale 自动放量.

将实验赢家自动推广到更大规模投放:

  Experiment Winner → Rollout Decision → UA Action → Scale

核心能力:
  - 赢家识别: 从实验和反馈中识别可放量素材
  - 放量决策: 基于表现和风险决定放量策略
  - 预算调整: 自动计算放量预算增幅
  - 风险控制: 疲劳度监控、预算上限、回滚机制
  - 与 UA Agent 联动: 输出 UA Action 供 UA Agent 执行

放量策略:
  - GRADUAL: 逐日渐进放量 (+20%/天)
  - AGGRESSIVE: 快速放量 (+50%/天)
  - CONSERVATIVE: 保守放量 (+10%/天)
  - MAINTAIN: 维持当前规模

设计原则:
  - 确定性放量逻辑
  - 与 UA Agent 执行层对齐
  - 风险控制优先
  - 所有放量可回滚
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .experiment import CreativeExperiment, ExperimentResult, VariantMetrics
from .strategy import CreativeStrategyType
from .opportunity import OpportunityPriority


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class RolloutStrategy(str, Enum):
    """放量策略."""
    GRADUAL = "gradual"          # 渐进放量 (+20%/天)
    AGGRESSIVE = "aggressive"    # 快速放量 (+50%/天)
    CONSERVATIVE = "conservative"  # 保守放量 (+10%/天)
    MAINTAIN = "maintain"        # 维持当前
    HALT = "halt"                # 停止
    ROLLBACK = "rollback"        # 回滚


class RolloutStatus(str, Enum):
    """放量状态."""
    PENDING = "pending"          # 等待
    APPROVED = "approved"        # 已批准
    EXECUTING = "executing"      # 执行中
    COMPLETED = "completed"      # 完成
    FAILED = "failed"            # 失败
    ROLLED_BACK = "rolled_back"  # 已回滚


class RolloutTrigger(str, Enum):
    """放量触发条件."""
    EXPERIMENT_WINNER = "experiment_winner"    # 实验发现赢家
    UA_FEEDBACK = "ua_feedback"               # UA 反馈推荐
    SUPERVISOR_APPROVAL = "supervisor"         # Supervisor 审批
    MANUAL = "manual"                          # 手动触发


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class RolloutDecision:
    """放量决策.

    Attributes:
        decision_id: 决策 ID
        experiment_id: 关联实验 ID
        variant_id: 目标变体 ID
        creative_id: 素材 ID
        rollout_strategy: 放量策略
        status: 放量状态
        priority: 优先级
        current_budget: 当前预算
        target_budget: 目标预算
        budget_increase_pct: 预算增幅 (%)
        daily_step_pct: 每日增幅 (%)
        risk_level: 风险等级 (0-1)
        reason: 决策理由
        conditions: 放量条件 (停止条件)
        previous_state: 放量前状态 (用于回滚)
        created_at: 创建时间
        executed_at: 执行时间
        completed_at: 完成时间
        metadata: 扩展元数据
    """
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str = ""
    variant_id: str = ""
    creative_id: str = ""
    rollout_strategy: RolloutStrategy = RolloutStrategy.CONSERVATIVE
    status: RolloutStatus = RolloutStatus.PENDING
    priority: OpportunityPriority = OpportunityPriority.MEDIUM
    current_budget: float = 0.0
    target_budget: float = 0.0
    budget_increase_pct: float = 0.0
    daily_step_pct: float = 0.0
    risk_level: float = 0.0
    reason: str = ""
    conditions: list[str] = field(default_factory=list)
    previous_state: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    executed_at: str = ""
    completed_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "experiment_id": self.experiment_id,
            "variant_id": self.variant_id,
            "creative_id": self.creative_id,
            "rollout_strategy": self.rollout_strategy.value,
            "status": self.status.value,
            "priority": self.priority.value,
            "current_budget": self.current_budget,
            "target_budget": self.target_budget,
            "budget_increase_pct": self.budget_increase_pct,
            "daily_step_pct": self.daily_step_pct,
            "risk_level": self.risk_level,
            "reason": self.reason,
            "conditions": self.conditions,
            "previous_state": self.previous_state,
            "created_at": self.created_at,
            "executed_at": self.executed_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }

    @property
    def ua_action(self) -> dict[str, Any]:
        """转化为 UA Agent 可执行的动作."""
        return {
            "action_type": "adjust_budget",
            "creative_id": self.creative_id,
            "current_budget": self.current_budget,
            "target_budget": self.target_budget,
            "increase_pct": self.budget_increase_pct,
            "strategy": self.rollout_strategy.value,
            "priority": self.priority.value,
            "risk_level": self.risk_level,
            "decision_id": self.decision_id,
            "conditions": self.conditions,
        }

    @property
    def summary(self) -> str:
        parts = [
            f"[{self.rollout_strategy.value}] {self.creative_id}",
            f"budget: {self.current_budget}→{self.target_budget}",
            f"(+{self.budget_increase_pct:.0%})",
        ]
        if self.risk_level > 0.3:
            parts.append(f"risk={self.risk_level:.0%}")
        return " ".join(parts)


@dataclass
class RolloutReport:
    """放量报告.

    Attributes:
        report_id: 报告 ID
        decisions: 放量决策列表
        total_decisions: 总决策数
        executed: 已执行
        pending: 等待中
        active_budgets: 活跃预算总额
        summary: 报告摘要
        created_at: 创建时间
    """
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decisions: list[RolloutDecision] = field(default_factory=list)
    total_decisions: int = 0
    executed: int = 0
    pending: int = 0
    active_budgets: float = 0.0
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "decisions": [d.to_dict() for d in self.decisions],
            "total_decisions": self.total_decisions,
            "executed": self.executed,
            "pending": self.pending,
            "active_budgets": self.active_budgets,
            "summary": self.summary,
            "created_at": self.created_at,
        }

    @property
    def decision_count(self) -> int:
        return len(self.decisions)


# ═══════════════════════════════════════════════════════════════
# Rollout Controller
# ═══════════════════════════════════════════════════════════════


class RolloutController:
    """放量控制器 — Winner → Scale.

    职责:
      1. 赢家识别: 从实验中识别可放量素材
      2. 放量决策: 基于表现和风险决定放量策略
      3. 预算计算: 自动计算放量目标和每日增幅
      4. 风险控制: 设置停止条件、预算上限
      5. 回滚支持: 所有放量可回滚

    用法:
        controller = RolloutController()
        decision = controller.evaluate_winner(experiment, variant_metrics)
        controller.execute(decision)
    """

    # 默认配置
    DEFAULT_MAX_BUDGET = 5000.0        # 最大预算
    DEFAULT_MAX_DAILY_INCREASE = 0.50  # 最大日增幅
    DEFAULT_MIN_ROAS_FOR_SCALE = 1.0   # 放量最低 ROAS
    DEFAULT_MAX_FATIGUE = 0.5          # 放量最高疲劳度

    def __init__(
        self,
        max_budget: float = 5000.0,
        max_daily_increase: float = 0.50,
        min_roas: float = 1.0,
        max_fatigue: float = 0.5,
    ):
        self._max_budget = max_budget
        self._max_daily_increase = max_daily_increase
        self._min_roas = min_roas
        self._max_fatigue = max_fatigue

        self._decisions: dict[str, RolloutDecision] = {}
        self._history: list[RolloutDecision] = []

    # ── 核心方法 ──────────────────────────────────────────────

    def evaluate_winner(
        self,
        experiment: CreativeExperiment,
        variant: VariantMetrics,
        trigger: RolloutTrigger = RolloutTrigger.EXPERIMENT_WINNER,
    ) -> RolloutDecision | None:
        """评估赢家是否可放量.

        Args:
            experiment: 实验
            variant: 变体指标
            trigger: 触发条件

        Returns:
            RolloutDecision | None: 放量决策 (None 表示不符合放量条件)
        """
        # 1. 放量条件检查
        if not self._can_scale(variant):
            return None

        # 2. 确定放量策略
        strategy = self._determine_strategy(variant)

        # 3. 计算预算
        current_budget = variant.spend
        target_budget = self._calculate_target_budget(variant, strategy)
        budget_increase_pct = (target_budget - current_budget) / current_budget if current_budget > 0 else 0.5
        daily_step = self._calculate_daily_step(strategy, variant)

        # 4. 风险评估
        risk_level = self._assess_risk(variant)

        # 5. 设置停止条件
        conditions = self._build_conditions(variant)

        # 6. 构建理由
        reason = self._build_reason(variant, strategy)

        decision = RolloutDecision(
            experiment_id=experiment.experiment_id,
            variant_id=variant.variant_id,
            creative_id=variant.creative_id,
            rollout_strategy=strategy,
            priority=experiment.priority,
            current_budget=current_budget,
            target_budget=target_budget,
            budget_increase_pct=budget_increase_pct,
            daily_step_pct=daily_step,
            risk_level=risk_level,
            reason=reason,
            conditions=conditions,
            previous_state={
                "budget": current_budget,
                "roas": variant.roas,
                "ctr": variant.ctr,
                "fatigue": variant.fatigue,
            },
        )

        self._decisions[decision.decision_id] = decision
        self._history.append(decision)
        return decision

    def approve(self, decision: RolloutDecision) -> bool:
        """批准放量."""
        if decision.status != RolloutStatus.PENDING:
            return False
        decision.status = RolloutStatus.APPROVED
        return True

    def execute(self, decision: RolloutDecision) -> bool:
        """执行放量.

        Returns:
            bool: 是否成功执行
        """
        if decision.status not in (RolloutStatus.APPROVED, RolloutStatus.PENDING):
            return False
        decision.status = RolloutStatus.EXECUTING
        decision.executed_at = datetime.now(timezone.utc).isoformat()
        return True

    def complete(self, decision: RolloutDecision) -> bool:
        """完成放量."""
        if decision.status != RolloutStatus.EXECUTING:
            return False
        decision.status = RolloutStatus.COMPLETED
        decision.completed_at = datetime.now(timezone.utc).isoformat()
        return True

    def rollback(self, decision: RolloutDecision) -> bool:
        """回滚放量."""
        if decision.status not in (RolloutStatus.EXECUTING, RolloutStatus.COMPLETED):
            return False
        decision.status = RolloutStatus.ROLLED_BACK
        decision.completed_at = datetime.now(timezone.utc).isoformat()
        return True

    def evaluate_batch(
        self,
        experiments: list[tuple[CreativeExperiment, VariantMetrics]],
    ) -> list[RolloutDecision]:
        """批量评估赢家.

        Args:
            experiments: [(experiment, variant), ...]

        Returns:
            list[RolloutDecision]: 放量决策列表
        """
        decisions = []
        for experiment, variant in experiments:
            decision = self.evaluate_winner(experiment, variant)
            if decision:
                decisions.append(decision)
        return decisions

    # ── 内部方法 ──────────────────────────────────────────────

    def _can_scale(self, variant: VariantMetrics) -> bool:
        """检查是否可放量."""
        if variant.roas < self._min_roas:
            return False
        if variant.fatigue > self._max_fatigue:
            return False
        if variant.installs < 500:  # 样本量不足
            return False
        return True

    def _determine_strategy(self, variant: VariantMetrics) -> RolloutStrategy:
        """确定放量策略."""
        if variant.roas >= 2.0 and variant.fatigue < 0.3:
            return RolloutStrategy.AGGRESSIVE
        elif variant.roas >= 1.5 and variant.fatigue < 0.4:
            return RolloutStrategy.GRADUAL
        elif variant.roas >= 1.0:
            return RolloutStrategy.CONSERVATIVE
        return RolloutStrategy.MAINTAIN

    def _calculate_target_budget(
        self,
        variant: VariantMetrics,
        strategy: RolloutStrategy,
    ) -> float:
        """计算目标预算."""
        current = variant.spend

        multipliers = {
            RolloutStrategy.AGGRESSIVE: 2.0,
            RolloutStrategy.GRADUAL: 1.5,
            RolloutStrategy.CONSERVATIVE: 1.3,
            RolloutStrategy.MAINTAIN: 1.0,
        }
        multiplier = multipliers.get(strategy, 1.0)
        target = current * multiplier

        # 预算上限
        return min(target, self._max_budget)

    def _calculate_daily_step(
        self,
        strategy: RolloutStrategy,
        variant: VariantMetrics,
    ) -> float:
        """计算每日增幅."""
        steps = {
            RolloutStrategy.AGGRESSIVE: 0.50,
            RolloutStrategy.GRADUAL: 0.20,
            RolloutStrategy.CONSERVATIVE: 0.10,
            RolloutStrategy.MAINTAIN: 0.0,
        }
        return steps.get(strategy, 0.10)

    def _assess_risk(self, variant: VariantMetrics) -> float:
        """评估放量风险."""
        risk = 0.0
        # 疲劳度越高，风险越大
        risk += variant.fatigue * 0.4
        # 样本量越小，风险越大
        if variant.installs < 1000:
            risk += 0.3
        elif variant.installs < 3000:
            risk += 0.15
        # ROAS 越低，风险越大
        if variant.roas < 1.2:
            risk += 0.2
        elif variant.roas < 1.5:
            risk += 0.1
        return min(risk, 1.0)

    def _build_conditions(self, variant: VariantMetrics) -> list[str]:
        """构建停止条件."""
        conditions = []
        conditions.append(f"ROAS 低于 {self._min_roas} 时停止")
        conditions.append(f"疲劳度超过 {self._max_fatigue} 时暂停")
        if variant.spend > 0:
            conditions.append(f"日花费超过 {self._max_budget} 时停止")
        return conditions

    def _build_reason(
        self,
        variant: VariantMetrics,
        strategy: RolloutStrategy,
    ) -> str:
        """构建放量理由."""
        return (
            f"实验赢家放量: ROAS={variant.roas:.2f}, "
            f"CTR={variant.ctr:.3f}, "
            f"疲劳度={variant.fatigue:.2f}, "
            f"策略={strategy.value}"
        )

    # ── 查询 ──────────────────────────────────────────────────

    def get_decision(self, decision_id: str) -> RolloutDecision | None:
        return self._decisions.get(decision_id)

    def get_decisions_by_creative(self, creative_id: str) -> list[RolloutDecision]:
        return [d for d in self._decisions.values() if d.creative_id == creative_id]

    def get_pending_decisions(self) -> list[RolloutDecision]:
        return [d for d in self._decisions.values() if d.status == RolloutStatus.PENDING]

    def get_executing_decisions(self) -> list[RolloutDecision]:
        return [d for d in self._decisions.values() if d.status == RolloutStatus.EXECUTING]

    def get_completed_decisions(self) -> list[RolloutDecision]:
        return [d for d in self._decisions.values() if d.status == RolloutStatus.COMPLETED]

    def get_history(self, n: int = 20) -> list[RolloutDecision]:
        return self._history[-n:]

    def generate_report(self) -> RolloutReport:
        """生成放量报告."""
        decisions = list(self._decisions.values())
        executed = len(self.get_completed_decisions())
        pending = len(self.get_pending_decisions())
        active_budgets = sum(
            d.target_budget for d in self._decisions.values()
            if d.status == RolloutStatus.EXECUTING
        )

        return RolloutReport(
            decisions=decisions,
            total_decisions=len(decisions),
            executed=executed,
            pending=pending,
            active_budgets=active_budgets,
            summary=f"共 {len(decisions)} 个放量决策, {executed} 已执行, {pending} 等待中",
        )

    def stats(self) -> dict[str, Any]:
        total = len(self._decisions)
        if total == 0:
            return {"total": 0}
        status_counts: dict[str, int] = {}
        for d in self._decisions.values():
            s = d.status.value
            status_counts[s] = status_counts.get(s, 0) + 1
        strategy_counts: dict[str, int] = {}
        for d in self._decisions.values():
            s = d.rollout_strategy.value
            strategy_counts[s] = strategy_counts.get(s, 0) + 1
        return {
            "total": total,
            "by_status": status_counts,
            "by_strategy": strategy_counts,
            "pending": len(self.get_pending_decisions()),
            "executing": len(self.get_executing_decisions()),
            "completed": len(self.get_completed_decisions()),
        }

    def reset(self) -> None:
        self._decisions.clear()
        self._history.clear()


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_rollout_controller(
    max_budget: float = 5000.0,
    min_roas: float = 1.0,
    max_fatigue: float = 0.5,
) -> RolloutController:
    """创建默认放量控制器."""
    return RolloutController(
        max_budget=max_budget,
        min_roas=min_roas,
        max_fatigue=max_fatigue,
    )