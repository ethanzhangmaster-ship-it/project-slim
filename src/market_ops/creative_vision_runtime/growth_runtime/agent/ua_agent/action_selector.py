"""E14.3.5 UA Action Selector — 动作选择与执行.

将策略转换为具体执行动作，连接到 E13 GrowthDecisionExecutor:

  输入: UAStrategy (从 strategy 输出)
  输出: SelectedAction (action_type, target, params, rollback)

选择逻辑:
  - 按优先级排序
  - 过滤审批需求
  - 去重合并
  - 生成执行计划

设计原则:
  - 每个动作可回滚
  - 高风险动作需审批
  - 执行记录可追溯
  - 连接 E13 执行层
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .strategy import UAStrategy, StrategyAction, StrategyType


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


class ActionStatus(str, Enum):
    """动作执行状态."""
    PENDING = "pending"          # 待执行
    SELECTED = "selected"        # 已选中
    APPROVED = "approved"        # 已审批
    EXECUTING = "executing"      # 执行中
    EXECUTED = "executed"        # 已执行
    ROLLED_BACK = "rolled_back"  # 已回滚
    FAILED = "failed"            # 失败
    SKIPPED = "skipped"          # 跳过


class ActionRisk(str, Enum):
    """动作风险等级."""
    LOW = "low"            # 低风险: 监控类
    MEDIUM = "medium"      # 中风险: 预算调整
    HIGH = "high"          # 高风险: 暂停系列
    CRITICAL = "critical"  # 极高风险: 大规模变更

    @property
    def level(self) -> int:
        """风险等级数值 (用于比较)."""
        return _RISK_LEVELS[self]


_RISK_LEVELS: dict[ActionRisk, int] = {
    ActionRisk.LOW: 0,
    ActionRisk.MEDIUM: 1,
    ActionRisk.HIGH: 2,
    ActionRisk.CRITICAL: 3,
}


@dataclass
class SelectedAction:
    """选中的执行动作.

    Attributes:
        action_id: 动作 ID
        action_type: 动作类型
        target: 目标实体
        parameters: 执行参数
        source_strategy: 来源策略 ID
        priority: 优先级
        confidence: 置信度
        risk: 风险等级
        status: 执行状态
        requires_approval: 是否需要审批
        rollback_action: 回滚动作 (恢复原始状态)
        expected_impact: 预期影响
        executed_at: 执行时间
        executed_by: 执行者
        execution_result: 执行结果
        error: 错误信息
        metadata: 扩展元数据
    """
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: str = ""
    target: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    source_strategy: str = ""
    priority: float = 0.5
    confidence: float = 0.0
    risk: ActionRisk = ActionRisk.LOW
    status: ActionStatus = ActionStatus.PENDING
    requires_approval: bool = False
    rollback_action: dict[str, Any] | None = None
    expected_impact: str = ""
    executed_at: str = ""
    executed_by: str = ""
    execution_result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "target": self.target,
            "parameters": self.parameters,
            "source_strategy": self.source_strategy,
            "priority": round(self.priority, 4),
            "confidence": round(self.confidence, 4),
            "risk": self.risk.value,
            "status": self.status.value,
            "requires_approval": self.requires_approval,
            "rollback_action": self.rollback_action,
            "expected_impact": self.expected_impact,
            "executed_at": self.executed_at,
            "executed_by": self.executed_by,
            "execution_result": self.execution_result,
            "error": self.error,
            "metadata": self.metadata,
        }

    def mark_executed(self, result: dict[str, Any] | None = None) -> None:
        self.status = ActionStatus.EXECUTED
        self.executed_at = datetime.now(timezone.utc).isoformat()
        if result:
            self.execution_result = result

    def mark_failed(self, error: str) -> None:
        self.status = ActionStatus.FAILED
        self.error = error

    def mark_rolled_back(self) -> None:
        self.status = ActionStatus.ROLLED_BACK

    def mark_approved(self) -> None:
        self.status = ActionStatus.APPROVED


@dataclass
class ActionPlan:
    """动作执行计划.

    Attributes:
        plan_id: 计划 ID
        actions: 选中的动作列表
        summary: 执行摘要
        total_estimated_impact: 总预期影响
        created_at: 创建时间
        metadata: 扩展元数据
    """
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    actions: list[SelectedAction] = field(default_factory=list)
    summary: str = ""
    total_estimated_impact: dict[str, float] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "actions": [a.to_dict() for a in self.actions],
            "summary": self.summary,
            "total_estimated_impact": self.total_estimated_impact,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @property
    def action_count(self) -> int:
        return len(self.actions)

    @property
    def pending_count(self) -> int:
        return sum(1 for a in self.actions if a.status == ActionStatus.PENDING)

    @property
    def executed_count(self) -> int:
        return sum(1 for a in self.actions if a.status == ActionStatus.EXECUTED)

    @property
    def failed_count(self) -> int:
        return sum(1 for a in self.actions if a.status == ActionStatus.FAILED)


# ═══════════════════════════════════════════════════════════════
# Risk Mapping
# ═══════════════════════════════════════════════════════════════

# 动作类型 → 风险等级
ACTION_RISK_MAP: dict[str, ActionRisk] = {
    "monitor_only": ActionRisk.LOW,
    "request_creative_analysis": ActionRisk.LOW,
    "generate_variants": ActionRisk.LOW,
    "expand_targeting": ActionRisk.MEDIUM,
    "change_audience": ActionRisk.MEDIUM,
    "adjust_bid": ActionRisk.MEDIUM,
    "reallocate_budget": ActionRisk.MEDIUM,
    "reduce_budget": ActionRisk.MEDIUM,
    "decrease_budget": ActionRisk.MEDIUM,
    "pause_low_performers": ActionRisk.HIGH,
    "pause_negative_roi": ActionRisk.HIGH,
    "pause_campaign": ActionRisk.HIGH,
    "optimize_store": ActionRisk.HIGH,
    "reallocate_to_winners": ActionRisk.MEDIUM,
    "escalate_to_supervisor": ActionRisk.LOW,
    "escalate_to_monetization": ActionRisk.LOW,
    "escalate_to_product": ActionRisk.LOW,
}

# 动作类型 → 回滚动作
ROLLBACK_MAP: dict[str, dict[str, Any]] = {
    "pause_campaign": {"action_type": "resume_campaign", "description": "恢复广告系列"},
    "pause_low_performers": {"action_type": "resume_low_performers", "description": "恢复低效系列"},
    "pause_negative_roi": {"action_type": "resume_negative_roi", "description": "恢复负ROI系列"},
    "adjust_bid": {"action_type": "restore_bid", "description": "恢复原始出价"},
    "reduce_budget": {"action_type": "restore_budget", "description": "恢复原始预算"},
    "decrease_budget": {"action_type": "restore_budget", "description": "恢复原始预算"},
    "reallocate_budget": {"action_type": "restore_allocation", "description": "恢复原始分配"},
    "change_audience": {"action_type": "restore_audience", "description": "恢复原始受众"},
    "expand_targeting": {"action_type": "restore_targeting", "description": "恢复原始定向"},
}


# ═══════════════════════════════════════════════════════════════
# UA Action Selector
# ═══════════════════════════════════════════════════════════════


class UAActionSelector:
    """UA 动作选择器 — 选择最优动作并生成执行计划.

    职责:
      1. 从策略列表中筛选可执行动作
      2. 去重合并相似动作
      3. 评估风险等级
      4. 生成回滚方案
      5. 生成执行计划

    用法:
        selector = UAActionSelector()
        plan = selector.select(strategies)
        # 执行
        for action in plan.actions:
            result = selector.execute(action)
    """

    def __init__(
        self,
        risk_threshold: ActionRisk = ActionRisk.HIGH,
        auto_approve_below: ActionRisk = ActionRisk.MEDIUM,
    ):
        self._risk_threshold = risk_threshold
        self._auto_approve_below = auto_approve_below
        self._history: list[SelectedAction] = []
        self._plans: list[ActionPlan] = []

    # ── 核心选择 ──────────────────────────────────────────────

    def select(
        self,
        strategies: list[UAStrategy],
        top_n: int = 10,
        deduplicate: bool = True,
    ) -> ActionPlan:
        """从策略中选择最优动作.

        Args:
            strategies: 策略列表
            top_n: 最多选择的动作数
            deduplicate: 是否去重

        Returns:
            ActionPlan: 执行计划
        """
        # 1. 展开所有策略动作为 SelectedAction
        actions = self._expand_actions(strategies)

        # 2. 按优先级排序
        actions.sort(key=lambda a: a.priority, reverse=True)

        # 3. 去重
        if deduplicate:
            actions = self._deduplicate(actions)

        # 4. 过滤风险
        actions = self._filter_by_risk(actions)

        # 5. 截取 Top N
        actions = actions[:top_n]

        # 6. 标记审批需求
        for a in actions:
            if a.risk.level >= self._risk_threshold.level:
                a.requires_approval = True
            elif a.risk.level <= self._auto_approve_below.level:
                a.status = ActionStatus.APPROVED

        # 7. 生成计划
        plan = self._build_plan(actions)
        self._plans.append(plan)
        self._history.extend(actions)
        return plan

    def select_from_dicts(
        self,
        strategies_data: list[dict[str, Any]],
        top_n: int = 10,
    ) -> ActionPlan:
        """从策略字典列表中选择."""
        strategies = []
        for sd in strategies_data:
            strategy = UAStrategy(
                strategy_id=sd.get("strategy_id", ""),
                strategy_type=StrategyType(sd.get("strategy_type", "monitor_only")),
                description=sd.get("description", ""),
                expected_impact=sd.get("expected_impact", ""),
                priority=sd.get("priority", 0.5),
                confidence=sd.get("confidence", 0.0),
                requires_approval=sd.get("requires_approval", False),
                actions=[
                    StrategyAction(
                        action_type=a.get("action_type", ""),
                        target=a.get("target", ""),
                        parameters=a.get("parameters", {}),
                        expected_impact=a.get("expected_impact", ""),
                        estimated_impact=a.get("estimated_impact", {}),
                        confidence=a.get("confidence", 0.0),
                    )
                    for a in sd.get("actions", [])
                ],
            )
            strategies.append(strategy)
        return self.select(strategies, top_n=top_n)

    # ── 动作展开 ──────────────────────────────────────────────

    def _expand_actions(self, strategies: list[UAStrategy]) -> list[SelectedAction]:
        """将策略展开为具体动作."""
        actions = []
        for strategy in strategies:
            for sa in strategy.actions:
                action = SelectedAction(
                    action_type=sa.action_type,
                    target=sa.target,
                    parameters=sa.parameters,
                    source_strategy=strategy.strategy_id,
                    priority=strategy.priority,
                    confidence=sa.confidence or strategy.confidence,
                    risk=ACTION_RISK_MAP.get(sa.action_type, ActionRisk.MEDIUM),
                    requires_approval=strategy.requires_approval,
                    rollback_action=ROLLBACK_MAP.get(
                        sa.action_type,
                        {"action_type": "manual_rollback", "description": "手动回滚"},
                    ),
                    expected_impact=sa.expected_impact,
                    metadata={
                        "strategy_type": strategy.strategy_type.value,
                        "strategy_description": strategy.description,
                        "estimated_impact": sa.estimated_impact,
                    },
                )
                actions.append(action)
        return actions

    # ── 去重 ──────────────────────────────────────────────────

    def _deduplicate(self, actions: list[SelectedAction]) -> list[SelectedAction]:
        """合并重复动作."""
        seen: dict[str, SelectedAction] = {}
        for action in actions:
            key = f"{action.action_type}:{action.target}"
            if key in seen:
                existing = seen[key]
                # 保留优先级更高的
                if action.priority > existing.priority:
                    seen[key] = action
                # 合并参数
                elif action.priority == existing.priority:
                    existing.parameters.update(action.parameters)
            else:
                seen[key] = action
        return list(seen.values())

    # ── 风险过滤 ──────────────────────────────────────────────

    def _filter_by_risk(self, actions: list[SelectedAction]) -> list[SelectedAction]:
        """过滤过高风险动作."""
        return [
            a for a in actions
            if a.risk.level <= self._risk_threshold.level
        ]

    # ── 计划生成 ──────────────────────────────────────────────

    def _build_plan(self, actions: list[SelectedAction]) -> ActionPlan:
        """生成执行计划."""
        summary_parts = []
        total_impact: dict[str, float] = {}

        for a in actions:
            summary_parts.append(
                f"[{a.risk.value}] {a.action_type} → {a.expected_impact[:40]}"
            )

            # 累计预期影响
            for key, val in a.metadata.get("estimated_impact", {}).items():
                total_impact[key] = total_impact.get(key, 0) + val

        summary = f"执行计划: {len(actions)} 个动作\n" + "\n".join(
            f"  {i+1}. {s}" for i, s in enumerate(summary_parts)
        )

        return ActionPlan(
            actions=actions,
            summary=summary,
            total_estimated_impact=total_impact,
        )

    # ── 执行接口 ──────────────────────────────────────────────

    def execute(
        self,
        action: SelectedAction,
        executor: Any = None,
    ) -> dict[str, Any]:
        """执行单个动作 (连接到 E13 GrowthDecisionExecutor).

        Args:
            action: 要执行的动作
            executor: 外部执行器 (GrowthDecisionExecutor)

        Returns:
            执行结果
        """
        action.status = ActionStatus.EXECUTING

        try:
            if executor and hasattr(executor, "execute"):
                result = executor.execute(action.to_dict())
                action.mark_executed(result)
                return {"success": True, "action_id": action.action_id, "result": result}
            else:
                # 无外部执行器时模拟执行
                result = {
                    "action_id": action.action_id,
                    "action_type": action.action_type,
                    "target": action.target,
                    "simulated": True,
                }
                action.mark_executed(result)
                return {"success": True, "action_id": action.action_id, "simulated": True, "result": result}
        except Exception as e:
            action.mark_failed(str(e))
            return {"success": False, "action_id": action.action_id, "error": str(e)}

    def execute_plan(
        self,
        plan: ActionPlan,
        executor: Any = None,
        stop_on_failure: bool = False,
    ) -> list[dict[str, Any]]:
        """执行整个计划.

        Args:
            plan: 执行计划
            executor: 外部执行器
            stop_on_failure: 失败时是否停止

        Returns:
            执行结果列表
        """
        results = []
        for action in plan.actions:
            result = self.execute(action, executor)
            results.append(result)
            if not result["success"] and stop_on_failure:
                break
        return results

    def rollback(
        self,
        action: SelectedAction,
        executor: Any = None,
    ) -> dict[str, Any]:
        """回滚动作.

        Args:
            action: 要回滚的动作
            executor: 外部执行器

        Returns:
            回滚结果
        """
        if not action.rollback_action:
            return {"success": False, "error": "No rollback action defined"}

        try:
            if executor and hasattr(executor, "execute"):
                result = executor.execute(action.rollback_action)
                action.mark_rolled_back()
                return {"success": True, "action_id": action.action_id, "result": result}
            else:
                action.mark_rolled_back()
                return {"success": True, "action_id": action.action_id, "simulated": True}
        except Exception as e:
            return {"success": False, "action_id": action.action_id, "error": str(e)}

    def rollback_plan(
        self,
        plan: ActionPlan,
        executor: Any = None,
    ) -> list[dict[str, Any]]:
        """回滚整个计划."""
        results = []
        for action in reversed(plan.actions):
            if action.status == ActionStatus.EXECUTED:
                result = self.rollback(action, executor)
                results.append(result)
        return results

    # ── 审批 ──────────────────────────────────────────────────

    def approve(self, action: SelectedAction) -> None:
        """审批动作."""
        action.mark_approved()

    def approve_plan(self, plan: ActionPlan) -> None:
        """审批整个计划."""
        for action in plan.actions:
            if action.requires_approval:
                action.mark_approved()

    def get_pending_approvals(self) -> list[SelectedAction]:
        """获取待审批动作."""
        return [
            a for a in self._history
            if a.status == ActionStatus.PENDING and a.requires_approval
        ]

    # ── 查询 ──────────────────────────────────────────────────

    def get_history(self, n: int = 20) -> list[SelectedAction]:
        return self._history[-n:]

    def get_plans(self, n: int = 10) -> list[ActionPlan]:
        return self._plans[-n:]

    def get_by_status(self, status: ActionStatus) -> list[SelectedAction]:
        return [a for a in self._history if a.status == status]

    def stats(self) -> dict[str, Any]:
        return {
            "total_actions": len(self._history),
            "executed": sum(1 for a in self._history if a.status == ActionStatus.EXECUTED),
            "failed": sum(1 for a in self._history if a.status == ActionStatus.FAILED),
            "rolled_back": sum(1 for a in self._history if a.status == ActionStatus.ROLLED_BACK),
            "pending": sum(1 for a in self._history if a.status == ActionStatus.PENDING),
            "plans": len(self._plans),
        }

    def reset(self) -> None:
        self._history.clear()
        self._plans.clear()