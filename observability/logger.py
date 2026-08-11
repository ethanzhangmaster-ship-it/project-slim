"""
EP0.6 — Observability: unified logging for all agents.

No print() allowed. All agent decision traces go through this logger.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Singleton logger
_logger: Optional["AgentLogger"] = None


class AgentLogger:
    """Unified structured logger for all AI agents.

    Usage::

        logger = AgentLogger(log_dir="logs")
        logger.info("decision_created", agent="aso", game_id="witch_merge", action="update_screenshot")
        logger.finish_span("pipeline_run", duration_ms=1240)
    """

    def __init__(
        self,
        log_dir: str = "logs",
        level: str = "INFO",
        json_lines: bool = True,
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.json_lines = json_lines

        # Python stdlib logger for file output
        name = f"launchforge.agent.{uuid.uuid4().hex[:8]}"
        self._py_logger = logging.getLogger(name)
        self._py_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self._py_logger.propagate = False

        self._handlers: list[logging.Handler] = []
        self._file_handler = None

        if not self._py_logger.handlers:
            # JSONL file handler
            fh = logging.FileHandler(
                self.log_dir / "agent_trace.jsonl", encoding="utf-8"
            )
            fh.setLevel(logging.DEBUG)
            self._py_logger.addHandler(fh)
            self._handlers.append(fh)
            self._file_handler = fh

            # Console handler (human-readable)
            ch = logging.StreamHandler(sys.stdout)
            ch.setLevel(logging.INFO)
            ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            self._py_logger.addHandler(ch)
            self._handlers.append(ch)

    # ------------------------------------------------------------------
    # Structured events
    # ------------------------------------------------------------------

    def info(self, event: str, **kwargs: Any) -> None:
        self._log("INFO", event, **kwargs)

    def warn(self, event: str, **kwargs: Any) -> None:
        self._log("WARNING", event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._log("ERROR", event, **kwargs)

    def span(self, span_name: str, **kwargs: Any) -> float:
        """Start a timed span. Returns start timestamp."""
        self._log("INFO", f"span_start:{span_name}", **kwargs)
        return time.perf_counter()

    def finish_span(self, span_name: str, start: float, **kwargs: Any) -> float:
        """Finish span, log duration."""
        duration_ms = (time.perf_counter() - start) * 1000
        self._log("INFO", f"span_end:{span_name}", duration_ms=duration_ms, **kwargs)
        return duration_ms

    def agent_decision(self, agent: str, action: str, game_id: str, **kwargs: Any) -> None:
        self._log("INFO", "agent_decision", agent=agent, action=action, game_id=game_id, **kwargs)

    def agent_execution(self, agent: str, action: str, result: str, **kwargs: Any) -> None:
        self._log("INFO", "agent_execution", agent=agent, action=action, result=result, **kwargs)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release file handles — call before cleanup."""
        for handler in self._handlers:
            handler.flush()
            handler.close()
            self._py_logger.removeHandler(handler)
        self._handlers.clear()
        self._file_handler = None

    def _log(self, level: str, event: str, **kwargs: Any) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        if self.json_lines:
            record = {"ts": ts, "level": level, "event": event, **kwargs}
            self._py_logger.log(
                getattr(logging, level.upper(), logging.INFO),
                json.dumps(record, default=str, ensure_ascii=False),
            )
        else:
            extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
            self._py_logger.log(
                getattr(logging, level.upper(), logging.INFO),
                f"[{event}] {extra}",
            )


def get_logger(log_dir: str = "logs") -> AgentLogger:
    """Get or create the singleton agent logger."""
    global _logger
    if _logger is None:
        _logger = AgentLogger(log_dir=log_dir)
    return _logger
