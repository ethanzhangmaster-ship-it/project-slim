"""E13.3.3 GrowthDecisionExecutor — 增长决策执行器.

核心职责:
  将 GrowthOpportunity 列表转换为可执行的 ExecutionAction 列表,
  并模拟执行生成 ExecutionResult.

输入:
  - list[GrowthOpportunity]: 增长机会列表

输出:
  - list[ExecutionAction]: 执行动作列表
  - list[ExecutionResult]: 执行结果列表
  - ExecutionBatch: 批量执行结果

流程:
  GrowthOpportunity
      ↓
  CreativeExecutor / UAExecutor / RevenueExecutor
      ↓
  ExecutionAction[]
      ↓
  _simulate_execute()
      ↓
  ExecutionResult[]
      ↓
  ExecutionBatch

连接:
  - E11 Evolution Engine (CreativeExecutor)
  - Meta Ads API (UAExecutor)
  - IAP/IAA/Retention Systems (RevenueExecutor)
"""

from __future__ import annotations

import time
from typing import Any

from .models import (
    ApprovalLevel,
    ExecutionAction,
    ExecutionActionType,
    ExecutionBatch,
    ExecutionResult,
    ExecutionStatus,
    GrowthOpportunity,
    OpportunityPriority,
    OpportunityType,
)
from .strategies import (
    CreativeExecutor,
    RevenueExecutor,
    UAExecutor,
)


