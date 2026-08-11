"""E15.2.1 Task Generator — 将模板展开为具体 Task 列表.

TaskGenerator 负责:
  1. 从模板展开 PlanningTask 列表
  2. 根据上下文填充参数
  3. 解析依赖关系 (模板中的 task_N 引用 → 实际 task_id)
  4. 按 phase 组织任务
"""

from __future__ import annotations

from typing import Any

from .models import PlanningTask, WorkflowType
from .workflow_template import TemplateRegistry, WorkflowTemplate


class TaskGenerator:
    """E15.2.1 Task 生成器 — 模板 → 任务列表.

    用法:
        registry = TemplateRegistry()
        generator = TaskGenerator(registry)
        template = registry.get("creative_refresh")
        tasks = generator.generate(template, context={
            "campaign_id": "123",
            "creative_id": "456",
        })
    """

    def __init__(self, registry: TemplateRegistry | None = None):
        self._registry = registry or TemplateRegistry()

    def generate(
        self,
        template: WorkflowTemplate,
        context: dict[str, Any] | None = None,
    ) -> list[PlanningTask]:
        """从模板生成 PlanningTask 列表.

        Args:
            template: WorkflowTemplate 模板
            context:  执行上下文

        Returns:
            list[PlanningTask]: 有序任务列表
        """
        ctx = context or {}
        raw_tasks = template.expand(ctx)

        # 解析依赖: task_N → 实际 task_id
        task_id_map: dict[str, str] = {}
        task_map: dict[str, PlanningTask] = {}

        # 第一遍: 建立 task_N → task_id 映射
        for i, task in enumerate(raw_tasks):
            task_id_map[f"task_{i + 1}"] = task.task_id
            task_map[task.task_id] = task

        # 第二遍: 解析依赖引用
        for task in raw_tasks:
            resolved_deps: list[str] = []
            for dep_ref in task.depends_on:
                if dep_ref in task_id_map:
                    resolved_deps.append(task_id_map[dep_ref])
                elif dep_ref in task_map:
                    resolved_deps.append(dep_ref)
                else:
                    resolved_deps.append(dep_ref)
            task.depends_on = resolved_deps

        # 按 order 排序
        raw_tasks.sort(key=lambda t: t.order)

        return raw_tasks

    def generate_by_action(
        self,
        action_type: str,
        context: dict[str, Any] | None = None,
    ) -> list[PlanningTask] | None:
        """按 Action 类型生成任务列表.

        Args:
            action_type: Action 类型
            context:     执行上下文

        Returns:
            list[PlanningTask] | None: 任务列表 (无匹配模板返回 None)
        """
        template = self._registry.get_best_match(action_type)
        if template is None:
            return None
        return self.generate(template, context)

    def generate_by_workflow_type(
        self,
        workflow_type: WorkflowType,
        context: dict[str, Any] | None = None,
    ) -> list[PlanningTask] | None:
        """按 WorkflowType 生成任务列表.

        Args:
            workflow_type: WorkflowType 枚举
            context:       执行上下文

        Returns:
            list[PlanningTask] | None: 任务列表 (无匹配模板返回 None)
        """
        template = self._registry.get_by_workflow_type(workflow_type)
        if template is None:
            return None
        return self.generate(template, context)

    def get_supported_actions(self) -> list[str]:
        """获取所有支持的 Action 类型."""
        return self._registry.list_action_types()

    def supports_action(self, action_type: str) -> bool:
        """检查是否支持指定 Action 类型."""
        return len(self._registry.get_by_action(action_type)) > 0


__all__ = ["TaskGenerator"]