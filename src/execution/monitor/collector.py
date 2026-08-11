"""P2.5.2 ExecutionEvent Collector（事件采集 + 摘要 + JSONL 存储）。

Monitor 的输入端：从 P2.4 SafeExecutionOutcome（及其原始 ExecutionRequest）
派生可观测事件与归一化摘要，不做任何决策、不修改结果、不调用外部 API。

- ``collect(outcome) -> List[ExecutionEvent]``：从一次执行产出事件流
- ``summarize(request, outcome) -> ExecutionSummary``：产出供 Metrics/Anomaly/
  Health 复用的归一化摘要（含 intended_action 以支持 DRIFT 检测）
- ``JsonlExecutionEventStore``：事件持久化（append-only JSONL）
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.execution.monitor.models import (
    EVENT_APPROVAL_GRANTED,
    EVENT_CREATED,
    EVENT_EXECUTION_STARTED,
    EVENT_PROVIDER_CALLED,
    EVENT_PROVIDER_FAILED,
    EVENT_PROVIDER_SUCCESS,
    EVENT_ROLLBACK_FAILED,
    EVENT_ROLLBACK_STARTED,
    EVENT_ROLLBACK_SUCCESS,
    EVENT_VERIFIED,
    ExecutionEvent,
    ExecutionSummary,
    _as_str,
)
from src.execution.safe_executor.models import (
    VERDICT_BLOCKED,
    VERDICT_ESCALATED,
    VERDICT_EXECUTED,
    VERDICT_FAILED,
    VERDICT_RETURN_EXISTING,
    VERDICT_ROLLED_BACK,
    SafeExecutionOutcome,
)
from src.execution.models import ExecutionRequest


def _parse_iso(value: str) -> Optional[datetime]:
    """宽松解析 ISO-8601（兼容 ``Z`` 尾标与毫秒）。失败返回 None。"""
    if not value:
        return None
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        # 退化为秒级
        try:
            return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return None


def _verdict_final_state(verdict: str) -> str:
    from src.execution.monitor.models import (
        STATE_BLOCKED,
        STATE_ESCALATED,
        STATE_FAILED,
        STATE_ROLLED_BACK,
        STATE_SUCCESS,
    )

    return {
        VERDICT_EXECUTED: STATE_SUCCESS,
        VERDICT_RETURN_EXISTING: STATE_SUCCESS,
        VERDICT_BLOCKED: STATE_BLOCKED,
        VERDICT_ROLLED_BACK: STATE_ROLLED_BACK,
        VERDICT_ESCALATED: STATE_ESCALATED,
        VERDICT_FAILED: STATE_FAILED,
    }.get(verdict, STATE_SUCCESS)


class ExecutionEventCollector:
    """从 SafeExecutionOutcome 派生事件流（纯函数，无状态）。"""

    def collect(self, outcome: SafeExecutionOutcome) -> List[ExecutionEvent]:
        ctx = outcome.context
        verdict = outcome.verdict
        final_state = _verdict_final_state(verdict)
        provider = ""
        if outcome.result is not None:
            provider = _as_str(getattr(outcome.result, "provider", ""))
        action = _as_str(ctx.action)
        rid = ctx.execution_id

        events: List[ExecutionEvent] = []
        # 1) 创建
        events.append(
            ExecutionEvent(
                execution_id=rid,
                event_type=EVENT_CREATED,
                provider=provider,
                action=action,
                status=final_state,
                metadata={"mode": ctx.mode, "target": ctx.target},
            )
        )
        # 2) 授权（仅当携带 authorization_id）
        if ctx.authorization_id:
            events.append(
                ExecutionEvent(
                    execution_id=rid,
                    event_type=EVENT_APPROVAL_GRANTED,
                    provider=provider,
                    action=action,
                    status=final_state,
                    metadata={"authorization_id": ctx.authorization_id},
                )
            )

        if verdict == VERDICT_BLOCKED:
            # 闸门拦截：从未触碰外部系统，无后续执行事件
            return events

        if verdict == VERDICT_RETURN_EXISTING:
            # 幂等命中短路：直接 VERIFIED，无 Provider 调用
            events.append(
                ExecutionEvent(
                    execution_id=rid,
                    event_type=EVENT_VERIFIED,
                    provider=provider,
                    action=action,
                    status=final_state,
                    metadata={"idempotent": True},
                )
            )
            return events

        # 以下分支均已真实尝试执行
        events.append(
            ExecutionEvent(
                execution_id=rid,
                event_type=EVENT_EXECUTION_STARTED,
                provider=provider,
                action=action,
                status=final_state,
                metadata={"mode": ctx.mode},
            )
        )
        real = False
        if outcome.result is not None:
            real = bool(getattr(outcome.result, "real_api_called", False))
        events.append(
            ExecutionEvent(
                execution_id=rid,
                event_type=EVENT_PROVIDER_CALLED,
                provider=provider,
                action=action,
                status=final_state,
                metadata={"real_api_called": real},
            )
        )
        if verdict in (VERDICT_EXECUTED,):
            events.append(
                ExecutionEvent(
                    execution_id=rid,
                    event_type=EVENT_PROVIDER_SUCCESS,
                    provider=provider,
                    action=action,
                    status=final_state,
                )
            )
            events.append(
                ExecutionEvent(
                    execution_id=rid,
                    event_type=EVENT_VERIFIED,
                    provider=provider,
                    action=action,
                    status=final_state,
                    metadata={"verified": True},
                )
            )
        elif verdict in (VERDICT_FAILED, VERDICT_ROLLED_BACK, VERDICT_ESCALATED):
            events.append(
                ExecutionEvent(
                    execution_id=rid,
                    event_type=EVENT_PROVIDER_FAILED,
                    provider=provider,
                    action=action,
                    status=final_state,
                    metadata=(
                        {"error": _as_str(getattr(outcome.result, "error", ""))}
                        if outcome.result is not None
                        else {}
                    ),
                )
            )
            if verdict in (VERDICT_ROLLED_BACK, VERDICT_ESCALATED):
                events.append(
                    ExecutionEvent(
                        execution_id=rid,
                        event_type=EVENT_ROLLBACK_STARTED,
                        provider=provider,
                        action=action,
                        status=final_state,
                    )
                )
                if verdict == VERDICT_ROLLED_BACK:
                    events.append(
                        ExecutionEvent(
                            execution_id=rid,
                            event_type=EVENT_ROLLBACK_SUCCESS,
                            provider=provider,
                            action=action,
                            status=final_state,
                        )
                    )
                    events.append(
                        ExecutionEvent(
                            execution_id=rid,
                            event_type=EVENT_VERIFIED,
                            provider=provider,
                            action=action,
                            status=final_state,
                            metadata={"rolled_back": True},
                        )
                    )
                else:  # ESCALATED：回滚失败
                    events.append(
                        ExecutionEvent(
                            execution_id=rid,
                            event_type=EVENT_ROLLBACK_FAILED,
                            provider=provider,
                            action=action,
                            status=final_state,
                            metadata={"escalated": True},
                        )
                    )
        return events

    def summarize(
        self, request: Optional[ExecutionRequest], outcome: SafeExecutionOutcome
    ) -> ExecutionSummary:
        ctx = outcome.context
        provider = ""
        is_real = False
        if outcome.result is not None:
            provider = _as_str(getattr(outcome.result, "provider", ""))
            is_real = bool(getattr(outcome.result, "real_api_called", False))
        intended_action = ""
        if request is not None:
            intent = getattr(request, "intent", None)
            if intent is not None:
                intended_action = _as_str(getattr(intent, "action", ""))
        latency = 0.0
        start = _parse_iso(ctx.started_at)
        end = _parse_iso(ctx.finished_at)
        if start is not None and end is not None:
            latency = max(0.0, (end - start).total_seconds())
        return ExecutionSummary(
            execution_id=ctx.execution_id,
            action=_as_str(ctx.action),
            target=_as_str(ctx.target),
            provider=provider,
            verdict=_as_str(outcome.verdict),
            status=_verdict_final_state(outcome.verdict),
            timestamp=ctx.started_at,
            is_real=is_real,
            intended_action=intended_action,
            latency_seconds=round(latency, 3),
        )


class JsonlExecutionEventStore:
    """append-only JSONL 事件存储。"""

    def __init__(self, path: str = "data/ceo/execution_events.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def append(self, events: List[ExecutionEvent]) -> None:
        if not events:
            return
        with self.path.open("a", encoding="utf-8") as f:
            for ev in events:
                f.write(json.dumps(ev.to_dict(), ensure_ascii=False) + "\n")

    def all(self) -> List[ExecutionEvent]:
        if not self.path.exists():
            return []
        out: List[ExecutionEvent] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(ExecutionEvent.from_dict(json.loads(line)))
        return out

    def for_execution(self, execution_id: str) -> List[ExecutionEvent]:
        return [e for e in self.all() if e.execution_id == execution_id]


__all__ = [
    "ExecutionEventCollector",
    "JsonlExecutionEventStore",
    "_parse_iso",
]
