"""P2.4 Safe Executor — 执行安全沙箱 + 幂等 + 回滚机制。

从「能执行」到「敢执行」：
    P2.1 Contract -> P2.2 Provider -> P2.3 Approval -> P2.4 SafeExecutor -> Result

Execution Policy：
    Rule 1 授权过期/缺失/不匹配 -> BLOCK
    Rule 2 幂等冲突（RUNNING/ROLLED_BACK）-> BLOCK
    Rule 3 Snapshot 失败 -> BLOCK
    Rule 4 Provider 失败 -> 尝试回滚
    Rule 5 回滚失败 -> ESCALATE（人工介入）
"""

from src.execution.safe_executor.audit import (
    EVENT_EXECUTION_FINISHED,
    EVENT_EXECUTION_STARTED,
    EVENT_PROVIDER_CALLED,
    EVENT_ROLLBACK_FINISHED,
    ExecutionAuditLogger,
)
from src.execution.safe_executor.executor import SafeExecutor, build_safe_executor
from src.execution.safe_executor.idempotency import (
    ExecutionIdempotencyStore,
    IdempotencyRecord,
    InMemoryIdempotencyStore,
    JsonlIdempotencyStore,
    check_idempotency,
    make_idempotency_key,
)
from src.execution.safe_executor.models import (
    RollbackCapability,
    RollbackPlan,
    SafeExecutionContext,
    SafeExecutionOutcome,
)
from src.execution.safe_executor.rollback import (
    DEFAULT_CAPABILITIES,
    RollbackEngine,
    RollbackRegistry,
    RollbackResult,
)
from src.execution.safe_executor.sandbox import ExecutionSandbox, GateCheck
from src.execution.safe_executor.snapshot import (
    InMemorySnapshotStore,
    JsonlSnapshotStore,
    SnapshotError,
    Snapshotter,
    SnapshotStore,
)

__all__ = [
    # models
    "SafeExecutionContext",
    "SafeExecutionOutcome",
    "RollbackCapability",
    "RollbackPlan",
    # idempotency
    "ExecutionIdempotencyStore",
    "IdempotencyRecord",
    "InMemoryIdempotencyStore",
    "JsonlIdempotencyStore",
    "make_idempotency_key",
    "check_idempotency",
    # snapshot
    "SnapshotStore",
    "InMemorySnapshotStore",
    "JsonlSnapshotStore",
    "Snapshotter",
    "SnapshotError",
    # rollback
    "RollbackRegistry",
    "RollbackEngine",
    "RollbackResult",
    "DEFAULT_CAPABILITIES",
    # sandbox
    "ExecutionSandbox",
    "GateCheck",
    # audit
    "ExecutionAuditLogger",
    "EVENT_EXECUTION_STARTED",
    "EVENT_PROVIDER_CALLED",
    "EVENT_EXECUTION_FINISHED",
    "EVENT_ROLLBACK_FINISHED",
    # executor
    "SafeExecutor",
    "build_safe_executor",
]
