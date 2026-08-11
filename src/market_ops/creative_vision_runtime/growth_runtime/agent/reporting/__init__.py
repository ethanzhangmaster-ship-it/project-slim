"""E13.7.4.4 Agent Reporting — 人机接口 (可观察性层).

Agent Reporting 把 Agent 的「思考、决策、执行、学习」透明化给人类操作者:
    Human
      ↓
    AgentReporter (API)
      ↓
    Decision / Execution / Health / Learning Report
      ↓
    ReportStore (Memory / File / DB)

模块:
  - report_models: 核心数据模型 (AgentReport, ReportSection, ReportType, etc.)
  - decision_report: 决策报告生成器 (为什么这么做)
  - execution_report: 执行报告生成器 (执行了什么)
  - health_report: 健康报告生成器 (Agent 是否健康)
  - learning_report: 学习报告生成器 (学到了什么)
  - agent_reporter: 主报告器 (统一入口)
  - report_store: 报告存储 (内存 / 文件)

与外部系统的关系:
  - 输出: JSON / Markdown / Text 格式报告
  - 未来: React Dashboard / Telegram Bot / 企业微信 / Web UI
"""

from .report_models import (
    # Enums
    ReportType,
    ReportFormat,
    ReportStatus,
    # Data
    ReportMetric,
    ReportEvidence,
    ReportSection,
    ReportSummary,
    AgentReport,
    ReportQuery,
)

from .decision_report import (
    DecisionReportBuilder,
    DecisionEntry,
    DecisionEvidence,
    DecisionHypothesis,
    ObservedMetric,
    create_decision_report,
)

from .execution_report import (
    ExecutionReportBuilder,
    ExecutionAction,
    ExecutionTask,
    create_execution_report,
)

from .health_report import (
    HealthReportBuilder,
    create_health_report,
)

from .learning_report import (
    LearningReportBuilder,
    LearningEntry,
    PatternUpdate,
    MemoryFeedback,
    create_learning_report,
)

from .agent_reporter import (
    AgentReporter,
    create_agent_reporter,
)

from .report_store import (
    ReportStore,
    InMemoryReportStore,
    FileReportStore,
    create_report_store,
)

__all__ = [
    # Models
    "ReportType",
    "ReportFormat",
    "ReportStatus",
    "ReportMetric",
    "ReportEvidence",
    "ReportSection",
    "ReportSummary",
    "AgentReport",
    "ReportQuery",
    # Decision
    "DecisionReportBuilder",
    "DecisionEntry",
    "DecisionEvidence",
    "DecisionHypothesis",
    "ObservedMetric",
    "create_decision_report",
    # Execution
    "ExecutionReportBuilder",
    "ExecutionAction",
    "ExecutionTask",
    "create_execution_report",
    # Health
    "HealthReportBuilder",
    "create_health_report",
    # Learning
    "LearningReportBuilder",
    "LearningEntry",
    "PatternUpdate",
    "MemoryFeedback",
    "create_learning_report",
    # Reporter
    "AgentReporter",
    "create_agent_reporter",
    # Store
    "ReportStore",
    "InMemoryReportStore",
    "FileReportStore",
    "create_report_store",
]