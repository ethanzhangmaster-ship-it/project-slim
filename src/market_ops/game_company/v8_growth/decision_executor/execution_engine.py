from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class ExecutionResult(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    TIMEOUT = "timeout"


@dataclass
class ExecutionContext:
    context_id: str
    action_id: str
    action_type: str
    target: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context_id": self.context_id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "target": self.target,
            "parameters": self.parameters,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class ExecutionLog:
    log_id: str
    action_id: str
    status: ExecutionStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "log_id": self.log_id,
            "action_id": self.action_id,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ExecutionRecord:
    record_id: str
    action_id: str
    status: ExecutionStatus
    result: ExecutionResult = ExecutionResult.SUCCESS
    output: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    logs: List[ExecutionLog] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "action_id": self.action_id,
            "status": self.status.value,
            "result": self.result.value,
            "output": self.output,
            "duration_seconds": self.duration_seconds,
            "logs": [l.to_dict() for l in self.logs],
            "created_at": self.created_at.isoformat(),
        }


class ExecutionEngine:
    def __init__(self):
        self._contexts: Dict[str, ExecutionContext] = {}
        self._records: Dict[str, ExecutionRecord] = []
        self._logs: List[ExecutionLog] = []
        self._active_executions: Dict[str, str] = {}

    def execute(self, action_id: str, action_type: str, target: str, parameters: Dict[str, Any] = None) -> ExecutionRecord:
        context_id = f"ctx_{action_id}"
        context = ExecutionContext(
            context_id=context_id,
            action_id=action_id,
            action_type=action_type,
            target=target,
            parameters=parameters or {},
        )
        self._contexts[context_id] = context

        self._log(action_id, ExecutionStatus.RUNNING, f"Starting execution of {action_type} on {target}")

        record_id = f"rec_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        record = ExecutionRecord(
            record_id=record_id,
            action_id=action_id,
            status=ExecutionStatus.RUNNING,
        )
        self._records.append(record)
        self._active_executions[action_id] = record_id

        try:
            context.started_at = datetime.now()
            output = self._execute_action(action_type, target, parameters or {})
            context.completed_at = datetime.now()
            duration = (context.completed_at - context.started_at).total_seconds()

            record.status = ExecutionStatus.COMPLETED
            record.result = ExecutionResult.SUCCESS
            record.output = output
            record.duration_seconds = duration

            self._log(action_id, ExecutionStatus.COMPLETED, f"Successfully executed {action_type}")

        except Exception as e:
            record.status = ExecutionStatus.FAILED
            record.result = ExecutionResult.FAILURE
            record.output = {"error": str(e)}
            self._log(action_id, ExecutionStatus.FAILED, f"Execution failed: {str(e)}")

            if context.retry_count < context.max_retries:
                context.retry_count += 1
                return self.execute(action_id, action_type, target, parameters)

        finally:
            if action_id in self._active_executions:
                del self._active_executions[action_id]

        return record

    def _execute_action(self, action_type: str, target: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        outputs = {
            "scale_up": {"budget_change": parameters.get("percent", 30), "new_budget": random.uniform(1000, 10000)},
            "scale_down": {"budget_change": parameters.get("percent", -30), "new_budget": random.uniform(500, 5000)},
            "pause": {"status": "paused", "paused_at": datetime.now().isoformat()},
            "resume": {"status": "active", "resumed_at": datetime.now().isoformat()},
            "optimize": {"optimization": "applied", "improvement": random.uniform(0.05, 0.2)},
            "test": {"test_started": True, "test_id": f"test_{random.randint(1000, 9999)}"},
            "deploy": {"deployed": True, "version": parameters.get("version", "v1.0.0")},
            "update": {"updated": True, "changes": parameters.keys() if parameters else []},
        }
        return outputs.get(action_type, {"executed": True})

    def _log(self, action_id: str, status: ExecutionStatus, message: str, details: Dict[str, Any] = None):
        log = ExecutionLog(
            log_id=f"log_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            action_id=action_id,
            status=status,
            message=message,
            details=details or {},
        )
        self._logs.append(log)

    def cancel(self, action_id: str) -> Optional[ExecutionRecord]:
        record_id = self._active_executions.get(action_id)
        if not record_id:
            return None

        for record in self._records:
            if record.record_id == record_id:
                record.status = ExecutionStatus.CANCELLED
                self._log(action_id, ExecutionStatus.CANCELLED, "Execution cancelled by user")
                if action_id in self._active_executions:
                    del self._active_executions[action_id]
                return record
        return None

    def get_context(self, action_id: str) -> Optional[ExecutionContext]:
        context_id = f"ctx_{action_id}"
        return self._contexts.get(context_id)

    def get_record(self, record_id: str) -> Optional[ExecutionRecord]:
        for record in self._records:
            if record.record_id == record_id:
                return record
        return None

    def get_records(self, action_id: str = None) -> List[ExecutionRecord]:
        if action_id:
            return [r for r in self._records if r.action_id == action_id]
        return list(self._records)

    def get_logs(self, action_id: str = None) -> List[ExecutionLog]:
        if action_id:
            return [l for l in self._logs if l.action_id == action_id]
        return list(self._logs)

    def get_active_executions(self) -> Dict[str, str]:
        return dict(self._active_executions)

    def get_stats(self) -> Dict[str, Any]:
        records = list(self._records)
        return {
            "total_executions": len(records),
            "executions_by_status": {
                status.value: sum(1 for r in records if r.status == status)
                for status in ExecutionStatus
            },
            "executions_by_result": {
                result.value: sum(1 for r in records if r.result == result)
                for result in ExecutionResult
            },
            "active_executions": len(self._active_executions),
            "total_logs": len(self._logs),
        }