class GrowthDecisionExecutor:
    """增长决策执行器 — 将机会转换为动作并执行.

    用法:
        executor = GrowthDecisionExecutor()
        batch = executor.execute(opportunities, product_id="p1")
    """

    def __init__(self, auto_execute: bool = False):
        """初始化执行器.

        Args:
            auto_execute: 是否自动执行 (True=模拟执行, False=仅生成动作)
        """
        self._creative_executor = CreativeExecutor()
        self._ua_executor = UAExecutor()
        self._revenue_executor = RevenueExecutor()
        self._auto_execute = auto_execute

    @property
    def auto_execute(self) -> bool:
        return self._auto_execute

    @auto_execute.setter
    def auto_execute(self, value: bool) -> None:
        self._auto_execute = value

    def execute(
        self,
        opportunities: list[GrowthOpportunity],
        product_id: str = "",
        date: str = "",
        auto_execute: bool | None = None,
    ) -> ExecutionBatch:
        """执行机会列表，生成执行动作和结果.

        Args:
            opportunities: GrowthOpportunity 列表
            product_id: 产品ID
            date: 执行日期
            auto_execute: 是否自动执行 (None=使用实例默认值)

        Returns:
            ExecutionBatch: 含完整执行动作和结果
        """
        start = time.perf_counter()

        do_execute = auto_execute if auto_execute is not None else self._auto_execute

        # Step 1: 将机会转换为执行动作
        actions = self._convert_opportunities(opportunities)

        # Step 2: 模拟执行 (或仅生成动作)
        if do_execute:
            results = self._simulate_execute(actions)
        else:
            results = []

        # Step 3: 统计
        total_success = sum(1 for r in results if r.success)
        total_failed = sum(1 for r in results if not r.success and r.status == ExecutionStatus.FAILED)
        total_rolled_back = sum(1 for r in results if r.rolled_back)

        summary: dict[str, int] = {}
        for action in actions:
            key = action.action_type.value
            summary[key] = summary.get(key, 0) + 1

        elapsed_ms = (time.perf_counter() - start) * 1000

        return ExecutionBatch(
            product_id=product_id,
            date=date,
            actions=actions,
            results=results,
            total_opportunities=len(opportunities),
            total_actions=len(actions),
            total_success=total_success,
            total_failed=total_failed,
            total_rolled_back=total_rolled_back,
            summary=summary,
            elapsed_ms=round(elapsed_ms, 2),
        )

    # ═══════════════════════════════════════════════════════════
    # Opportunity → Action Conversion
    # ═══════════════════════════════════════════════════════════

    def _convert_opportunities(
        self,
        opportunities: list[GrowthOpportunity],
    ) -> list[ExecutionAction]:
        """将机会列表转换为执行动作列表."""
        all_actions: list[ExecutionAction] = []

        for opp in opportunities:
            actions = self._route_opportunity(opp)
            all_actions.extend(actions)

        return all_actions

    def _route_opportunity(self, opportunity: GrowthOpportunity) -> list[ExecutionAction]:
        """根据机会类型路由到对应的执行器."""
        opp_type = opportunity.opportunity_type

        if opp_type in (
            OpportunityType.CREATIVE_SCALE,
            OpportunityType.CREATIVE_REFRESH,
            OpportunityType.CREATIVE_MUTATION,
        ):
            return self._creative_executor.execute(opportunity)
        elif opp_type in (
            OpportunityType.UA_SCALE,
            OpportunityType.BUDGET_REDUCTION,
            OpportunityType.UA_REBALANCE,
        ):
            return self._ua_executor.execute(opportunity)
        elif opp_type in (
            OpportunityType.MONETIZATION_OPTIMIZE,
            OpportunityType.MONETIZATION_SCALE,
        ):
            return self._revenue_executor.execute(opportunity)

        return []

    # ═══════════════════════════════════════════════════════════
    # Simulation Execution
    # ═══════════════════════════════════════════════════════════

    def _simulate_execute(self, actions: list[ExecutionAction]) -> list[ExecutionResult]:
        """模拟执行动作列表 (用于测试和开发).

        生产环境中，此方法会被替换为真实的 API 调用。
        """
        results: list[ExecutionResult] = []

        for action in actions:
            result = self._simulate_single_action(action)
            results.append(result)

        return results

    def _simulate_single_action(self, action: ExecutionAction) -> ExecutionResult:
        """模拟执行单个动作."""
        # 基于置信度和审批级别决定是否成功
        if action.approval_level == ApprovalLevel.AUTO:
            success = action.confidence > 0.4
        elif action.approval_level == ApprovalLevel.LOW:
            success = action.confidence > 0.5
        elif action.approval_level == ApprovalLevel.MEDIUM:
            success = action.confidence > 0.6
        elif action.approval_level == ApprovalLevel.HIGH:
            success = action.confidence > 0.7
        else:
            success = action.confidence > 0.8

        return ExecutionResult(
            action_id=action.action_id,
            action_type=action.action_type,
            status=ExecutionStatus.COMPLETED if success else ExecutionStatus.FAILED,
            success=success,
            output={
                "action_type": action.action_type.value,
                "entity_id": action.entity_id,
                "params": action.params,
            } if success else {},
            error="" if success else f"Simulated failure: confidence {action.confidence:.2f} below threshold",
            elapsed_ms=round(action.confidence * 100, 2),
            rolled_back=not success and action.rollback_action is not None,
        )

    # ═══════════════════════════════════════════════════════════
    # Convenience Methods
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def get_actions_by_type(
        actions: list[ExecutionAction],
        action_type: ExecutionActionType,
    ) -> list[ExecutionAction]:
        """按动作类型过滤."""
        return [a for a in actions if a.action_type == action_type]

    @staticmethod
    def get_actions_by_approval(
        actions: list[ExecutionAction],
        min_approval: ApprovalLevel = ApprovalLevel.MEDIUM,
    ) -> list[ExecutionAction]:
        """获取需要审批的动作 (>= min_approval)."""
        approval_order = {
            ApprovalLevel.AUTO: 0,
            ApprovalLevel.LOW: 1,
            ApprovalLevel.MEDIUM: 2,
            ApprovalLevel.HIGH: 3,
            ApprovalLevel.CRITICAL: 4,
        }
        threshold = approval_order.get(min_approval, 99)
        return [a for a in actions if approval_order.get(a.approval_level, 0) >= threshold]

    @staticmethod
    def get_autonomous_actions(
        actions: list[ExecutionAction],
    ) -> list[ExecutionAction]:
        """获取可自动执行的动作 (AUTO + LOW)."""
        return [a for a in actions if a.approval_level in (ApprovalLevel.AUTO, ApprovalLevel.LOW)]

    @staticmethod
    def get_actions_by_priority(
        actions: list[ExecutionAction],
        min_priority: OpportunityPriority = OpportunityPriority.HIGH,
    ) -> list[ExecutionAction]:
        """按最低优先级过滤."""
        priority_order = {
            OpportunityPriority.CRITICAL: 0,
            OpportunityPriority.HIGH: 1,
            OpportunityPriority.MEDIUM: 2,
            OpportunityPriority.LOW: 3,
        }
        threshold = priority_order.get(min_priority, 99)
        return [a for a in actions if priority_order.get(a.priority, 99) <= threshold]

    @staticmethod
    def get_successful_results(results: list[ExecutionResult]) -> list[ExecutionResult]:
        """获取成功的执行结果."""
        return [r for r in results if r.success]

    @staticmethod
    def get_failed_results(results: list[ExecutionResult]) -> list[ExecutionResult]:
        """获取失败的执行结果."""
        return [r for r in results if not r.success]

    @staticmethod
    def get_rolled_back_results(results: list[ExecutionResult]) -> list[ExecutionResult]:
        """获取已回滚的执行结果."""
        return [r for r in results if r.rolled_back]