"""E15.0.11 Trace System — 分布式追踪上下文.

实现跨模块的请求链路追踪:
  - TraceContext: 追踪上下文 (trace_id + span_id + parent_id)
  - Span:         单个追踪片段
  - TraceManager: 追踪管理器

链路示例:
  trace_id=abc001
    Growth Decision    span=001
    Execution Runtime  span=002 (parent=001)
    Adapter            span=003 (parent=002)
    Meta API           span=004 (parent=003)

未来兼容: OpenTelemetry / Jaeger / Grafana Tempo
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Span Status
# ═══════════════════════════════════════════════════════════════


class SpanStatus(str, Enum):
    """Span 状态."""
    ACTIVE = "active"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


# ═══════════════════════════════════════════════════════════════
# Trace Context
# ═══════════════════════════════════════════════════════════════


@dataclass
class TraceContext:
    """分布式追踪上下文.

    Attributes:
        trace_id:  全局追踪 ID (同一请求链路上所有 span 共享)
        span_id:   当前 span ID
        parent_id: 父 span ID (None 表示根 span)
    """

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:16])
    parent_id: str | None = None

    def child(self) -> "TraceContext":
        """创建子级上下文."""
        return TraceContext(
            trace_id=self.trace_id,
            span_id=str(uuid.uuid4())[:16],
            parent_id=self.span_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
        }

    def __repr__(self) -> str:
        return f"TraceContext(trace={self.trace_id[:8]}..., span={self.span_id})"


# ═══════════════════════════════════════════════════════════════
# Span
# ═══════════════════════════════════════════════════════════════


@dataclass
class Span:
    """单个追踪片段 — 记录一次操作的开始和结束.

    Attributes:
        span_id:     Span ID
        trace_id:    追踪 ID
        name:        操作名称
        parent_id:   父 Span ID
        status:      状态
        start_time:  开始时间
        end_time:    结束时间
        duration_ms: 耗时 (毫秒)
        metadata:    扩展元数据
    """

    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:16])
    trace_id: str = ""
    name: str = ""
    parent_id: str | None = None
    status: SpanStatus = SpanStatus.ACTIVE
    start_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: str = ""
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def finish(self, status: SpanStatus = SpanStatus.SUCCESS) -> None:
        """结束 Span."""
        self.status = status
        self.end_time = datetime.now(timezone.utc).isoformat()
        try:
            start = datetime.fromisoformat(self.start_time)
            end = datetime.fromisoformat(self.end_time)
            self.duration_ms = (end - start).total_seconds() * 1000
        except (ValueError, TypeError):
            self.duration_ms = 0.0

    def fail(self, error: str = "") -> None:
        """标记失败."""
        if error:
            self.metadata["error"] = error
        self.finish(SpanStatus.FAILED)

    def timeout(self) -> None:
        """标记超时."""
        self.finish(SpanStatus.TIMEOUT)

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "name": self.name,
            "parent_id": self.parent_id,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return f"Span({self.name}, status={self.status.value}, duration={self.duration_ms:.1f}ms)"


# ═══════════════════════════════════════════════════════════════
# Trace Manager
# ═══════════════════════════════════════════════════════════════


class TraceManager:
    """E15.0.11 追踪管理器 — 管理 Span 生命周期.

    用法:
        tm = TraceManager()

        # 创建根 Trace
        ctx = tm.start_trace()

        # 创建 Span
        span = tm.start_span(ctx, "decision_engine")
        # ... 业务逻辑 ...
        tm.finish_span(span, SpanStatus.SUCCESS)

        # 创建子 Span
        child_ctx = ctx.child()
        child_span = tm.start_span(child_ctx, "execution_adapter")
        tm.finish_span(child_span, SpanStatus.SUCCESS)

        # 查询
        trace = tm.get_trace(ctx.trace_id)
        stats = tm.stats()
    """

    def __init__(self, max_traces: int = 1000):
        self._max_traces = max_traces
        self._spans: dict[str, list[Span]] = {}  # trace_id -> spans
        self._active_spans: dict[str, Span] = {}  # span_id -> active span

    # ── Trace ────────────────────────────────────────────────

    def start_trace(self) -> TraceContext:
        """创建新的根 Trace."""
        ctx = TraceContext()
        self._spans[ctx.trace_id] = []
        return ctx

    # ── Span ─────────────────────────────────────────────────

    def start_span(self, ctx: TraceContext, name: str, **metadata: Any) -> Span:
        """创建并开始 Span.

        Args:
            ctx:  TraceContext
            name: 操作名称
            **metadata: 扩展元数据

        Returns:
            Span: 新创建的 Span
        """
        span = Span(
            span_id=ctx.span_id,
            trace_id=ctx.trace_id,
            name=name,
            parent_id=ctx.parent_id,
            metadata=metadata,
        )

        if ctx.trace_id not in self._spans:
            self._spans[ctx.trace_id] = []

        self._spans[ctx.trace_id].append(span)
        self._active_spans[span.span_id] = span
        self._trim()
        return span

    def finish_span(self, span: Span, status: SpanStatus = SpanStatus.SUCCESS) -> Span:
        """结束 Span.

        Args:
            span:   Span 实例
            status: 结束状态

        Returns:
            Span: 已结束的 Span
        """
        span.finish(status)
        self._active_spans.pop(span.span_id, None)
        return span

    def fail_span(self, span: Span, error: str = "") -> Span:
        """标记 Span 失败."""
        span.fail(error)
        self._active_spans.pop(span.span_id, None)
        return span

    # ── Query ────────────────────────────────────────────────

    def get_trace(self, trace_id: str) -> list[Span]:
        """获取完整 Trace 的所有 Span."""
        return self._spans.get(trace_id, [])

    def get_active_spans(self) -> list[Span]:
        """获取所有活跃 Span."""
        return list(self._active_spans.values())

    def get_trace_tree(self, trace_id: str) -> dict[str, Any]:
        """获取 Trace 树结构."""
        spans = self.get_trace(trace_id)
        if not spans:
            return {}

        # 构建树
        nodes: dict[str, Any] = {}
        for span in spans:
            nodes[span.span_id] = {
                "span": span.to_dict(),
                "children": [],
            }

        root = None
        for span in spans:
            if span.parent_id is None:
                root = nodes[span.span_id]
            elif span.parent_id in nodes:
                nodes[span.parent_id]["children"].append(nodes[span.span_id])

        return root or {}

    # ── Stats ────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        total_spans = sum(len(s) for s in self._spans.values())
        status_counts = {"active": 0, "success": 0, "failed": 0, "timeout": 0}
        for spans in self._spans.values():
            for span in spans:
                status_counts[span.status.value] = status_counts.get(span.status.value, 0) + 1

        return {
            "total_traces": len(self._spans),
            "total_spans": total_spans,
            "active_spans": len(self._active_spans),
            "by_status": status_counts,
        }

    def clear(self) -> None:
        """清空所有 Traces."""
        self._spans.clear()
        self._active_spans.clear()

    # ── Internal ─────────────────────────────────────────────

    def _trim(self) -> None:
        if len(self._spans) > self._max_traces:
            oldest = sorted(self._spans.keys())[: len(self._spans) - self._max_traces]
            for key in oldest:
                del self._spans[key]

    def __repr__(self) -> str:
        return f"TraceManager(traces={len(self._spans)}, active_spans={len(self._active_spans)})"


__all__ = [
    "SpanStatus",
    "TraceContext",
    "Span",
    "TraceManager",
]