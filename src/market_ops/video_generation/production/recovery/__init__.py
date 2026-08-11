"""Recovery Module for Generation Task Failure Handling.

Provides automatic recovery capabilities:
- Failure detection and classification
- Automatic recovery with retry/switch/resume
- Checkpoint-based task resumption
"""

from .failure_detector import (
    FailureDetector,
    FailureRecord,
    FailureType,
    FailureSeverity,
    FailurePattern
)

from .auto_recovery import (
    AutoRecovery,
    RecoveryPlan,
    RecoveryResult,
    RecoveryAction,
    RecoveryStatus
)

from .checkpoint import (
    CheckpointManager,
    Checkpoint,
    CheckpointStatus
)

__all__ = [
    # Failure Detection
    "FailureDetector",
    "FailureRecord",
    "FailureType",
    "FailureSeverity",
    "FailurePattern",
    
    # Auto Recovery
    "AutoRecovery",
    "RecoveryPlan",
    "RecoveryResult",
    "RecoveryAction",
    "RecoveryStatus",
    
    # Checkpoint
    "CheckpointManager",
    "Checkpoint",
    "CheckpointStatus"
]