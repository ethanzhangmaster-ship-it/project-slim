"""E13.6.1 Task Converter — Decision → ExecutionTask 桥接层.

将 E13.5.5 DecisionOutput 转换为 E13.6 可执行的 ExecutionTask。

核心映射:
  DecisionType.EXECUTE  → ExecutionTask (直接执行)
  DecisionType.TEST     → ExecutionTask (小预算测试)
  DecisionType.BLOCK    → ExecutionTask (CANCELLED)
  DecisionType.ESCALATE → ExecutionTask (PENDING + 审批标记)
  DecisionType.HOLD     → ExecutionTask (PENDING + 观察)

连接:
  E13.5.5 DecisionEngine → E13.6.1 TaskConverter → E13.6.3 Campaign/Creative/Budget Executor
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..intelligence.decision.models import DecisionOutput, DecisionPlan, DecisionType
from .models import (
    ExecutionAction,
    ExecutionActionType,
    ExecutionDomain,
    ExecutionPlan,
    ExecutionPriority,
    ExecutionStatus,
    ExecutionTask,
)


class TaskConverter:
    """任务转换器 — 将 DecisionOutput 转换为 ExecutionTask.

    用法:
        converter = TaskConverter()
        task = converter.convert(decision_output)
        plan = converter.convert_to_plan(decision_output)
    """

    # ── 默认配置 ──────────────────────────────────────────────

    # 决策类型 → 执行优先级映射
    _PRIORITY_MAP: dict[str, ExecutionPriority] = {
        "execute": ExecutionPriority.HIGH,
        "test": ExecutionPriority.MEDIUM,
        "hold": ExecutionPriority.LOW,
        "block": ExecutionPriority.LOW,
        "escalate": ExecutionPriority.HIGH,
    }

    # 决策类型 → 默认时长 (小时)
    _DURATION_MAP: dict[str, float] = {
        "execute": 168.0,   # 7 天
        "test": 72.0,       # 3 天
        "hold": 0.0,        # 不执行
        "block": 0.0,       # 不执行
        "escalate": 0.0,    # 等待审批
    }

    # 默认测试配置
    default_test_creative_count: int = 5
    default_test_budget: float = 500.0
    default_test_duration_days: int = 3

    # 默认执行配置
    default_execute_budget: float = 2000.0
    default_execute_duration_days: int = 7

    def __init__(
        self,
        default_test_creative_count: int = 5,
        default_test_budget: float = 500.0,
        default_test_duration_days: int = 3,
        default_execute_budget: float = 2000.0,
        default_execute_duration_days: int = 7,
    ):
        self.default_test_creative_count = default_test_creative_count
        self.default_test_budget = default_test_budget
        self.default_test_duration_days = default_test_duration_days
        self.default_execute_budget = default_execute_budget
        self.default_execute_duration_days = default_execute_duration_days

    # ═══════════════════════════════════════════════════════════
    # 主入口
    # ═══════════════════════════════════════════════════════════

    def convert(self, decision: DecisionOutput) -> ExecutionTask:
        """将 DecisionOutput 转换为 ExecutionTask.

        Args:
            decision: E13.5.5 决策输出

        Returns:
            ExecutionTask: 可执行的任务
        """
        dt = decision.decision_type

        if dt == DecisionType.EXECUTE:
            return self._convert_execute(decision)
        elif dt == DecisionType.TEST:
            return self._convert_test(decision)
        elif dt == DecisionType.BLOCK:
            return self._convert_block(decision)
        elif dt == DecisionType.ESCALATE:
            return self._convert_escalate(decision)
        elif dt == DecisionType.HOLD:
            return self._convert_hold(decision)
        else:
            return self._convert_hold(decision)

    def convert_to_plan(self, decision: DecisionOutput) -> ExecutionPlan:
        """将 DecisionOutput 转换为 ExecutionPlan (多步骤).

        Args:
            decision: E13.5.5 决策输出

        Returns:
            ExecutionPlan: 包含多个步骤的执行计划
        """
        task = self.convert(decision)
        plan = ExecutionPlan(decision_id=decision.decision_id)
        plan.add_task(task)
        return plan

    def convert_batch(
        self,
        decisions: list[DecisionOutput],
    ) -> list[ExecutionTask]:
        """批量转换决策.

        Args:
            decisions: 决策列表

        Returns:
            list[ExecutionTask]: 任务列表
        """
        return [self.convert(d) for d in decisions]

    # ═══════════════════════════════════════════════════════════
    # 各决策类型转换
    # ═══════════════════════════════════════════════════════════

    def _convert_execute(self, decision: DecisionOutput) -> ExecutionTask:
        """EXECUTE → ExecutionTask (直接执行)."""
        task = self._create_base_task(decision, ExecutionStatus.PENDING)

        plan = decision.action_plan
        strategy_name = decision.strategy_name.lower()

        actions = self._build_execute_actions(decision, plan)
        task.actions = actions
        task.estimated_duration_hours = self._DURATION_MAP["execute"]
        task.deadline = self._compute_deadline(self._DURATION_MAP["execute"])

        # 生成回滚计划
        task.rollback_plan = self._build_rollback_plan(actions)

        return task

    def _convert_test(self, decision: DecisionOutput) -> ExecutionTask:
        """TEST → ExecutionTask (小预算测试)."""
        task = self._create_base_task(decision, ExecutionStatus.PENDING)
        plan = decision.action_plan

        actions = self._build_test_actions(decision, plan)
        task.actions = actions
        task.estimated_duration_hours = self._DURATION_MAP["test"]
        task.deadline = self._compute_deadline(self._DURATION_MAP["test"])

        # 测试任务也需要回滚
        task.rollback_plan = self._build_rollback_plan(actions)

        return task

    def _convert_block(self, decision: DecisionOutput) -> ExecutionTask:
        """BLOCK → ExecutionTask (CANCELLED)."""
        task = self._create_base_task(decision, ExecutionStatus.CANCELLED)
        task.error_message = "决策被风险控制拦截: risk_score too high"
        return task

    def _convert_escalate(self, decision: DecisionOutput) -> ExecutionTask:
        """ESCALATE → ExecutionTask (PENDING + 审批)."""
        task = self._create_base_task(decision, ExecutionStatus.PENDING)
        task.requires_approval = True
        task.metadata["escalation_reason"] = "决策需要人工确认"
        return task

    def _convert_hold(self, decision: DecisionOutput) -> ExecutionTask:
        """HOLD → ExecutionTask (PENDING + 观察)."""
        task = self._create_base_task(decision, ExecutionStatus.PENDING)
        task.metadata["observation"] = True
        task.metadata["hold_reason"] = "置信度不足，保持观察"

        # 添加监控动作
        task.actions = [self._create_monitor_action(decision)]
        return task

    # ═══════════════════════════════════════════════════════════
    # Action 构建
    # ═══════════════════════════════════════════════════════════

    def _build_execute_actions(
        self,
        decision: DecisionOutput,
        plan: DecisionPlan | None,
    ) -> list[ExecutionAction]:
        """构建 EXECUTE 模式的动作序列."""
        actions: list[ExecutionAction] = []
        strategy = decision.strategy_name.lower()

        if "creative" in strategy or "mutation" in strategy or "mutate" in strategy:
            # 素材相关: 生成 → 上传 → 创建 Campaign
            actions.append(self._create_mutate_action(decision, plan))
            actions.append(self._create_upload_action(decision))
            actions.append(self._create_campaign_action(decision, plan))
        elif "budget" in strategy or "scale" in strategy:
            # 预算相关: 直接调整预算
            actions.append(self._create_scale_budget_action(decision, plan))
        elif "audience" in strategy:
            # 受众相关: 更新 Campaign
            actions.append(self._create_campaign_action(decision, plan))
        else:
            # 通用: 创建 Campaign + 监控
            actions.append(self._create_campaign_action(decision, plan))
            actions.append(self._create_monitor_action(decision))

        return actions

    def _build_test_actions(
        self,
        decision: DecisionOutput,
        plan: DecisionPlan | None,
    ) -> list[ExecutionAction]:
        """构建 TEST 模式的动作序列."""
        actions: list[ExecutionAction] = []
        strategy = decision.strategy_name.lower()

        if "creative" in strategy or "mutation" in strategy or "mutate" in strategy:
            # 小批量素材变异
            actions.append(self._create_mutate_action(decision, plan, is_test=True))
            actions.append(self._create_upload_action(decision))
            actions.append(self._create_campaign_action(decision, plan, is_test=True))
        elif "budget" in strategy:
            actions.append(self._create_scale_budget_action(decision, plan, is_test=True))
        else:
            actions.append(self._create_campaign_action(decision, plan, is_test=True))

        # 测试任务统一追加监控
        actions.append(self._create_monitor_action(decision, is_test=True))

        return actions

    def _build_rollback_plan(
        self,
        actions: list[ExecutionAction],
    ) -> list[dict[str, Any]]:
        """生成回滚计划."""
        rollback: list[dict[str, Any]] = []
        for action in actions:
            if action.action_type in {
                ExecutionActionType.CREATE_CAMPAIGN,
                ExecutionActionType.CREATE_AD_SET,
                ExecutionActionType.SCALE_BUDGET,
            }:
                rollback.append({
                    "action_id": action.action_id,
                    "rollback_type": "pause_campaign",
                    "target_entity": action.target_entity,
                    "reason": f"自动回滚: {action.action_type.value}",
                })
        return rollback

    # ═══════════════════════════════════════════════════════════
    # 单个 Action 工厂方法
    # ═══════════════════════════════════════════════════════════

    def _create_mutate_action(
        self,
        decision: DecisionOutput,
        plan: DecisionPlan | None,
        is_test: bool = False,
    ) -> ExecutionAction:
        """创建素材变异 Action."""
        count = self.default_test_creative_count if is_test else self.default_test_creative_count * 2
        if plan and plan.params:
            count = plan.params.get("generate_creatives", count)

        return ExecutionAction(
            action_type=ExecutionActionType.MUTATE_CREATIVE,
            domain=ExecutionDomain.CREATIVE,
            target_entity=plan.target_entity_id if plan else "",
            target_entity_type="creative",
            parameters={
                "count": count,
                "strategy_id": decision.strategy_id,
                "mode": "test" if is_test else "execute",
            },
            priority=self._PRIORITY_MAP.get(decision.decision_type.value, ExecutionPriority.MEDIUM),
        )

    def _create_upload_action(self, decision: DecisionOutput) -> ExecutionAction:
        """创建上传素材 Action."""
        return ExecutionAction(
            action_type=ExecutionActionType.UPLOAD_CREATIVE,
            domain=ExecutionDomain.CREATIVE,
            target_entity_type="creative",
            parameters={"source": "dna_evolution"},
            priority=ExecutionPriority.HIGH,
        )

    def _create_campaign_action(
        self,
        decision: DecisionOutput,
        plan: DecisionPlan | None,
        is_test: bool = False,
    ) -> ExecutionAction:
        """创建 Campaign Action."""
        budget = plan.test_budget if (is_test and plan) else (
            plan.execute_budget if plan else self.default_execute_budget
        )
        if budget <= 0:
            budget = self.default_test_budget if is_test else self.default_execute_budget

        return ExecutionAction(
            action_type=ExecutionActionType.CREATE_CAMPAIGN if not plan or not plan.target_entity_id
            else ExecutionActionType.UPDATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
            target_entity=plan.target_entity_id if plan else "",
            target_entity_type="campaign",
            parameters={
                "budget": budget,
                "strategy_id": decision.strategy_id,
                "mode": "test" if is_test else "execute",
                "duration_days": plan.duration_days if plan else 7,
            },
            priority=ExecutionPriority.HIGH,
        )

    def _create_scale_budget_action(
        self,
        decision: DecisionOutput,
        plan: DecisionPlan | None,
        is_test: bool = False,
    ) -> ExecutionAction:
        """创建预算调整 Action."""
        budget = plan.test_budget if (is_test and plan) else (
            plan.execute_budget if plan else self.default_execute_budget
        )

        return ExecutionAction(
            action_type=ExecutionActionType.SCALE_BUDGET if not is_test
            else ExecutionActionType.UPDATE_BUDGET,
            domain=ExecutionDomain.BUDGET,
            target_entity=plan.target_entity_id if plan else "",
            target_entity_type="campaign",
            parameters={
                "budget": budget,
                "mode": "test" if is_test else "execute",
            },
            priority=ExecutionPriority.HIGH,
        )

    def _create_monitor_action(
        self,
        decision: DecisionOutput,
        is_test: bool = False,
    ) -> ExecutionAction:
        """创建监控 Action."""
        duration = self.default_test_duration_days if is_test else self.default_execute_duration_days
        return ExecutionAction(
            action_type=ExecutionActionType.MONITOR,
            domain=ExecutionDomain.MONITOR,
            target_entity_type="campaign",
            parameters={
                "duration_days": duration,
                "metrics": ["ctr", "cvr", "roas", "spend", "revenue"],
            },
            priority=ExecutionPriority.MEDIUM,
        )

    # ═══════════════════════════════════════════════════════════
    # 辅助
    # ═══════════════════════════════════════════════════════════

    def _create_base_task(
        self,
        decision: DecisionOutput,
        status: ExecutionStatus,
    ) -> ExecutionTask:
        """创建基础任务."""
        dt = decision.decision_type.value if isinstance(decision.decision_type, DecisionType) else str(decision.decision_type)
        return ExecutionTask(
            decision_id=decision.decision_id,
            opportunity_id=decision.opportunity_id,
            strategy_id=decision.strategy_id,
            strategy_name=decision.strategy_name,
            decision_type=dt,
            status=status,
            priority=self._PRIORITY_MAP.get(dt, ExecutionPriority.MEDIUM),
            requires_approval=decision.requires_approval,
            risk_level=decision.risk_level,
            metadata=decision.metadata,
        )

    def _compute_deadline(self, hours: float) -> str:
        """计算截止时间."""
        if hours <= 0:
            return ""
        deadline = datetime.now(timezone.utc) + timedelta(hours=hours)
        return deadline.isoformat()

    @staticmethod
    def _extract_strategy_domain(strategy_name: str) -> ExecutionDomain:
        """从策略名称推断执行领域."""
        name = strategy_name.lower()
        if "creative" in name or "mutation" in name or "mutate" in name:
            return ExecutionDomain.CREATIVE
        if "budget" in name or "scale" in name:
            return ExecutionDomain.BUDGET
        if "campaign" in name or "audience" in name:
            return ExecutionDomain.CAMPAIGN
        return ExecutionDomain.CAMPAIGN