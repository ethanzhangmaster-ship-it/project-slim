from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import time


class ErrorLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RetryStrategy(Enum):
    NONE = "none"
    IMMEDIATE = "immediate"
    BACKOFF = "backoff"
    EXPONENTIAL = "exponential"


@dataclass
class ErrorRecord:
    error_id: str
    platform: str
    level: ErrorLevel
    message: str
    timestamp: datetime
    retry_count: int = 0
    last_retry: Optional[datetime] = None
    resolved: bool = False
    resolution: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_id": self.error_id,
            "platform": self.platform,
            "level": self.level.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "retry_count": self.retry_count,
            "last_retry": self.last_retry.isoformat() if self.last_retry else None,
            "resolved": self.resolved,
            "resolution": self.resolution,
        }


class ErrorHandler:
    def __init__(self):
        self._errors: List[ErrorRecord] = []
        self._error_handlers: Dict[str, List[Callable]] = {}
        self._retry_config: Dict[str, RetryStrategy] = {}

    def record_error(self, platform: str, level: ErrorLevel, message: str) -> ErrorRecord:
        error_id = f"err_{hash(platform + message + str(datetime.now())) % 100000:05d}"
        error = ErrorRecord(
            error_id=error_id,
            platform=platform,
            level=level,
            message=message,
            timestamp=datetime.now(),
        )
        self._errors.append(error)

        handlers = self._error_handlers.get(platform, [])
        for handler in handlers:
            handler(error)

        return error

    def register_handler(self, platform: str, handler: Callable):
        if platform not in self._error_handlers:
            self._error_handlers[platform] = []
        self._error_handlers[platform].append(handler)

    def resolve_error(self, error_id: str, resolution: str) -> bool:
        for error in self._errors:
            if error.error_id == error_id:
                error.resolved = True
                error.resolution = resolution
                return True
        return False

    def get_errors(self, platform: str = None, level: ErrorLevel = None, resolved: bool = None) -> List[ErrorRecord]:
        result = self._errors
        if platform:
            result = [e for e in result if e.platform == platform]
        if level:
            result = [e for e in result if e.level == level]
        if resolved is not None:
            result = [e for e in result if e.resolved == resolved]
        return result

    def get_active_errors(self) -> List[ErrorRecord]:
        return self.get_errors(resolved=False)

    def get_critical_errors(self) -> List[ErrorRecord]:
        return self.get_errors(level=ErrorLevel.CRITICAL, resolved=False)

    def retry_operation(self, platform: str, operation: Callable, max_retries: int = 3) -> Any:
        strategy = self._retry_config.get(platform, RetryStrategy.EXPONENTIAL)
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return operation()
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    self.record_error(platform, ErrorLevel.WARNING, f"Retry attempt {attempt + 1}: {str(e)}")
                    wait_time = self._calculate_wait_time(strategy, attempt)
                    time.sleep(wait_time)

        self.record_error(platform, ErrorLevel.ERROR, f"Failed after {max_retries + 1} attempts: {str(last_error)}")
        raise last_error

    def _calculate_wait_time(self, strategy: RetryStrategy, attempt: int) -> float:
        if strategy == RetryStrategy.NONE:
            return 0
        elif strategy == RetryStrategy.IMMEDIATE:
            return 0
        elif strategy == RetryStrategy.BACKOFF:
            return 1.0 * (attempt + 1)
        elif strategy == RetryStrategy.EXPONENTIAL:
            return min(30.0, 2 ** attempt * 0.5)
        return 1.0

    def set_retry_strategy(self, platform: str, strategy: RetryStrategy):
        self._retry_config[platform] = strategy

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._errors)
        resolved = sum(1 for e in self._errors if e.resolved)
        by_level = {}
        by_platform = {}

        for e in self._errors:
            by_level[e.level.value] = by_level.get(e.level.value, 0) + 1
            by_platform[e.platform] = by_platform.get(e.platform, 0) + 1

        return {
            "total_errors": total,
            "resolved_errors": resolved,
            "active_errors": total - resolved,
            "errors_by_level": by_level,
            "errors_by_platform": by_platform,
        }

    def get_recent_errors(self, minutes: int = 60) -> List[ErrorRecord]:
        cutoff = datetime.now() - datetime.timedelta(minutes=minutes)
        return [e for e in self._errors if e.timestamp >= cutoff]

    def clear_resolved(self):
        self._errors = [e for e in self._errors if not e.resolved]
