"""E15.0.11 Structured Logger — 结构化 JSON 日志.

输出 JSON 格式日志，方便接入:
  - Elasticsearch
  - Loki
  - Cloud Logging

每条日志包含:
  - level:     INFO / WARNING / ERROR / DEBUG
  - event:     事件名称
  - timestamp: 时间戳
  - trace_id:  分布式追踪 ID
  - context:   上下文信息

用法:
    logger = ExecutionLogger()

    logger.info("ACTION_EXECUTED", action_id="act_001", adapter="MetaAds", duration=430)
    logger.error("ADAPTER_FAILED", error="Connection timeout", action_id="act_002")
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any, TextIO


# ═══════════════════════════════════════════════════════════════
# Execution Logger
# ═══════════════════════════════════════════════════════════════


class ExecutionLogger:
    """E15.0.11 结构化日志器.

    Attributes:
        output:   输出流 (默认 stdout)
        min_level: 最低日志级别 (DEBUG=0, INFO=1, WARNING=2, ERROR=3)
        default_context: 每条日志都附加的默认上下文
    """

    LEVELS = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}

    def __init__(
        self,
        output: TextIO | None = None,
        min_level: str = "INFO",
        default_context: dict[str, Any] | None = None,
    ):
        self._output = output or sys.stdout
        self._min_level = self.LEVELS.get(min_level.upper(), 1)
        self._default_context = default_context or {}
        self._log_count: int = 0
        self._error_count: int = 0
        self._warning_count: int = 0

    # ── Log Methods ──────────────────────────────────────────

    def debug(self, event: str, **context: Any) -> None:
        self._log("DEBUG", event, context)

    def info(self, event: str, **context: Any) -> None:
        self._log("INFO", event, context)

    def warning(self, event: str, **context: Any) -> None:
        self._log("WARNING", event, context)

    def error(self, event: str, error: str = "", **context: Any) -> None:
        if error:
            context["error"] = error
        self._log("ERROR", event, context)

    # ── Action-specific Logging ──────────────────────────────

    def log_action_created(self, action_id: str, action_type: str, **extra: Any) -> None:
        self.info("ACTION_CREATED", action_id=action_id, action_type=action_type, **extra)

    def log_execution_started(self, action_id: str, adapter: str, **extra: Any) -> None:
        self.info("EXECUTION_STARTED", action_id=action_id, adapter=adapter, **extra)

    def log_execution_success(self, action_id: str, adapter: str, duration_ms: float, **extra: Any) -> None:
        self.info(
            "EXECUTION_SUCCESS",
            action_id=action_id,
            adapter=adapter,
            duration_ms=duration_ms,
            **extra,
        )

    def log_execution_failed(self, action_id: str, adapter: str, error: str, **extra: Any) -> None:
        self.error(
            "EXECUTION_FAILED",
            action_id=action_id,
            adapter=adapter,
            error=error,
            **extra,
        )

    def log_approval_required(self, action_id: str, risk_level: str, **extra: Any) -> None:
        self.info("APPROVAL_REQUIRED", action_id=action_id, risk_level=risk_level, **extra)

    def log_approval_decision(self, action_id: str, decision: str, reviewer: str, **extra: Any) -> None:
        self.info(
            "APPROVAL_DECISION",
            action_id=action_id,
            decision=decision,
            reviewer=reviewer,
            **extra,
        )

    # ── Internal ─────────────────────────────────────────────

    def _log(self, level: str, event: str, context: dict[str, Any]) -> None:
        if self.LEVELS.get(level, 0) < self._min_level:
            return

        self._log_count += 1
        if level == "ERROR":
            self._error_count += 1
        elif level == "WARNING":
            self._warning_count += 1

        entry = {
            "level": level,
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **self._default_context,
            **context,
        }

        self._output.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        self._output.flush()

    # ── Stats ────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "log_count": self._log_count,
            "error_count": self._error_count,
            "warning_count": self._warning_count,
            "min_level": [k for k, v in self.LEVELS.items() if v == self._min_level][0],
        }

    def __repr__(self) -> str:
        return f"ExecutionLogger(entries={self._log_count}, errors={self._error_count})"


__all__ = ["ExecutionLogger"]