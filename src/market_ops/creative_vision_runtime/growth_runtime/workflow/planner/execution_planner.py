"""E15.2.1 Execution Planner — 将 Growth Opportunity 转换为 ExecutionPlan.

ExecutionPlanner 是 E15.2.1 的核心入口，负责:
  1. 接收 GrowthOpportunity
  2. 查询 PatternMemory 获取历史最佳执行方案
  3. 选择匹配的 WorkflowTemplate
  4. 通过 TaskGenerator 生成任务列表
  5. 通过 SafetyValidator 验证计划安全性
  6. 输出 ExecutionPlan

架构:
  Growth Opportunity
      ↓
  PatternMemory.query() → 历史经验
      ↓
  TemplateRegistry.get_best_match() → 模板
      ↓
  TaskGenerator.generate() → 任务列表
      ↓
  SafetyValidator.validate() → 安全检查
      ↓
  ExecutionPlan

用法:
    planner = ExecutionPlanner()
    plan = planner.create_plan(opportunity)
    if plan.is_valid:
        workflow = planner.to_workflow_definition(plan)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .models import (
    ExecutionPlan,
    PlanStatus,
    PlanningTask,
    RiskLevel,
    WorkflowType,
)
from .planning_rules import SafetyValidator
from .task_generator import TaskGenerator
from .workflow_template import TemplateRegistry, WorkflowTemplate

if TYPE_CHECKING:
    from ..models import WorkflowDefinition, WorkflowTask


class ExecutionPlanner:
    """E15.2.1 执行规划器 — 机会 → 计划 → Workflow.

    用法:
        planner = ExecutionPlanner()
        plan = planner.create_plan(opportunity)
        workflow = planner.to_workflow_definition(plan)
    """

    def __init__(
        self,
        template_registry: TemplateRegistry | None = None,
        task_generator: TaskGenerator | None = None,
        safety_validator: SafetyValidator | None = None,
        pattern_store: Any = None,
    ):
        self._templates = template_registry or TemplateRegistry()
        self._generator = task_generator or TaskGenerator(self._templates)
        self._validator = safety_validator or SafetyValidator()
        self._pattern_store = pattern_store
        self._plan_history: list[ExecutionPlan] = []

    # ── Core API: Create Plan ─────────────────────────────────

    def create_plan(
        self,
        opportunity: Any,
        context: dict[str, Any] | None = None,
    ) -> ExecutionPlan:
        """从 GrowthOpportunity 创建 ExecutionPlan.

        这是 Planner 的核心入口方法。

        Args:
            opportunity: GrowthOpportunity 实例 (含 action, confidence, 等)
            context:     额外上下文

        Returns:
            ExecutionPlan: 完整的执行计划
        """
        ctx = context or {}

        # 1. 提取机会信息
        is_dict = isinstance(opportunity, dict)
        action_type = self._extract_action_type(opportunity)
        opportunity_id = opportunity.get("opportunity_id", "") if is_dict else getattr(opportunity, "opportunity_id", "")
        opportunity_type = opportunity.get("action", "") if is_dict else getattr(opportunity, "action", "")
        if hasattr(opportunity_type, "value"):
            opportunity_type = opportunity_type.value
        confidence = opportunity.get("confidence", 0.0) if is_dict else getattr(opportunity, "confidence", 0.0)
        severity = opportunity.get("severity", "medium") if is_dict else getattr(opportunity, "severity", "medium")
        if hasattr(severity, "value"):
            severity = severity.value

        # 2. 查询 Pattern Memory 增强
        pattern_boost = False
        pattern_score = 0.0
        pattern_success_rate = 0.0
        if self._pattern_store is not None:
            try:
                enhancement = self._pattern_store.enhance_decision(
                    opportunity_type=opportunity_type,
                    action_type=action_type,
                    base_confidence=confidence,
                )
                if enhancement and enhancement.get("matched_pattern"):
                    pattern_boost = True
                    pattern_score = enhancement.get("pattern_score", 0.0)
                    pattern_success_rate = enhancement.get("historical_success_rate", 0.0)
                    confidence = max(confidence, enhancement.get("enhanced_confidence", confidence))
            except Exception:
                pass

        # 3. 选择模板
        template = self._templates.get_best_match(action_type)
        if template is None:
            return self._create_fallback_plan(
                opportunity_id, opportunity_type, action_type, confidence, ctx
            )

        # 4. 生成任务
        tasks = self._generator.generate(template, ctx)

        # 5. 确定风险等级
        risk_level = self._determine_risk_level(template, severity, action_type)

        # 6. 构建计划
        plan = ExecutionPlan(
            opportunity_id=opportunity_id,
            opportunity_type=opportunity_type,
            action_type=action_type,
            workflow_type=template.workflow_type,
            template_name=template.name,
            tasks=tasks,
            confidence=round(confidence, 4),
            risk_level=risk_level,
            required_approval=template.requires_approval,
            pattern_boost=pattern_boost,
            pattern_score=pattern_score,
            pattern_success_rate=pattern_success_rate,
            context={
                "product_id": opportunity.get("product_id", "") if is_dict else getattr(opportunity, "product_id", ""),
                "creative_id": opportunity.get("creative_id", "") if is_dict else getattr(opportunity, "creative_id", ""),
                "budget_multiplier": opportunity.get("budget_multiplier", 1.0) if is_dict else getattr(opportunity, "budget_multiplier", 1.0),
                "target_budget": opportunity.get("target_budget", 0.0) if is_dict else getattr(opportunity, "target_budget", 0.0),
                "current_budget": opportunity.get("current_budget", 0.0) if is_dict else getattr(opportunity, "current_budget", 0.0),
                "severity": severity,
                **ctx,
            },
        )

        # 7. 验证
        errors = self._validator.validate(plan)
        plan.validation_errors = errors
        if not errors:
            plan.status = PlanStatus.VALIDATED
        else:
            plan.status = PlanStatus.REJECTED

        # 8. 记录历史
        self._plan_history.append(plan)

        return plan

    def create_plan_from_action(
        self,
        action_type: str,
        confidence: float = 0.0,
        context: dict[str, Any] | None = None,
    ) -> ExecutionPlan:
        """从 Action 类型直接创建计划 (无 Opportunity).

        用于测试和直接调用场景。

        Args:
            action_type: Action 类型
            confidence:  置信度
            context:     执行上下文

        Returns:
            ExecutionPlan
        """
        ctx = context or {}

        # 选择模板
        template = self._templates.get_best_match(action_type)
        if template is None:
            return ExecutionPlan(
                action_type=action_type,
                workflow_type=WorkflowType.CUSTOM,
                confidence=confidence,
                status=PlanStatus.REJECTED,
                validation_errors=[f"No template found for action '{action_type}'"],
            )

        # 生成任务
        tasks = self._generator.generate(template, ctx)

        # 风险等级
        risk_level = self._determine_risk_level(template, "medium", action_type)

        plan = ExecutionPlan(
            action_type=action_type,
            workflow_type=template.workflow_type,
            template_name=template.name,
            tasks=tasks,
            confidence=round(confidence, 4),
            risk_level=risk_level,
            required_approval=template.requires_approval,
            context=ctx,
        )

        # 验证
        errors = self._validator.validate(plan)
        plan.validation_errors = errors
        plan.status = PlanStatus.VALIDATED if not errors else PlanStatus.REJECTED

        self._plan_history.append(plan)
        return plan

    # ── Conversion: Plan → WorkflowDefinition ─────────────────

    def to_workflow_definition(self, plan: ExecutionPlan) -> WorkflowDefinition:
        """将 ExecutionPlan 转换为 WorkflowDefinition.

        Args:
            plan: ExecutionPlan

        Returns:
            WorkflowDefinition: 可供 E15.1 引擎执行的 Workflow
        """
        from ..models import WorkflowDefinition, WorkflowTask

        wf = WorkflowDefinition(
            name=f"{plan.workflow_type.value}_{plan.plan_id[:8]}",
            version="1.0.0",
            description=f"Auto-generated from plan: {plan.template_name}",
            metadata={
                "plan_id": plan.plan_id,
                "action_type": plan.action_type,
                "workflow_type": plan.workflow_type.value,
                "risk_level": plan.risk_level.value,
                "pattern_boost": plan.pattern_boost,
            },
        )

        # 添加任务
        for pt in plan.tasks:
            task = WorkflowTask(
                task_id=pt.task_id,
                name=pt.name,
                action_type=pt.action_type,
                depends_on=pt.depends_on,
                requires_approval=pt.requires_approval,
                parameters=pt.parameters,
                timeout_ms=pt.timeout_ms,
                retry_count=pt.retry_count,
                metadata={
                    "adapter": pt.adapter,
                    "phase": pt.phase,
                    "order": pt.order,
                },
            )
            wf.add_task(task)

        return wf

    # ── Query ─────────────────────────────────────────────────

    def get_plan_history(self, limit: int = 20) -> list[ExecutionPlan]:
        """获取历史计划."""
        return self._plan_history[-limit:]

    def get_supported_actions(self) -> list[str]:
        """获取支持的 Action 类型."""
        return self._templates.list_action_types()

    def get_template(self, name: str) -> WorkflowTemplate | None:
        """获取指定模板."""
        return self._templates.get(name)

    def list_templates(self) -> list[WorkflowTemplate]:
        """列出所有模板."""
        return self._templates.list_all()

    def validate_action(self, action_type: str, confidence: float = 0.0) -> list[str]:
        """验证 Action 是否安全 (不创建计划).

        Args:
            action_type: Action 类型
            confidence:  置信度

        Returns:
            list[str]: 违规列表
        """
        plan = self.create_plan_from_action(action_type, confidence)
        return plan.validation_errors

    # ── Internal ──────────────────────────────────────────────

    def _extract_action_type(self, opportunity: Any) -> str:
        """从 Opportunity 中提取 action_type."""
        if isinstance(opportunity, dict):
            action = opportunity.get("action_type", opportunity.get("action", ""))
            if hasattr(action, "value"):
                return action.value
            return str(action)
        action = getattr(opportunity, "action_type", "")
        if not action:
            action = getattr(opportunity, "action", "")
        if hasattr(action, "value"):
            return action.value
        return str(action)

    def _determine_risk_level(
        self,
        template: WorkflowTemplate,
        severity: str,
        action_type: str,
    ) -> RiskLevel:
        """综合模板和严重程度确定风险等级."""
        # 模板自带风险等级优先
        if template.risk_level != RiskLevel.LOW:
            return template.risk_level

        # 根据严重程度调整
        severity_map = {
            "critical": RiskLevel.CRITICAL,
            "high": RiskLevel.HIGH,
            "medium": RiskLevel.MEDIUM,
            "low": RiskLevel.LOW,
        }
        return severity_map.get(severity, template.risk_level)

    def _create_fallback_plan(
        self,
        opportunity_id: str,
        opportunity_type: str,
        action_type: str,
        confidence: float,
        context: dict[str, Any],
    ) -> ExecutionPlan:
        """无模板时的回退计划."""
        return ExecutionPlan(
            opportunity_id=opportunity_id,
            opportunity_type=opportunity_type,
            action_type=action_type,
            workflow_type=WorkflowType.CUSTOM,
            template_name="",
            confidence=confidence,
            risk_level=RiskLevel.MEDIUM,
            status=PlanStatus.REJECTED,
            validation_errors=[f"No template found for action '{action_type}'"],
            warnings=["No template matched — manual review required"],
            context=context,
        )


__all__ = ["ExecutionPlanner"]