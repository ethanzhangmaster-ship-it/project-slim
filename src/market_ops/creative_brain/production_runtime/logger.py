"""V4.4 Logger — structured logging for production runtime.

Supports: levels, structured data, task context, output to console.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Logger:
    """Structured logger for production runtime."""

    def __init__(self, name: str = "runtime", level: LogLevel = LogLevel.INFO) -> None:
        self._name = name
        self._level = level
        self._logs: list[dict[str, Any]] = []
        self._counts: dict[str, int] = {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0}
        self._current_task_id: str = ""

    def set_task_context(self, task_id: str) -> None:
        """Set current task context for log correlation."""
        self._current_task_id = task_id

    def clear_task_context(self) -> None:
        """Clear task context."""
        self._current_task_id = ""

    def debug(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.ERROR, message, **kwargs)

    def _log(self, level: LogLevel, message: str, **kwargs: Any) -> None:
        """Internal log method."""
        self._counts[level.value] = self._counts.get(level.value, 0) + 1

        entry = {
            "timestamp": time.time(),
            "level": level.value,
            "name": self._name,
            "message": message,
            "task_id": self._current_task_id,
            **kwargs,
        }
        self._logs.append(entry)

    def get_logs(self, level: LogLevel | None = None,
                 limit: int = 100) -> list[dict[str, Any]]:
        """Get recent logs, optionally filtered by level."""
        if level:
            return [l for l in self._logs[-limit:] if l["level"] == level.value]
        return self._logs[-limit:]

    def get_errors(self) -> list[dict[str, Any]]:
        """Get all error logs."""
        return self.get_logs(LogLevel.ERROR)

    def get_counts(self) -> dict[str, int]:
        """Get log counts by level."""
        return dict(self._counts)

    def clear(self) -> None:
        """Clear all logs."""
        self._logs = []
        self._counts = {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0}