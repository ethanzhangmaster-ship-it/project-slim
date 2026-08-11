"""E15.4 Execution Trigger — Reality Signal → Execution Bridge.

将 Reality Layer (E12/E13) 的信号和机会转换为 E15 Execution Layer
可执行的 Workflow，是 Autonomous Growth Loop 的最后一公里桥接。

核心职责:
  1. 接收 GrowthOpportunity 列表 (来自 E13 OpportunityDetector)
  2. 将 Opportunity ActionType 映射为 E15 Template action_type
  3. 委托 ExecutionPlanner 创建 ExecutionPlan
  4. 生成 ExecutionContext 并关联到 Workflow
  5. 返回 ExecutionPlan 供 Scheduler 调度执行

数据流:
  RealityDataHub
      ↓
  OpportunityDetector.detect()
      ↓
  GrowthOpportunity[]
      ↓
  ExecutionTrigger.trigger()          ← 本模块
      ↓
  ExecutionPlanner.create_plan()
      ↓
  ExecutionPlan
      ↓
  ExecutionContext + Scheduler
      ↓
  Real Execution

用法:
    trigger = ExecutionTrigger()
    plans = trigger.trigger(opportunities)
    for plan in plans:
        if plan.is_valid:
            ctx = trigger.create_context(plan)
            scheduler.submit(ctx)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .context import ExecutionContext
from .planner.execution_planner import ExecutionPlanner
from .planner.models import ExecutionPlan, PlanStatus

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Opportunity → Template Action 映射表
# ═══════════════════════════════════════════════════════════════

# E13 OpportunityDetector ActionType → E15 Template action_type
# 注意: E13 使用 ActionType 枚举 (SCALE, STOP, PAUSE, MUTATE...)
#       E15 使用字符串 action_type (scale, pause_campaign, replace_creative...)
OPPORTUNITY_TO_TEMPLATE: dict[str, str] = {
    # 放量
    "scale": "scale",
    "SCALE": "scale",
    # 停投
    "stop": "pause_campaign",
    "STOP": "pause_campaign",
    # 暂停
    "pause": "pause_campaign",
    "PAUSE": "pause_campaign",
    # 变异/刷新
    "mutate": "replace_creative",
    "MUTATE": "replace_creative",
    # 加预算
    "increase_budget": "increase_budget",
    "INCREASE_BUDGET": "increase_budget",
    # 减预算
    "decrease_budget": "increase_budget",
    "DECREASE_BUDGET": "increase_budget",
    # 实验
    "launch_experiment": "replace_creative",
    "LAUNCH_EXPERIMENT": "replace_creative",
    # 复制 Winner
    "duplicate_winner": "scale",
    "DUPLICATE_WINNER": "scale",
}

# 信号严重程度 → 优先级映射
SEVERITY_TO_PRIORITY: dict[str, str] = {
    "critical": "critical",
    "CRITICAL": "critical",
    "high": "high",
    "HIGH": "high",
    "medium": "medium",
    "MEDIUM": "medium",
    "low": "low",
    "LOW": "low",
}


# ═══════════════════════════════════════════════════════════════
# Trigger Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class TriggerResult:
    """触发结果 — 封装一次 trigger 的输出.

    Attributes:
        trigger_id:      触发 ID
        opportunity_id:  来源 Opportunity ID
        plan:            生成的 ExecutionPlan
        mapped_action:   映射后的 action_type
        confidence:      置信度
        priority:        优先级
        created_at:      创建时间
        metadata:        扩展元数据
    """

    trigger_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    opportunity_id: str = ""
    plan: ExecutionPlan | None = None
    mapped_action: str = ""
    confidence: float = 0.0
    priority: str = "medium"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return self.plan is not None and self.plan.status == PlanStatus.VALIDATED

    @property
    def is_rejected(self) -> bool:
        return self.plan is not None and self.plan.status == PlanStatus.REJECTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "opportunity_id": self.opportunity_id,
            "mapped_action": self.mapped_action,
            "confidence": self.confidence,
            "priority": self.priority,
            "is_valid": self.is_valid,
            "is_rejected": self.is_rejected,
            "plan": self.plan.to_dict() if self.plan else None,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        status = "valid" if self.is_valid else ("rejected" if self.is_rejected else "no_plan")
        return (
            f"TriggerResult(id={self.trigger_id[:8]}..., "
            f"action={self.mapped_action}, "
            f"status={status})"
        )


# ═══════════════════════════════════════════════════════════════
# Execution Trigger
# ═══════════════════════════════════════════════════════════════


class ExecutionTrigger:
    """E15.4 Execution Trigger — Reality → Execution 桥接器.

    将 E13 OpportunityDetector 的输出转换为 E15 ExecutionPlan，
    是 Autonomous Growth Loop 从"看到世界"到"改变世界"的关键桥接。

    Attributes:
        planner:        ExecutionPlanner 实例
        action_map:     Opportunity → Template action 映射表
        min_confidence: 最低置信度阈值
        trigger_history: 触发历史
    """

    # 默认阈值
    DEFAULT_MIN_CONFIDENCE = 0.5
    DEFAULT_MAX_PLANS_PER_TRIGGER = 10

    def __init__(
        self,
        planner: ExecutionPlanner | None = None,
        min_confidence: float = 0.5,
        max_plans_per_trigger: int = 10,
    ):
        self._planner = planner or ExecutionPlanner()
        self._min_confidence = min_confidence
        self._max_plans_per_trigger = max_plans_per_trigger
        self._trigger_history: list[TriggerResult] = []
        self._total_triggers: int = 0

    # ── Core API: trigger ─────────────────────────────────────

    def trigger(
        self,
        opportunities: list[Any],
        context: dict[str, Any] | None = None,
    ) -> list[TriggerResult]:
        """将 Opportunity 列表转换为 ExecutionPlan 列表.

        这是 ExecutionTrigger 的核心入口方法。

        Args:
            opportunities: GrowthOpportunity 列表 (或 dict 列表)
            context:       全局上下文 (game_id, product_id 等)

        Returns:
            list[TriggerResult]: 触发结果列表 (按优先级排序)
        """
        if not opportunities:
            logger.debug("ExecutionTrigger: no opportunities to trigger")
            return []

        ctx = context or {}
        results: list[TriggerResult] = []

        for opp in opportunities:
            result = self._trigger_single(opp, ctx)
            if result is not None:
                results.append(result)

        # 限制最大计划数
        if len(results) > self._max_plans_per_trigger:
            results = results[:self._max_plans_per_trigger]

        # 按优先级排序 (critical > high > medium > low)
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        results.sort(key=lambda r: (priority_order.get(r.priority, 99), -r.confidence))

        self._total_triggers += 1
        self._trigger_history.extend(results)

        valid_count = sum(1 for r in results if r.is_valid)
        logger.info(
            f"ExecutionTrigger: {len(results)} opportunities → "
            f"{valid_count} valid plans, "
            f"{len(results) - valid_count} rejected"
        )

        return results

    def trigger_from_snapshot(
        self,
        snapshot: Any,
        detector: Any = None,
        context: dict[str, Any] | None = None,
    ) -> list[TriggerResult]:
        """从 RealitySnapshot 直接触发 (一站式).

        流程:
          RealitySnapshot → OpportunityDetector → ExecutionTrigger → ExecutionPlan

        Args:
            snapshot:  RealitySnapshot (来自 RealityDataHub)
            detector:  OpportunityDetector 实例 (可选, 如果提供则自动检测)
            context:   全局上下文

        Returns:
            list[TriggerResult]
        """
        if detector is None:
            logger.warning(
                "ExecutionTrigger.trigger_from_snapshot: no detector provided, "
                "returning empty"
            )
            return []

        # 从 Snapshot 提取市场信号
        market_signal = None
        if hasattr(snapshot, "creatives"):
            # RealitySnapshot 有 creatives 属性
            market_signal = {
                "snapshot_id": getattr(snapshot, "snapshot_id", ""),
                "total_roi": getattr(snapshot, "total_roi", 0.0),
                "total_spend": getattr(snapshot, "total_spend", 0.0),
                "total_revenue": getattr(snapshot, "total_revenue", 0.0),
                "campaign_count": len(getattr(snapshot, "campaigns", [])),
                "creative_count": len(getattr(snapshot, "creatives", [])),
            }

        # 使用 detector 检测机会
        try:
            opportunities = detector.detect_from_snapshot(snapshot)
        except AttributeError:
            # detector 可能没有 detect_from_snapshot 方法, 尝试 detect
            logger.warning(
                "detector has no detect_from_snapshot, trying detect()"
            )
            opportunities = []

        if not opportunities:
            logger.info("ExecutionTrigger: no opportunities detected from snapshot")
            return []

        ctx_with_signal = {
            **(context or {}),
            "market_signal": market_signal,
            "source": "reality_snapshot",
        }

        return self.trigger(opportunities, ctx_with_signal)

    # ── Context Creation ──────────────────────────────────────

    def create_context(
        self,
        plan: ExecutionPlan,
        variables: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionContext:
        """从 ExecutionPlan 创建 ExecutionContext.

        Args:
            plan:      ExecutionPlan
            variables: 初始变量
            metadata:  元数据

        Returns:
            ExecutionContext: 可提交给 Scheduler 的上下文
        """
        # 将 Plan 转为 WorkflowDefinition
        wf = self._planner.to_workflow_definition(plan)

        # 创建 ExecutionContext
        ctx = ExecutionContext.from_definition(
            wf,
            variables=variables or {},
            metadata={
                "plan_id": plan.plan_id,
                "action_type": plan.action_type,
                "workflow_type": plan.workflow_type.value,
                "risk_level": plan.risk_level.value,
                "confidence": plan.confidence,
                **(metadata or {}),
            },
        )

        return ctx

    def create_contexts(
        self,
        results: list[TriggerResult],
        variables: dict[str, Any] | None = None,
    ) -> list[ExecutionContext]:
        """批量创建 ExecutionContext.

        Args:
            results:   TriggerResult 列表
            variables: 共享变量

        Returns:
            list[ExecutionContext]: 仅包含有效计划的上下文
        """
        contexts: list[ExecutionContext] = []
        for result in results:
            if result.is_valid and result.plan is not None:
                ctx = self.create_context(
                    result.plan,
                    variables=variables,
                    metadata={
                        "trigger_id": result.trigger_id,
                        "opportunity_id": result.opportunity_id,
                    },
                )
                contexts.append(ctx)
        return contexts

    # ── Query ─────────────────────────────────────────────────

    def get_history(self, limit: int = 20) -> list[TriggerResult]:
        """获取触发历史."""
        return self._trigger_history[-limit:]

    def get_valid_plans(self) -> list[ExecutionPlan]:
        """获取所有有效计划."""
        return [
            r.plan for r in self._trigger_history
            if r.is_valid and r.plan is not None
        ]

    def get_supported_actions(self) -> list[str]:
        """获取支持的 Action 映射."""
        return list(OPPORTUNITY_TO_TEMPLATE.keys())

    def stats(self) -> dict[str, Any]:
        """获取触发器统计."""
        valid = sum(1 for r in self._trigger_history if r.is_valid)
        rejected = sum(1 for r in self._trigger_history if r.is_rejected)
        no_plan = len(self._trigger_history) - valid - rejected

        by_action: dict[str, int] = {}
        for r in self._trigger_history:
            a = r.mapped_action or "unknown"
            by_action[a] = by_action.get(a, 0) + 1

        return {
            "total_triggers": self._total_triggers,
            "total_results": len(self._trigger_history),
            "valid_plans": valid,
            "rejected_plans": rejected,
            "no_plan": no_plan,
            "by_action": by_action,
            "avg_confidence": round(
                sum(r.confidence for r in self._trigger_history)
                / max(len(self._trigger_history), 1),
                4,
            ),
        }

    def reset(self) -> None:
        """重置状态."""
        self._trigger_history.clear()
        self._total_triggers = 0

    # ── Internal ──────────────────────────────────────────────

    def _trigger_single(
        self,
        opportunity: Any,
        context: dict[str, Any],
    ) -> TriggerResult | None:
        """处理单个 Opportunity.

        Args:
            opportunity: GrowthOpportunity 实例或 dict
            context:     全局上下文

        Returns:
            TriggerResult | None: 置信度不足时返回 None
        """
        # 提取 opportunity 信息
        is_dict = isinstance(opportunity, dict)

        # 提取 ActionType
        action = (
            opportunity.get("action", "")
            if is_dict
            else getattr(opportunity, "action", "")
        )
        if hasattr(action, "value"):
            action = action.value

        # 提取置信度
        confidence = (
            opportunity.get("confidence", 0.0)
            if is_dict
            else getattr(opportunity, "confidence", 0.0)
        )

        # 置信度过滤
        if confidence < self._min_confidence:
            logger.debug(
                f"ExecutionTrigger: skipping low-confidence opportunity "
                f"(conf={confidence:.2f} < {self._min_confidence})"
            )
            return None

        # 提取 ID
        opportunity_id = (
            opportunity.get("opportunity_id", "")
            if is_dict
            else getattr(opportunity, "opportunity_id", "")
        )

        # 提取严重程度
        severity = (
            opportunity.get("severity", "medium")
            if is_dict
            else getattr(opportunity, "severity", "medium")
        )
        if hasattr(severity, "value"):
            severity = severity.value

        # 映射 action → template action_type
        mapped_action = OPPORTUNITY_TO_TEMPLATE.get(action, action)

        # 映射 severity → priority
        priority = SEVERITY_TO_PRIORITY.get(severity, "medium")

        # 构建 planner context
        planner_context = {
            "game_id": context.get("game_id", ""),
            "product_id": (
                opportunity.get("product_id", "")
                if is_dict
                else getattr(opportunity, "product_id", "")
            ),
            "creative_id": (
                opportunity.get("creative_id", "")
                if is_dict
                else getattr(opportunity, "creative_id", "")
            ),
            "target_budget": (
                opportunity.get("target_budget", 0.0)
                if is_dict
                else getattr(opportunity, "target_budget", 0.0)
            ),
            "current_budget": (
                opportunity.get("current_budget", 0.0)
                if is_dict
                else getattr(opportunity, "current_budget", 0.0)
            ),
            "budget_multiplier": (
                opportunity.get("budget_multiplier", 1.0)
                if is_dict
                else getattr(opportunity, "budget_multiplier", 1.0)
            ),
            "reason": (
                opportunity.get("reason", "")
                if is_dict
                else getattr(opportunity, "reason", "")
            ),
            "severity": severity,
            "source": "execution_trigger",
            **context,
        }

        # 委托 Planner 创建计划
        # 将 opportunity 包装为 planner 期望的格式
        planner_input = _to_planner_input(opportunity, mapped_action, confidence)

        plan = self._planner.create_plan(planner_input, planner_context)

        result = TriggerResult(
            opportunity_id=opportunity_id,
            plan=plan,
            mapped_action=mapped_action,
            confidence=confidence,
            priority=priority,
            metadata={
                "original_action": action,
                "severity": severity,
                "context": planner_context,
            },
        )

        return result

    def __repr__(self) -> str:
        return (
            f"ExecutionTrigger(triggers={self._total_triggers}, "
            f"history={len(self._trigger_history)})"
        )


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _to_planner_input(
    opportunity: Any,
    mapped_action: str,
    confidence: float,
) -> dict[str, Any]:
    """将 Opportunity 转换为 Planner 可接受的输入格式.

    ExecutionPlanner.create_plan() 期望:
      - opportunity_id: str
      - action: str (action_type)
      - confidence: float
      - severity: str
      - ... 其他字段

    Args:
        opportunity:  原始 GrowthOpportunity
        mapped_action: 映射后的 action_type
        confidence:   置信度

    Returns:
        dict: Planner 兼容的输入
    """
    is_dict = isinstance(opportunity, dict)

    base = {
        "action_type": mapped_action,
        "action": mapped_action,
        "confidence": confidence,
    }

    # 复制所有相关字段
    for field in [
        "opportunity_id", "creative_id", "creative_name",
        "product_id", "reason", "severity",
        "expected_impact", "budget_multiplier",
        "target_budget", "current_budget",
    ]:
        if is_dict:
            val = opportunity.get(field)
            if val is not None:
                base[field] = val
        else:
            val = getattr(opportunity, field, None)
            if val is not None:
                base[field] = val.value if hasattr(val, "value") else val

    return base


def map_action_to_template(action: str) -> str:
    """将 Opportunity ActionType 映射为 Template action_type.

    Args:
        action: E13 ActionType 值 (如 "SCALE", "PAUSE", "MUTATE")

    Returns:
        str: E15 Template action_type (如 "scale", "pause_campaign", "replace_creative")
    """
    return OPPORTUNITY_TO_TEMPLATE.get(action, action)


__all__ = [
    "ExecutionTrigger",
    "TriggerResult",
    "OPPORTUNITY_TO_TEMPLATE",
    "SEVERITY_TO_PRIORITY",
    "map_action_to_template",
]