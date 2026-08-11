"""E15.0.11 Logger 测试 — 结构化日志器测试.

测试覆盖:
  - 各级别日志 (DEBUG/INFO/WARNING/ERROR)
  - JSON 格式输出
  - 最低日志级别过滤
  - Action 便捷方法
  - 默认上下文
  - 统计计数
"""

from __future__ import annotations

import io
import json

import pytest

from market_ops.creative_vision_runtime.growth_runtime.observability.logger import (
    ExecutionLogger,
)


class TestExecutionLogger:
    """ExecutionLogger 单元测试."""

    def setup_method(self):
        self.output = io.StringIO()
        self.logger = ExecutionLogger(output=self.output, min_level="DEBUG")

    def _get_lines(self) -> list[dict]:
        return [json.loads(line) for line in self.output.getvalue().strip().split("\n") if line]

    # ── Level Tests ──────────────────────────────────────────

    def test_debug(self):
        self.logger.debug("test_event", key="value")
        lines = self._get_lines()
        assert len(lines) == 1
        assert lines[0]["level"] == "DEBUG"
        assert lines[0]["event"] == "test_event"
        assert lines[0]["key"] == "value"

    def test_info(self):
        self.logger.info("ACTION_EXECUTED", action_id="act_001", adapter="meta")
        lines = self._get_lines()
        assert len(lines) == 1
        assert lines[0]["level"] == "INFO"
        assert lines[0]["event"] == "ACTION_EXECUTED"
        assert lines[0]["action_id"] == "act_001"
        assert lines[0]["adapter"] == "meta"

    def test_warning(self):
        self.logger.warning("SLOW_EXECUTION", duration_ms=5000)
        lines = self._get_lines()
        assert lines[0]["level"] == "WARNING"
        assert lines[0]["duration_ms"] == 5000

    def test_error(self):
        self.logger.error("ADAPTER_FAILED", error="Connection timeout")
        lines = self._get_lines()
        assert lines[0]["level"] == "ERROR"
        assert lines[0]["error"] == "Connection timeout"

    # ── Level Filtering ──────────────────────────────────────

    def test_min_level_info_filters_debug(self):
        logger = ExecutionLogger(output=self.output, min_level="INFO")
        logger.debug("should_not_appear")
        logger.info("should_appear")
        lines = self._get_lines()
        assert len(lines) == 1
        assert lines[0]["event"] == "should_appear"

    def test_min_level_warning_filters_info(self):
        logger = ExecutionLogger(output=self.output, min_level="WARNING")
        logger.info("should_not_appear")
        logger.warning("should_appear")
        lines = self._get_lines()
        assert len(lines) == 1
        assert lines[0]["event"] == "should_appear"

    def test_min_level_error_filters_warning(self):
        logger = ExecutionLogger(output=self.output, min_level="ERROR")
        logger.warning("should_not_appear")
        logger.error("should_appear")
        lines = self._get_lines()
        assert len(lines) == 1
        assert lines[0]["event"] == "should_appear"

    # ── JSON Structure ───────────────────────────────────────

    def test_has_timestamp(self):
        self.logger.info("test")
        lines = self._get_lines()
        assert "timestamp" in lines[0]
        assert lines[0]["timestamp"] != ""

    def test_json_format_valid(self):
        self.logger.info("test", key="value", num=42)
        result = self.output.getvalue().strip()
        parsed = json.loads(result)
        assert parsed["level"] == "INFO"
        assert parsed["key"] == "value"
        assert parsed["num"] == 42

    def test_unicode_content(self):
        self.logger.info("测试事件", 描述="执行成功")
        lines = self._get_lines()
        assert lines[0]["event"] == "测试事件"
        assert lines[0]["描述"] == "执行成功"

    # ── Action-specific Methods ──────────────────────────────

    def test_log_action_created(self):
        self.logger.log_action_created("act_001", "update_budget")
        lines = self._get_lines()
        assert lines[0]["event"] == "ACTION_CREATED"
        assert lines[0]["action_id"] == "act_001"
        assert lines[0]["action_type"] == "update_budget"

    def test_log_execution_success(self):
        self.logger.log_execution_success("act_001", "meta", 320.0)
        lines = self._get_lines()
        assert lines[0]["event"] == "EXECUTION_SUCCESS"
        assert lines[0]["action_id"] == "act_001"
        assert lines[0]["adapter"] == "meta"
        assert lines[0]["duration_ms"] == 320.0

    def test_log_execution_failed(self):
        self.logger.log_execution_failed("act_002", "max", "API timeout")
        lines = self._get_lines()
        assert lines[0]["event"] == "EXECUTION_FAILED"
        assert lines[0]["error"] == "API timeout"

    def test_log_approval_required(self):
        self.logger.log_approval_required("act_003", "high")
        lines = self._get_lines()
        assert lines[0]["event"] == "APPROVAL_REQUIRED"
        assert lines[0]["risk_level"] == "high"

    def test_log_approval_decision(self):
        self.logger.log_approval_decision("act_004", "approved", "admin")
        lines = self._get_lines()
        assert lines[0]["event"] == "APPROVAL_DECISION"
        assert lines[0]["decision"] == "approved"
        assert lines[0]["reviewer"] == "admin"

    # ── Default Context ──────────────────────────────────────

    def test_default_context(self):
        logger = ExecutionLogger(
            output=self.output,
            default_context={"service": "execution_runtime", "version": "15.0.11"},
        )
        logger.info("test")
        lines = [json.loads(l) for l in self.output.getvalue().strip().split("\n")]
        assert lines[0]["service"] == "execution_runtime"
        assert lines[0]["version"] == "15.0.11"

    def test_default_context_does_not_override(self):
        logger = ExecutionLogger(
            output=self.output,
            default_context={"service": "default"},
        )
        logger.info("test", service="override")
        lines = [json.loads(l) for l in self.output.getvalue().strip().split("\n")]
        assert lines[0]["service"] == "override"

    # ── Stats ────────────────────────────────────────────────

    def test_stats(self):
        self.logger.info("event1")
        self.logger.info("event2")
        self.logger.error("event3")
        self.logger.warning("event4")

        stats = self.logger.stats()
        assert stats["log_count"] == 4
        assert stats["error_count"] == 1
        assert stats["warning_count"] == 1

    def test_stats_initial(self):
        stats = self.logger.stats()
        assert stats["log_count"] == 0
        assert stats["error_count"] == 0
        assert stats["warning_count"] == 0

    def test_stats_respects_min_level(self):
        logger = ExecutionLogger(output=self.output, min_level="WARNING")
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")

        stats = logger.stats()
        assert stats["log_count"] == 2
        assert stats["error_count"] == 1
        assert stats["warning_count"] == 1

    # ── Multiple Entries ─────────────────────────────────────

    def test_multiple_entries(self):
        for i in range(5):
            self.logger.info(f"event_{i}", index=i)
        lines = self._get_lines()
        assert len(lines) == 5
        for i, line in enumerate(lines):
            assert line["event"] == f"event_{i}"
            assert line["index"] == i

    def test_flush_after_write(self):
        """每次写入后应 flush 到输出流."""
        self.logger.info("test")
        assert self.output.getvalue() != ""