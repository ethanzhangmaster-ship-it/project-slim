"""E15.2.1 Workflow Template System — 结构化 Workflow 模板.

模板系统约束 Planner 的输出，确保生成的 Workflow 符合业务规范。

核心组件:
  - WorkflowTemplate: 单条模板定义
  - TemplateRegistry: 模板注册与查询

内置模板:
  - creative_refresh:  素材刷新 (生成→验证→上传→测试→监控)
  - budget_optimize:   预算优化 (分析→调整→监控→回滚)
  - campaign_pause:    暂停止损 (验证→暂停→记录→监控)
  - campaign_scale:    放量扩量 (分析→放量→监控→回调)
  - audience_expand:   受众扩展 (分析→创建→测试→监控)
  - revenue_optimize:  收入优化 (分析→调价→监控)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import PlanningTask, RiskLevel, WorkflowType


# ═══════════════════════════════════════════════════════════════
# Workflow Template
# ═══════════════════════════════════════════════════════════════


@dataclass
class WorkflowTemplate:
    """E15.2.1 Workflow 模板 — 一种 Action 的标准执行流程.

    Attributes:
        name:              模板名称
        workflow_type:     Workflow 类型
        action_type:       匹配的 Action 类型
        description:       模板描述
        risk_level:        默认风险等级
        requires_approval: 是否需要审批
        task_definitions:  任务定义列表 (有序)
        min_confidence:    最低置信度阈值
        max_budget_change: 最大预算变化比例 (0 = 无限制)
        metadata:          扩展元数据
    """
    name: str = ""
    workflow_type: WorkflowType = WorkflowType.CUSTOM
    action_type: str = ""
    description: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False
    task_definitions: list[dict[str, Any]] = field(default_factory=list)
    min_confidence: float = 0.5
    max_budget_change: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def expand(self, context: dict[str, Any] | None = None) -> list[PlanningTask]:
        """将模板展开为 PlanningTask 列表.

        Args:
            context: 执行上下文 (用于填充参数)

        Returns:
            list[PlanningTask]: 有序任务列表
        """
        ctx = context or {}
        tasks: list[PlanningTask] = []
        for i, task_def in enumerate(self.task_definitions):
            task = PlanningTask(
                name=task_def.get("name", f"task_{i}"),
                action_type=task_def.get("action_type", ""),
                adapter=task_def.get("adapter", ""),
                requires_approval=task_def.get("requires_approval", False),
                parameters={**task_def.get("parameters", {}), **ctx.get("params", {})},
                depends_on=list(task_def.get("depends_on", [])),
                timeout_ms=task_def.get("timeout_ms", 0),
                retry_count=task_def.get("retry_count", 0),
                phase=task_def.get("phase", "execute"),
                order=i,
                metadata=task_def.get("metadata", {}),
            )
            tasks.append(task)
        return tasks

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "workflow_type": self.workflow_type.value,
            "action_type": self.action_type,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "requires_approval": self.requires_approval,
            "task_definitions": self.task_definitions,
            "min_confidence": self.min_confidence,
            "max_budget_change": self.max_budget_change,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Template Registry
# ═══════════════════════════════════════════════════════════════


class TemplateRegistry:
    """E15.2.1 模板注册中心 — 管理所有 Workflow 模板.

    用法:
        registry = TemplateRegistry()
        registry.register(my_template)
        template = registry.get("creative_refresh")
    """

    def __init__(self):
        self._templates: dict[str, WorkflowTemplate] = {}
        self._by_action: dict[str, list[WorkflowTemplate]] = {}
        self._by_type: dict[str, WorkflowTemplate] = {}
        self._register_builtin_templates()

    # ── Registration ──────────────────────────────────────────

    def register(self, template: WorkflowTemplate) -> None:
        """注册模板.

        Args:
            template: WorkflowTemplate 实例
        """
        self._templates[template.name] = template

        if template.action_type not in self._by_action:
            self._by_action[template.action_type] = []
        self._by_action[template.action_type].append(template)

        self._by_type[template.workflow_type.value] = template

    def unregister(self, name: str) -> bool:
        """注销模板."""
        template = self._templates.pop(name, None)
        if template is None:
            return False
        if template.action_type in self._by_action:
            self._by_action[template.action_type] = [
                t for t in self._by_action[template.action_type] if t.name != name
            ]
        if template.workflow_type.value in self._by_type:
            del self._by_type[template.workflow_type.value]
        return True

    # ── Query ─────────────────────────────────────────────────

    def get(self, name: str) -> WorkflowTemplate | None:
        """按名称获取模板."""
        return self._templates.get(name)

    def get_by_action(self, action_type: str) -> list[WorkflowTemplate]:
        """按 Action 类型获取匹配模板."""
        return self._by_action.get(action_type, [])

    def get_by_workflow_type(self, workflow_type: WorkflowType) -> WorkflowTemplate | None:
        """按 WorkflowType 获取模板."""
        return self._by_type.get(workflow_type.value)

    def get_best_match(self, action_type: str) -> WorkflowTemplate | None:
        """获取最佳匹配模板 (第一个注册的)."""
        templates = self.get_by_action(action_type)
        return templates[0] if templates else None

    def list_all(self) -> list[WorkflowTemplate]:
        """列出所有模板."""
        return list(self._templates.values())

    def list_action_types(self) -> list[str]:
        """列出所有已注册的 Action 类型."""
        return list(self._by_action.keys())

    @property
    def count(self) -> int:
        return len(self._templates)

    # ── Built-in Templates ────────────────────────────────────

    def _register_builtin_templates(self) -> None:
        """注册内置模板."""
        self.register(_make_creative_refresh_template())
        self.register(_make_budget_optimize_template())
        self.register(_make_campaign_pause_template())
        self.register(_make_campaign_scale_template())
        self.register(_make_audience_expand_template())
        self.register(_make_revenue_optimize_template())


# ═══════════════════════════════════════════════════════════════
# Built-in Template Definitions
# ═══════════════════════════════════════════════════════════════


def _make_creative_refresh_template() -> WorkflowTemplate:
    """Creative Refresh 模板 — 素材刷新标准流程."""
    return WorkflowTemplate(
        name="creative_refresh",
        workflow_type=WorkflowType.CREATIVE_REFRESH,
        action_type="replace_creative",
        description="Generate new creative, validate, upload, launch test, monitor",
        risk_level=RiskLevel.LOW,
        requires_approval=False,
        task_definitions=[
            {
                "name": "Generate Creative",
                "action_type": "generate_creative",
                "adapter": "creative",
                "phase": "prepare",
                "timeout_ms": 60000,
                "retry_count": 2,
            },
            {
                "name": "Validate Asset",
                "action_type": "validate_creative",
                "adapter": "creative",
                "phase": "prepare",
                "depends_on": ["task_1"],
                "timeout_ms": 10000,
            },
            {
                "name": "Upload Creative",
                "action_type": "upload_creative",
                "adapter": "meta_ads",
                "phase": "execute",
                "depends_on": ["task_2"],
                "timeout_ms": 30000,
            },
            {
                "name": "Launch A/B Test",
                "action_type": "launch_ab_test",
                "adapter": "meta_ads",
                "phase": "execute",
                "depends_on": ["task_3"],
                "requires_approval": True,
                "timeout_ms": 30000,
            },
            {
                "name": "Monitor Result",
                "action_type": "monitor",
                "adapter": "adjust",
                "phase": "monitor",
                "depends_on": ["task_4"],
                "timeout_ms": 0,
            },
        ],
    )


def _make_budget_optimize_template() -> WorkflowTemplate:
    """Budget Optimize 模板 — 预算优化标准流程."""
    return WorkflowTemplate(
        name="budget_optimize",
        workflow_type=WorkflowType.BUDGET_OPTIMIZE,
        action_type="increase_budget",
        description="Analyze campaign, adjust budget, monitor ROAS, rollback if needed",
        risk_level=RiskLevel.MEDIUM,
        requires_approval=True,
        max_budget_change=0.3,
        task_definitions=[
            {
                "name": "Analyze Campaign",
                "action_type": "analyze_campaign",
                "adapter": "meta_ads",
                "phase": "prepare",
                "timeout_ms": 15000,
            },
            {
                "name": "Validate Budget Change",
                "action_type": "validate_budget",
                "adapter": "meta_ads",
                "phase": "prepare",
                "depends_on": ["task_1"],
                "timeout_ms": 5000,
            },
            {
                "name": "Update Campaign Budget",
                "action_type": "update_budget",
                "adapter": "meta_ads",
                "phase": "execute",
                "depends_on": ["task_2"],
                "requires_approval": True,
                "timeout_ms": 15000,
            },
            {
                "name": "Monitor ROAS",
                "action_type": "monitor",
                "adapter": "adjust",
                "phase": "monitor",
                "depends_on": ["task_3"],
                "timeout_ms": 0,
            },
            {
                "name": "Rollback if Failed",
                "action_type": "rollback",
                "adapter": "meta_ads",
                "phase": "rollback",
                "depends_on": ["task_3"],
                "timeout_ms": 15000,
            },
        ],
    )


def _make_campaign_pause_template() -> WorkflowTemplate:
    """Campaign Pause 模板 — 暂停止损流程."""
    return WorkflowTemplate(
        name="campaign_pause",
        workflow_type=WorkflowType.CAMPAIGN_PAUSE,
        action_type="pause_campaign",
        description="Verify anomaly, pause campaign, record reason, monitor recovery",
        risk_level=RiskLevel.CRITICAL,
        requires_approval=False,
        task_definitions=[
            {
                "name": "Verify Anomaly",
                "action_type": "verify_anomaly",
                "adapter": "meta_ads",
                "phase": "prepare",
                "timeout_ms": 10000,
            },
            {
                "name": "Pause Campaign",
                "action_type": "pause_campaign",
                "adapter": "meta_ads",
                "phase": "execute",
                "depends_on": ["task_1"],
                "timeout_ms": 10000,
            },
            {
                "name": "Record Reason",
                "action_type": "record_audit",
                "adapter": "internal",
                "phase": "execute",
                "depends_on": ["task_2"],
                "timeout_ms": 5000,
            },
            {
                "name": "Monitor Recovery",
                "action_type": "monitor",
                "adapter": "adjust",
                "phase": "monitor",
                "depends_on": ["task_2"],
                "timeout_ms": 0,
            },
        ],
    )


def _make_campaign_scale_template() -> WorkflowTemplate:
    """Campaign Scale 模板 — 放量扩量流程."""
    return WorkflowTemplate(
        name="campaign_scale",
        workflow_type=WorkflowType.CAMPAIGN_SCALE,
        action_type="scale",
        description="Analyze scale potential, increase budget, monitor, adjust if needed",
        risk_level=RiskLevel.HIGH,
        requires_approval=True,
        max_budget_change=0.5,
        task_definitions=[
            {
                "name": "Analyze Scale Potential",
                "action_type": "analyze_campaign",
                "adapter": "meta_ads",
                "phase": "prepare",
                "timeout_ms": 15000,
            },
            {
                "name": "Scale Budget",
                "action_type": "scale_budget",
                "adapter": "meta_ads",
                "phase": "execute",
                "depends_on": ["task_1"],
                "requires_approval": True,
                "timeout_ms": 15000,
            },
            {
                "name": "Monitor Performance",
                "action_type": "monitor",
                "adapter": "adjust",
                "phase": "monitor",
                "depends_on": ["task_2"],
                "timeout_ms": 0,
            },
            {
                "name": "Adjust if Needed",
                "action_type": "adjust_budget",
                "adapter": "meta_ads",
                "phase": "monitor",
                "depends_on": ["task_3"],
                "timeout_ms": 15000,
            },
        ],
    )


def _make_audience_expand_template() -> WorkflowTemplate:
    """Audience Expand 模板 — 受众扩展流程."""
    return WorkflowTemplate(
        name="audience_expand",
        workflow_type=WorkflowType.AUDIENCE_EXPAND,
        action_type="expand_targeting",
        description="Analyze audience, create new ad set, launch test, monitor",
        risk_level=RiskLevel.MEDIUM,
        requires_approval=False,
        task_definitions=[
            {
                "name": "Analyze Audience",
                "action_type": "analyze_audience",
                "adapter": "meta_ads",
                "phase": "prepare",
                "timeout_ms": 15000,
            },
            {
                "name": "Create Ad Set",
                "action_type": "create_ad_set",
                "adapter": "meta_ads",
                "phase": "execute",
                "depends_on": ["task_1"],
                "timeout_ms": 15000,
            },
            {
                "name": "Launch Test",
                "action_type": "launch_ab_test",
                "adapter": "meta_ads",
                "phase": "execute",
                "depends_on": ["task_2"],
                "timeout_ms": 15000,
            },
            {
                "name": "Monitor",
                "action_type": "monitor",
                "adapter": "adjust",
                "phase": "monitor",
                "depends_on": ["task_3"],
                "timeout_ms": 0,
            },
        ],
    )


def _make_revenue_optimize_template() -> WorkflowTemplate:
    """Revenue Optimize 模板 — 收入优化流程."""
    return WorkflowTemplate(
        name="revenue_optimize",
        workflow_type=WorkflowType.REVENUE_OPTIMIZE,
        action_type="optimize_pricing",
        description="Analyze pricing, adjust strategy, monitor revenue impact",
        risk_level=RiskLevel.MEDIUM,
        requires_approval=True,
        task_definitions=[
            {
                "name": "Analyze Pricing",
                "action_type": "analyze_pricing",
                "adapter": "internal",
                "phase": "prepare",
                "timeout_ms": 15000,
            },
            {
                "name": "Optimize Pricing",
                "action_type": "optimize_pricing",
                "adapter": "internal",
                "phase": "execute",
                "depends_on": ["task_1"],
                "requires_approval": True,
                "timeout_ms": 15000,
            },
            {
                "name": "Monitor Revenue",
                "action_type": "monitor",
                "adapter": "adjust",
                "phase": "monitor",
                "depends_on": ["task_2"],
                "timeout_ms": 0,
            },
        ],
    )


__all__ = [
    "WorkflowTemplate",
    "TemplateRegistry",
]