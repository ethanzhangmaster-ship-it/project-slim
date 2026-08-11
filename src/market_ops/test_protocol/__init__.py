"""E11 Phase 2.5 — Test Protocol & Decision Rules。

测试协议和决策引擎，定义：
  - TestProtocol: 测试标准（预算、周期、通过条件）
  - TestResult:   测试结果（PASSED / FAILED / BORDERLINE）
  - TestDecision: 处置决策（SCALE / KILL / EXTEND / REDUCE / KEEP）
  - TestLifecycle: 测试生命周期状态机
  - TestProtocolEngine: AEO/ROAS 决策 + 处置矩阵
  - BudgetManager: 预算缩放逻辑
"""

from .protocol import (
    TestObjective,
    TestResult,
    TestDecision,
    TestProtocol,
    TestRecord,
    CreativeMaturity,
    DEFAULT_PROTOCOLS,
    build_protocol,
)
from .decision_engine import (
    TestProtocolEngine,
    ObjectiveDecision,
    JudgementResult,
    DispositionDecision,
)
from .test_lifecycle import (
    TestStatus,
    TestLifecycle,
    TestLifecycleManager,
)
from .budget_manager import (
    BudgetAction,
    BudgetActionType,
    BudgetManager,
)

__all__ = [
    # Protocol
    "TestObjective",
    "TestResult",
    "TestDecision",
    "TestProtocol",
    "TestRecord",
    "CreativeMaturity",
    "DEFAULT_PROTOCOLS",
    "build_protocol",
    # Decision Engine
    "TestProtocolEngine",
    "ObjectiveDecision",
    "JudgementResult",
    "DispositionDecision",
    # Lifecycle
    "TestStatus",
    "TestLifecycle",
    "TestLifecycleManager",
    # Budget
    "BudgetAction",
    "BudgetActionType",
    "BudgetManager",
]