from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class RollbackStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RollbackTrigger(Enum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"
    ERROR = "error"
    TIMEOUT = "timeout"
    PERFORMANCE = "performance"


@dataclass
class RollbackPoint:
    point_id: str
    action_id: str
    action_type: str
    target: str
    state_before: Dict[str, Any] = field(default_factory=dict)
    state_after: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "point_id": self.point_id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "target": self.target,
            "state_before": self.state_before,
            "state_after": self.state_after,
            "parameters": self.parameters,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class RollbackRequest:
    request_id: str
    action_id: str
    trigger: RollbackTrigger = RollbackTrigger.MANUAL
    reason: str = ""
    status: RollbackStatus = RollbackStatus.PENDING
    requested_by: str = "system"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "action_id": self.action_id,
            "trigger": self.trigger.value,
            "reason": self.reason,
            "status": self.status.value,
            "requested_by": self.requested_by,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class RollbackResult:
    result_id: str
    request_id: str
    action_id: str
    success: bool = False
    restored_state: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "request_id": self.request_id,
            "action_id": self.action_id,
            "success": self.success,
            "restored_state": self.restored_state,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
        }


class RollbackManager:
    def __init__(self):
        self._points: Dict[str, RollbackPoint] = {}
        self._requests: Dict[str, RollbackRequest] = {}
        self._results: List[RollbackResult] = []
        self._auto_rollback_enabled: bool = True
        self._thresholds = {
            "performance_drop": 0.3,
            "error_rate": 0.1,
        }

    def create_point(
        self,
        action_id: str,
        action_type: str,
        target: str,
        state_before: Dict[str, Any],
        parameters: Dict[str, Any] = None
    ) -> RollbackPoint:
        point_id = f"rp_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        point = RollbackPoint(
            point_id=point_id,
            action_id=action_id,
            action_type=action_type,
            target=target,
            state_before=state_before,
            parameters=parameters or {},
        )
        self._points[point_id] = point
        return point

    def request_rollback(
        self,
        action_id: str,
        trigger: RollbackTrigger = RollbackTrigger.MANUAL,
        reason: str = "",
        requested_by: str = "system"
    ) -> RollbackRequest:
        request_id = f"rb_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        request = RollbackRequest(
            request_id=request_id,
            action_id=action_id,
            trigger=trigger,
            reason=reason,
            requested_by=requested_by,
        )
        self._requests[request_id] = request
        return request

    def execute_rollback(self, request_id: str) -> RollbackResult:
        request = self._requests.get(request_id)
        if not request:
            return RollbackResult(
                result_id=f"rr_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                request_id=request_id,
                action_id="",
                success=False,
                message="Request not found",
            )

        request.status = RollbackStatus.IN_PROGRESS
        request.started_at = datetime.now()

        point = self._find_point_for_action(request.action_id)
        if not point:
            request.status = RollbackStatus.SKIPPED
            return RollbackResult(
                result_id=f"rr_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                request_id=request_id,
                action_id=request.action_id,
                success=False,
                message="No rollback point found for action",
            )

        try:
            restored_state = self._restore_state(point)
            request.status = RollbackStatus.COMPLETED
            request.completed_at = datetime.now()

            result = RollbackResult(
                result_id=f"rr_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                request_id=request_id,
                action_id=request.action_id,
                success=True,
                restored_state=restored_state,
                message=f"Successfully rolled back {point.action_type} on {point.target}",
            )
            self._results.append(result)
            return result

        except Exception as e:
            request.status = RollbackStatus.FAILED
            request.completed_at = datetime.now()
            result = RollbackResult(
                result_id=f"rr_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                request_id=request_id,
                action_id=request.action_id,
                success=False,
                message=f"Rollback failed: {str(e)}",
            )
            self._results.append(result)
            return result

    def _find_point_for_action(self, action_id: str) -> Optional[RollbackPoint]:
        for point in self._points.values():
            if point.action_id == action_id:
                return point
        return None

    def _restore_state(self, point: RollbackPoint) -> Dict[str, Any]:
        return dict(point.state_before)

    def check_auto_rollback(self, performance_metrics: Dict[str, Any]) -> Optional[RollbackRequest]:
        if not self._auto_rollback_enabled:
            return None

        for point in self._points.values():
            perf_drop = performance_metrics.get("performance_drop", 0)
            error_rate = performance_metrics.get("error_rate", 0)

            if perf_drop > self._thresholds["performance_drop"]:
                return self.request_rollback(
                    action_id=point.action_id,
                    trigger=RollbackTrigger.PERFORMANCE,
                    reason=f"Performance dropped by {perf_drop:.1%}",
                )

            if error_rate > self._thresholds["error_rate"]:
                return self.request_rollback(
                    action_id=point.action_id,
                    trigger=RollbackTrigger.ERROR,
                    reason=f"Error rate exceeded threshold: {error_rate:.1%}",
                )

        return None

    def get_point(self, point_id: str) -> Optional[RollbackPoint]:
        return self._points.get(point_id)

    def get_point_for_action(self, action_id: str) -> Optional[RollbackPoint]:
        return self._find_point_for_action(action_id)

    def get_all_points(self) -> List[RollbackPoint]:
        return list(self._points.values())

    def get_request(self, request_id: str) -> Optional[RollbackRequest]:
        return self._requests.get(request_id)

    def get_all_requests(self) -> List[RollbackRequest]:
        return list(self._requests.values())

    def get_results(self, action_id: str = None) -> List[RollbackResult]:
        if action_id:
            return [r for r in self._results if r.action_id == action_id]
        return list(self._results)

    def set_threshold(self, metric: str, value: float):
        self._thresholds[metric] = value

    def get_thresholds(self) -> Dict[str, float]:
        return dict(self._thresholds)

    def get_stats(self) -> Dict[str, Any]:
        requests = list(self._requests.values())
        return {
            "total_points": len(self._points),
            "total_requests": len(requests),
            "requests_by_status": {
                status.value: sum(1 for r in requests if r.status == status)
                for status in RollbackStatus
            },
            "total_results": len(self._results),
            "auto_rollback_enabled": self._auto_rollback_enabled,
            "thresholds": self._thresholds,
        }