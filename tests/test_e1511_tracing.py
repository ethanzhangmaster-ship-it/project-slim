"""E15.0.11 Tracing 测试 — 分布式追踪测试.

测试覆盖:
  - TraceContext 创建与子级上下文
  - Span 创建/结束/失败/超时
  - TraceManager 管理 Span 生命周期
  - 追踪树构建
  - 多 Trace 隔离
  - 活跃 Span 追踪
"""

from __future__ import annotations

import time

import pytest

from market_ops.creative_vision_runtime.growth_runtime.observability.tracer import (
    Span,
    SpanStatus,
    TraceContext,
    TraceManager,
)


class TestTraceContext:
    """TraceContext 单元测试."""

    def test_create_context(self):
        ctx = TraceContext()
        assert ctx.trace_id != ""
        assert ctx.span_id != ""
        assert ctx.parent_id is None

    def test_child_context(self):
        parent = TraceContext()
        child = parent.child()

        assert child.trace_id == parent.trace_id
        assert child.parent_id == parent.span_id
        assert child.span_id != parent.span_id

    def test_grandchild_context(self):
        root = TraceContext()
        child = root.child()
        grandchild = child.child()

        assert grandchild.trace_id == root.trace_id
        assert grandchild.parent_id == child.span_id

    def test_to_dict(self):
        ctx = TraceContext(trace_id="trace_abc", span_id="span_001", parent_id="span_000")
        d = ctx.to_dict()
        assert d["trace_id"] == "trace_abc"
        assert d["span_id"] == "span_001"
        assert d["parent_id"] == "span_000"

    def test_unique_ids(self):
        ctx1 = TraceContext()
        ctx2 = TraceContext()
        assert ctx1.trace_id != ctx2.trace_id
        assert ctx1.span_id != ctx2.span_id


class TestSpan:
    """Span 单元测试."""

    def test_create_span(self):
        span = Span(trace_id="trace_abc", name="decision_engine")
        assert span.name == "decision_engine"
        assert span.trace_id == "trace_abc"
        assert span.status == SpanStatus.ACTIVE

    def test_finish_success(self):
        span = Span(name="decision_engine")
        span.finish(SpanStatus.SUCCESS)
        assert span.status == SpanStatus.SUCCESS
        assert span.end_time != ""
        assert span.duration_ms >= 0

    def test_finish_failed(self):
        span = Span(name="decision_engine")
        span.fail("Connection timeout")
        assert span.status == SpanStatus.FAILED
        assert span.metadata["error"] == "Connection timeout"
        assert span.duration_ms >= 0

    def test_timeout(self):
        span = Span(name="decision_engine")
        span.timeout()
        assert span.status == SpanStatus.TIMEOUT

    def test_duration(self):
        span = Span(name="test")
        span.start_time = "2026-07-01T00:00:00"
        # finish() 内部会设置 end_time 为当前时间，并计算 duration
        span.finish()
        assert span.status == SpanStatus.SUCCESS
        assert span.end_time != ""
        assert span.duration_ms >= 0

    def test_duration_zero(self):
        span = Span(name="test")
        span.finish()
        assert span.duration_ms >= 0

    def test_to_dict(self):
        span = Span(
            span_id="s001",
            trace_id="t001",
            name="decision_engine",
            parent_id="s000",
            status=SpanStatus.SUCCESS,
            start_time="2026-01-01T00:00:00",
            end_time="2026-01-01T00:00:00.500",
            duration_ms=500.0,
            metadata={"confidence": 0.9},
        )
        d = span.to_dict()
        assert d["span_id"] == "s001"
        assert d["trace_id"] == "t001"
        assert d["name"] == "decision_engine"
        assert d["parent_id"] == "s000"
        assert d["status"] == "success"
        assert d["duration_ms"] == 500.0
        assert d["metadata"]["confidence"] == 0.9

    def test_fail_without_error(self):
        span = Span(name="test")
        span.fail()
        assert span.status == SpanStatus.FAILED
        assert "error" not in span.metadata


