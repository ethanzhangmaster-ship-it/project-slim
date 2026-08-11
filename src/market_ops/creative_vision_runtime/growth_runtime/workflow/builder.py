"""E15.1.1 Workflow Builder — Builder 模式构建 Workflow.

提供声明式 API 简化 WorkflowDefinition 的构建:

    builder = WorkflowBuilder("campaign_optimizer")
    builder.add_step("analyze", "performance_analysis") \
           .add_step("approve", "human_approval", requires_approval=True) \
           .add_step("execute", "update_campaign_budget") \
           .depends_on("approve", "analyze") \
           .depends_on("execute", "approve")
    workflow = builder.build()

与 WorkflowDefinition 的关系:
  - WorkflowBuilder: 构建器 (流式 API)
  - WorkflowDefinition: 产物 (不可变模板)
"""

from __future__ import annotations

from typing import Any

from .models import WorkflowDefinition, WorkflowTask


# ═══════════════════════════════════════════════════════════════
# Workflow Builder
# ═══════════════════════════════════════════════════════════════


class WorkflowBuilder:
    """E15.1.1 Workflow 构建器 — 声明式流式 API.

    用法:
        builder = WorkflowBuilder("creative_refresh", version="1.0.0")
        builder.add_step("generate", "generate_creative") \
               .add_step("approve", "human_approval", requires_approval=True) \
               .add_step("upload", "upload_creative") \
               .depends_on("approve", "generate") \
               .depends_on("upload", "approve")
        workflow = builder.build()

    Attributes:
        _workflow_id: Workflow ID
        _name:        Workflow 名称
        _version:     版本号
        _description: 描述
        _tasks:       任务列表
        _metadata:    扩展元数据
    """

    def __init__(
        self,
        name: str,
        workflow_id: str = "",
        version: str = "1.0.0",
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ):
        from uuid import uuid4

        self._workflow_id = workflow_id or str(uuid4())
        self._name = name
        self._version = version
        self._description = description
        self._tasks: list[WorkflowTask] = []
        self._metadata = metadata or {}

    # ── Step Management ──────────────────────────────────────

    def add_step(
        self,
        name: str,
        action_type: str,
        task_id: str = "",
        description: str = "",
        requires_approval: bool = False,
        approval_threshold: str = "",
        parameters: dict[str, Any] | None = None,
        timeout_ms: int = 0,
        retry_count: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> "WorkflowBuilder":
        """添加一个执行步骤.

        Args:
            name:              步骤名称
            action_type:       对应的 ActionType
            task_id:           任务 ID (空则自动生成)
            description:       步骤描述
            requires_approval: 是否需要审批
            approval_threshold: 审批阈值说明
            parameters:        任务参数
            timeout_ms:        超时
            retry_count:       重试次数
            metadata:          扩展元数据

        Returns:
            self (支持链式调用)
        """
        from uuid import uuid4

        task = WorkflowTask(
            task_id=task_id or str(uuid4()),
            name=name,
            description=description,
            action_type=action_type,
            requires_approval=requires_approval,
            approval_threshold=approval_threshold,
            parameters=parameters or {},
            timeout_ms=timeout_ms,
            retry_count=retry_count,
            metadata=metadata or {},
        )
        self._tasks.append(task)
        return self

    def remove_step(self, task_id: str) -> "WorkflowBuilder":
        """移除一个步骤."""
        self._tasks = [t for t in self._tasks if t.task_id != task_id]
        return self

    # ── Dependency Management ────────────────────────────────

    def depends_on(self, task_id: str, depends_on_id: str) -> "WorkflowBuilder":
        """添加任务依赖: task_id 依赖 depends_on_id.

        Args:
            task_id:       当前任务 ID (或 name)
            depends_on_id: 依赖的任务 ID (或 name)

        Returns:
            self (支持链式调用)
        """
        task = self._find_task(task_id)
        if task is None:
            raise ValueError(f"Task '{task_id}' not found in builder")

        dep_task = self._find_task(depends_on_id)
        if dep_task is None:
            raise ValueError(f"Dependency task '{depends_on_id}' not found in builder")

        if dep_task.task_id not in task.depends_on:
            task.depends_on.append(dep_task.task_id)
        return self

    def remove_dependency(self, task_id: str, depends_on_id: str) -> "WorkflowBuilder":
        """移除任务依赖."""
        task = self._find_task(task_id)
        if task is None:
            return self
        dep_task = self._find_task(depends_on_id)
        if dep_task is None:
            return self
        if dep_task.task_id in task.depends_on:
            task.depends_on = [d for d in task.depends_on if d != dep_task.task_id]
        return self

    # ── Build ────────────────────────────────────────────────

    def build(self) -> WorkflowDefinition:
        """构建 WorkflowDefinition.

        Returns:
            WorkflowDefinition: 构建好的 Workflow 模板

        Raises:
            ValueError: 验证失败
        """
        wf = WorkflowDefinition(
            workflow_id=self._workflow_id,
            name=self._name,
            version=self._version,
            description=self._description,
            tasks=list(self._tasks),
            metadata=self._metadata,
        )

        errors = wf.validate()
        if errors:
            raise ValueError(f"Workflow validation failed: {'; '.join(errors)}")

        return wf

    def build_unchecked(self) -> WorkflowDefinition:
        """构建 WorkflowDefinition (跳过验证)."""
        return WorkflowDefinition(
            workflow_id=self._workflow_id,
            name=self._name,
            version=self._version,
            description=self._description,
            tasks=list(self._tasks),
            metadata=self._metadata,
        )

    # ── Query ────────────────────────────────────────────────

    def get_task(self, task_id: str) -> WorkflowTask | None:
        """按 ID 获取任务."""
        return self._find_task(task_id)

    def get_task_by_name(self, name: str) -> WorkflowTask | None:
        """按名称获取任务."""
        for t in self._tasks:
            if t.name == name:
                return t
        return None

    def task_count(self) -> int:
        """获取步骤数量."""
        return len(self._tasks)

    # ── Internal ─────────────────────────────────────────────

    def _find_task(self, identifier: str) -> WorkflowTask | None:
        """按 ID 或 name 查找任务."""
        for t in self._tasks:
            if t.task_id == identifier or t.name == identifier:
                return t
        return None

    def __repr__(self) -> str:
        return f"WorkflowBuilder(name={self._name}, tasks={len(self._tasks)})"


# ═══════════════════════════════════════════════════════════════
# Preset Workflows
# ═══════════════════════════════════════════════════════════════


def create_campaign_optimization_workflow() -> WorkflowDefinition:
    """创建预设的 Campaign Optimization Workflow.

    流程:
        Analyze → Generate Recommendation → Human Approval → Update Budget → Observe Result
    """
    builder = WorkflowBuilder(
        name="Campaign Budget Optimization",
        version="1.0.0",
        description="Reduce inefficient campaign spend through analysis and execution",
    )

    builder.add_step(
        name="Analyze Campaign",
        action_type="performance_analysis",
        description="Analyze campaign performance metrics (ROAS, CTR, CPA)",
    ).add_step(
        name="Generate Recommendation",
        action_type="generate_recommendation",
        description="Generate budget optimization recommendation",
    ).add_step(
        name="Human Approval",
        action_type="human_approval",
        description="Require human review for budget changes > 20%",
        requires_approval=True,
        approval_threshold="Budget change > 20%",
    ).add_step(
        name="Update Budget",
        action_type="update_campaign_budget",
        description="Apply approved budget changes to Meta Ads",
        retry_count=3,
    ).add_step(
        name="Observe Result",
        action_type="observe_result",
        description="Wait and observe D7 revenue impact",
        timeout_ms=600000,  # 10 minutes
    )

    builder.depends_on("Generate Recommendation", "Analyze Campaign")
    builder.depends_on("Human Approval", "Generate Recommendation")
    builder.depends_on("Update Budget", "Human Approval")
    builder.depends_on("Observe Result", "Update Budget")

    return builder.build()


def create_creative_refresh_workflow() -> WorkflowDefinition:
    """创建预设的 Creative Refresh Workflow.

    流程:
        Detect Fatigue → Generate Creative → Human Approval → Upload Creative → Launch Test
    """
    builder = WorkflowBuilder(
        name="Creative Refresh",
        version="1.0.0",
        description="Detect creative fatigue and refresh with new variants",
    )

    builder.add_step(
        name="Detect Fatigue",
        action_type="detect_fatigue",
        description="Analyze creative performance degradation",
    ).add_step(
        name="Generate Creative",
        action_type="generate_creative",
        description="Generate new creative variants",
    ).add_step(
        name="Human Approval",
        action_type="human_approval",
        requires_approval=True,
    ).add_step(
        name="Upload Creative",
        action_type="upload_creative",
        description="Upload new creative to Meta Ads",
        retry_count=2,
    ).add_step(
        name="Launch Test",
        action_type="launch_test",
        description="Launch A/B test campaign with new creative",
    )

    builder.depends_on("Generate Creative", "Detect Fatigue")
    builder.depends_on("Human Approval", "Generate Creative")
    builder.depends_on("Upload Creative", "Human Approval")
    builder.depends_on("Launch Test", "Upload Creative")

    return builder.build()


def create_growth_recovery_workflow() -> WorkflowDefinition:
    """创建预设的 Growth Recovery Workflow.

    完整 AI CEO 决策链路:
        Analyze Adjust → Detect Fatigue → Mutate Creative → Approval
        → Upload Meta → Launch Test → Observe D7 → Store Learning
    """
    builder = WorkflowBuilder(
        name="Growth Recovery",
        version="1.0.0",
        description="Full growth recovery workflow triggered by ROAS decline",
    )

    builder.add_step(
        name="Analyze Adjust Data",
        action_type="analyze_adjust",
        description="Pull and analyze Adjust attribution data",
    ).add_step(
        name="Detect Fatigue",
        action_type="detect_fatigue",
        description="Detect creative fatigue from performance signals",
    ).add_step(
        name="Mutate Creative",
        action_type="mutate_creative",
        description="Generate creative mutations based on winning DNA",
    ).add_step(
        name="Human Approval",
        action_type="human_approval",
        requires_approval=True,
        approval_threshold="New creative upload",
    ).add_step(
        name="Upload to Meta",
        action_type="upload_creative",
        description="Upload mutated creative to Meta Ads",
        retry_count=3,
    ).add_step(
        name="Launch Test Campaign",
        action_type="create_campaign",
        description="Launch test campaign with new creative",
    ).add_step(
        name="Observe D7 Revenue",
        action_type="observe_result",
        description="Wait 7 days and observe revenue impact",
        timeout_ms=604800000,  # 7 days
    ).add_step(
        name="Store Learning",
        action_type="store_learning",
        description="Store results in Experience Memory for future decisions",
    )

    builder.depends_on("Detect Fatigue", "Analyze Adjust Data")
    builder.depends_on("Mutate Creative", "Detect Fatigue")
    builder.depends_on("Human Approval", "Mutate Creative")
    builder.depends_on("Upload to Meta", "Human Approval")
    builder.depends_on("Launch Test Campaign", "Upload to Meta")
    builder.depends_on("Observe D7 Revenue", "Launch Test Campaign")
    builder.depends_on("Store Learning", "Observe D7 Revenue")

    return builder.build()


__all__ = [
    "WorkflowBuilder",
    "create_campaign_optimization_workflow",
    "create_creative_refresh_workflow",
    "create_growth_recovery_workflow",
]