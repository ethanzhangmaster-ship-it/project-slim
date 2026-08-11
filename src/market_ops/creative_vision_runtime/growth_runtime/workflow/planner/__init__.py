"""E15.2.1 Execution Planner — 将 Growth Opportunity 转换为结构化 Workflow.

提供:
  - ExecutionPlan:        执行计划数据模型
  - WorkflowTemplate:     Workflow 模板定义
  - TemplateRegistry:     模板注册与查询
  - TaskGenerator:        Task 列表生成器
  - PlanningRule:         安全规则
  - SafetyValidator:      规则验证器
  - ExecutionPlanner:     主规划器 (核心入口)

架构位置:
  Growth Opportunity → Execution Planner → Workflow Definition
  → Task Scheduler → Execution Engine → Memory Feedback Bridge
"""

from .execution_planner import ExecutionPlanner
from .models import ExecutionPlan, PlanningTask, RiskLevel, WorkflowType
from .planning_rules import PlanningRule, SafetyValidator
from .task_generator import TaskGenerator
from .workflow_template import TemplateRegistry, WorkflowTemplate

__all__ = [
    # Models
    "ExecutionPlan",
    "PlanningTask",
    "RiskLevel",
    "WorkflowType",
    # Templates
    "WorkflowTemplate",
    "TemplateRegistry",
    # Generator
    "TaskGenerator",
    # Rules
    "PlanningRule",
    "SafetyValidator",
    # Planner
    "ExecutionPlanner",
]