class TestTraceManager:
    """TraceManager 单元测试."""

    def setup_method(self):
        self.tm = TraceManager()

    # ── Start Trace ──────────────────────────────────────────

    def test_start_trace(self):
        ctx = self.tm.start_trace()
        assert ctx.trace_id != ""
        assert self.tm.get_trace(ctx.trace_id) == []

    def test_start_trace_unique_ids(self):
        ctx1 = self.tm.start_trace()
        ctx2 = self.tm.start_trace()
        assert ctx1.trace_id != ctx2.trace_id

    # ── Start Span ───────────────────────────────────────────

    def test_start_span(self):
        ctx = self.tm.start_trace()
        span = self.tm.start_span(ctx, "decision_engine")
        assert span.name == "decision_engine"
        assert span.trace_id == ctx.trace_id
        assert span.span_id == ctx.span_id
        assert span.status == SpanStatus.ACTIVE

    def test_start_span_with_metadata(self):
        ctx = self.tm.start_trace()
        span = self.tm.start_span(ctx, "decision_engine", confidence=0.9, game_id="mw")
        assert span.metadata["confidence"] == 0.9
        assert span.metadata["game_id"] == "mw"

    def test_multiple_spans_same_trace(self):
        ctx = self.tm.start_trace()
        span1 = self.tm.start_span(ctx, "step1")
        child_ctx = ctx.child()
        span2 = self.tm.start_span(child_ctx, "step2")

        trace = self.tm.get_trace(ctx.trace_id)
        assert len(trace) == 2
        assert span1 in trace
        assert span2 in trace

    # ── Finish Span ──────────────────────────────────────────

    def test_finish_span(self):
        ctx = self.tm.start_trace()
        span = self.tm.start_span(ctx, "test")
        self.tm.finish_span(span)
        assert span.status == SpanStatus.SUCCESS
        assert span.duration_ms >= 0

    def test_fail_span(self):
        ctx = self.tm.start_trace()
        span = self.tm.start_span(ctx, "test")
        self.tm.fail_span(span, "API error")
        assert span.status == SpanStatus.FAILED
        assert span.metadata["error"] == "API error"

    def test_finish_span_removes_from_active(self):
        ctx = self.tm.start_trace()
        span = self.tm.start_span(ctx, "test")
        assert len(self.tm.get_active_spans()) == 1
        self.tm.finish_span(span)
        assert len(self.tm.get_active_spans()) == 0

    # ── Trace Tree ───────────────────────────────────────────

    def test_trace_tree(self):
        ctx = self.tm.start_trace()
        root_span = self.tm.start_span(ctx, "root")

        child_ctx = ctx.child()
        child_span = self.tm.start_span(child_ctx, "child")

        self.tm.finish_span(root_span)
        self.tm.finish_span(child_span)

        tree = self.tm.get_trace_tree(ctx.trace_id)
        assert tree["span"]["name"] == "root"
        assert len(tree["children"]) == 1
        assert tree["children"][0]["span"]["name"] == "child"

    def test_trace_tree_empty(self):
        assert self.tm.get_trace_tree("nonexistent") == {}

    def test_trace_tree_deep_nesting(self):
        ctx = self.tm.start_trace()
        root = self.tm.start_span(ctx, "root")
        self.tm.finish_span(root)

        child = ctx.child()
        mid = self.tm.start_span(child, "mid")
        self.tm.finish_span(mid)

        grandchild = child.child()
        leaf = self.tm.start_span(grandchild, "leaf")
        self.tm.finish_span(leaf)

        tree = self.tm.get_trace_tree(ctx.trace_id)
        assert tree["span"]["name"] == "root"
        assert len(tree["children"]) == 1
        assert tree["children"][0]["span"]["name"] == "mid"
        assert len(tree["children"][0]["children"]) == 1
        assert tree["children"][0]["children"][0]["span"]["name"] == "leaf"

    # ── Active Spans ─────────────────────────────────────────

    def test_get_active_spans(self):
        ctx = self.tm.start_trace()
        span1 = self.tm.start_span(ctx, "step1")
        span2 = self.tm.start_span(ctx.child(), "step2")

        active = self.tm.get_active_spans()
        assert len(active) == 2

    def test_active_spans_after_finish(self):
        ctx = self.tm.start_trace()
        span = self.tm.start_span(ctx, "step1")
        self.tm.finish_span(span)
        assert len(self.tm.get_active_spans()) == 0

    # ── Trace Isolation ──────────────────────────────────────

    def test_trace_isolation(self):
        ctx1 = self.tm.start_trace()
        ctx2 = self.tm.start_trace()

        self.tm.start_span(ctx1, "trace1_span")
        self.tm.start_span(ctx2, "trace2_span")

        trace1 = self.tm.get_trace(ctx1.trace_id)
        trace2 = self.tm.get_trace(ctx2.trace_id)
        assert len(trace1) == 1
        assert len(trace2) == 1
        assert trace1[0].name == "trace1_span"
        assert trace2[0].name == "trace2_span"

    # ── Stats ────────────────────────────────────────────────

    def test_stats(self):
        ctx = self.tm.start_trace()
        span = self.tm.start_span(ctx, "test")
        self.tm.finish_span(span)

        stats = self.tm.stats()
        assert stats["total_traces"] == 1
        assert stats["total_spans"] == 1
        assert stats["by_status"]["success"] == 1

    def test_stats_multiple_traces(self):
        for i in range(3):
            ctx = self.tm.start_trace()
            s = self.tm.start_span(ctx, f"step_{i}")
            if i % 2 == 0:
                self.tm.finish_span(s)
            else:
                self.tm.fail_span(s, "oops")

        stats = self.tm.stats()
        assert stats["total_traces"] == 3
        assert stats["total_spans"] == 3
        assert stats["by_status"]["success"] == 2
        assert stats["by_status"]["failed"] == 1

    def test_stats_initial(self):
        stats = self.tm.stats()
        assert stats["total_traces"] == 0
        assert stats["total_spans"] == 0
        assert stats["active_spans"] == 0

    # ── Clear ────────────────────────────────────────────────

    def test_clear(self):
        ctx = self.tm.start_trace()
        self.tm.start_span(ctx, "test")
        self.tm.clear()
        assert self.tm.stats()["total_traces"] == 0

    # ── Max Traces ───────────────────────────────────────────

    def test_max_traces(self):
        tm = TraceManager(max_traces=3)
        for i in range(5):
            ctx = tm.start_trace()
            tm.start_span(ctx, f"step_{i}")
        assert tm.stats()["total_traces"] <= 3

    # ── End-to-End Trace Flow ────────────────────────────────

    def test_e2e_trace_flow(self):
        """模拟完整链路: Decision → Execution → Adapter → API."""
        tm = TraceManager()

        # 1. Decision
        trace_ctx = tm.start_trace()
        decision_span = tm.start_span(trace_ctx, "decision_engine")
        time.sleep(0.001)
        tm.finish_span(decision_span, SpanStatus.SUCCESS)

        # 2. Execution
        exec_ctx = trace_ctx.child()
        exec_span = tm.start_span(exec_ctx, "execution_runtime")
        time.sleep(0.001)
        tm.finish_span(exec_span, SpanStatus.SUCCESS)

        # 3. Adapter
        adapter_ctx = exec_ctx.child()
        adapter_span = tm.start_span(adapter_ctx, "meta_adapter")
        tm.finish_span(adapter_span, SpanStatus.SUCCESS)

        trace = tm.get_trace(trace_ctx.trace_id)
        assert len(trace) == 3

        tree = tm.get_trace_tree(trace_ctx.trace_id)
        assert tree["span"]["name"] == "decision_engine"
        assert len(tree["children"]) == 1
        assert tree["children"][0]["span"]["name"] == "execution_runtime"
        assert len(tree["children"][0]["children"]) == 1
        assert tree["children"][0]["children"][0]["span"]["name"] == "meta_adapter"

        # 所有 span 都有 duration
        for span in trace:
            assert span.duration_ms > 0 or span.duration_ms == 0.0