"""
E14.2 — Production Runtime Layer
================================

Upgrades the script-based GameFactory OS into a long-running, fault-tolerant
service. Modules:

  * alerting.py      — AlertProvider interface + MockAlertProvider
  * event_logger.py  — structured JSONL runtime event log
  * checkpoint.py    — per-game stage checkpoints + store snapshots
  * health.py        — per-game health monitor (stall / failure-rate / delay)
  * recovery.py      — automated recovery policies (restart / disable / restore)
  * supervisor.py    — fleet process-manager (start/stop/restart/status + ticks)

Pure-Python, stdlib only. No LLM, no external API. Designed to plug a real
delivery backend (Datadog / CloudWatch / Slack) in later via AlertProvider.
"""
from monetization.runtime.alerting import (
    ALERT_CRITICAL, ALERT_INFO, ALERT_WARNING, Alert, AlertProvider,
    MockAlertProvider,
)
from monetization.runtime.checkpoint import (
    STAGE_AFTER_DECISION, STAGE_AFTER_EXECUTION, STAGE_BEFORE_DECISION,
    STAGE_DURING_EXECUTION, CheckpointManager,
)
from monetization.runtime.event_logger import EVENT_CYCLE_DONE, EVENT_CYCLE_START, RuntimeEvent, EventLogger
from monetization.runtime.health import HealthMonitor, HealthStatus
from monetization.runtime.recovery import DisabledExecutor, RecoveryManager
from monetization.runtime.supervisor import (
    GameRuntime, RuntimeConfig, RuntimeSupervisor, STATUS_CRASHED,
    STATUS_DEGRADED, STATUS_RUNNING, STATUS_STOPPED,
)

__all__ = [
    "Alert", "AlertProvider", "MockAlertProvider",
    "ALERT_INFO", "ALERT_WARNING", "ALERT_CRITICAL",
    "CheckpointManager",
    "STAGE_BEFORE_DECISION", "STAGE_AFTER_DECISION",
    "STAGE_DURING_EXECUTION", "STAGE_AFTER_EXECUTION",
    "RuntimeEvent", "EventLogger", "EVENT_CYCLE_START", "EVENT_CYCLE_DONE",
    "HealthMonitor", "HealthStatus",
    "RecoveryManager", "DisabledExecutor",
    "RuntimeSupervisor", "RuntimeConfig", "GameRuntime",
    "STATUS_RUNNING", "STATUS_STOPPED", "STATUS_CRASHED", "STATUS_DEGRADED",
]
