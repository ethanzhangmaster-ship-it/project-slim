"""P2.5.8 Execution Monitor — 执行可观测层门面（Facade）。

链路位置：
    ... -> P2.4 SafeExecutor -> ExecutionResult -> **P2.5 Monitor**
    -> (状态追踪 / SLA 监控 / 异常检测 / Provider 健康 / 回传 Memory)

核心纪律（不可违背）：
    - 只观察，不做决策
    - 不修改执行结果
    - 不绕过 Approval
    - 不直接调用平台 API
    - 流程：observe -> detect -> report -> feedback

本模块暴露：
    - ExecutionMonitor 门面：observe() / report() / observe_batch()
    - 各子模块全部公开符号（models / collector / state_tracker / health /
      anomaly / reporter / feedback）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.execution.monitor.anomaly import (
    AnomalyDetector,
    AnomalyFinding,
    AnomalyReport,
)
from src.execution.monitor.collector import (
    ExecutionEventCollector,
    JsonlExecutionEventStore,
    _parse_iso,
)
from src.execution.monitor.feedback import (
    ExecutionExperienceRecord,
    ExecutionExperienceStore,
    FeedbackBridge,
    JsonlExecutionExperienceStore,
    default_reward,
)
from src.execution.monitor.health import (
    ExecutionHealthScore,
    ProviderHealth,
    compute_health_score,
    compute_metrics,
    compute_provider_health,
    latency_level,
    latency_score,
)
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
    HEALTH_GREEN,
    HEALTH_RED,
    HEALTH_YELLOW,
    IllegalStateTransitionError,
    SEVERITY_ALERT,
    SEVERITY_BLOCK,
    SEVERITY_RED,
    SEVERITY_WARNING,
    STATE_AUTHORIZED,
    STATE_BLOCKED,
    STATE_CREATED,
    STATE_ESCALATED,
    STATE_FAILED,
    STATE_ROLLBACK,
    STATE_ROLLED_BACK,
    STATE_RUNNING,
    STATE_SUCCESS,
    TERMINAL_STATES,
    VALID_EVENT_TYPES,
    VALID_HEALTH_LEVELS,
    VALID_STATES,
    ExecutionEvent,
    ExecutionMetrics,
    ExecutionSummary,
)
from src.execution.monitor.reporter import (
    ExecutionDailyReport,
    ExecutionReporter,
)
from src.execution.monitor.state_tracker import (
    ExecutionStateTracker,
    TrackedState,
    ctx_to_state,
    validate_transition,
)
from src.execution.models import ExecutionRequest
from src.execution.safe_executor.models import SafeExecutionOutcome


@dataclass
class ObservationResult:
    """单次 observe() 的产出（全部为观察结论，无副作用决策）。"""

    execution_id: str
    events: List[ExecutionEvent] = field(default_factory=list)
    tracked_state: Optional[TrackedState] = None
    summary: Optional[ExecutionSummary] = None
    experience: Optional[ExecutionExperienceRecord] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "events": [e.to_dict() for e in self.events],
            "tracked_state": self.tracked_state.to_dict()
            if self.tracked_state
            else None,
            "summary": self.summary.to_dict() if self.summary else None,
            "experience": self.experience.to_dict() if self.experience else None,
        }


class ExecutionMonitor:
    """执行可观测层门面。

    observe()   : 单次执行观察（事件采集 + 状态追踪 + 经验回流）
    report()    : 批量报告（指标 + 异常 + 健康分 + 每日报告 + 经验学习）
    observe_batch(): 批量 observe + 汇总报告（全链路验收入口）
    """

    def __init__(
        self,
        *,
        event_store: Optional[JsonlExecutionEventStore] = None,
        feedback_store: Optional[ExecutionExperienceStore] = None,
        graph: Any = None,
    ) -> None:
        self.collector = ExecutionEventCollector()
        self.state_tracker = ExecutionStateTracker()
        self.anomaly_detector = AnomalyDetector()
        self.reporter = ExecutionReporter()
        self.feedback = FeedbackBridge(store=feedback_store, graph=graph)
        self.event_store = event_store

    # ------------------------------------------------------------------
    # 单次观察
    # ------------------------------------------------------------------
    def observe(
        self,
        request: Optional[ExecutionRequest],
        outcome: SafeExecutionOutcome,
    ) -> ObservationResult:
        # 1) 事件采集
        events = self.collector.collect(outcome)
        if self.event_store is not None:
            self.event_store.append(events)
        # 2) 状态追踪
        tracked = self.state_tracker.track_execution(outcome)
        # 3) 摘要
        summary = self.collector.summarize(request, outcome)
        # 4) 经验回流 Memory（经验库 + E17.7 图谱）
        experience = self.feedback.push(request, outcome)
        self.feedback.push_to_graph(experience)
        return ObservationResult(
            execution_id=outcome.context.execution_id,
            events=events,
            tracked_state=tracked,
            summary=summary,
            experience=experience,
        )

    # ------------------------------------------------------------------
    # 批量报告
    # ------------------------------------------------------------------
    def report(
        self,
        date: str,
        outcomes: List[SafeExecutionOutcome],
        requests: Optional[List[ExecutionRequest]] = None,
    ) -> ExecutionDailyReport:
        requests = requests or [None] * len(outcomes)
        summaries: List[ExecutionSummary] = []
        for req, out in zip(requests, outcomes):
            summaries.append(self.collector.summarize(req, out))

        anomalies = self.anomaly_detector.analyze(summaries, scope=date)
        health = compute_health_score(outcomes)

        # 注意：经验回流由 observe() 负责（单次执行即 push），report() 只聚合观察结论，
        # 不重复 push，避免重复写入经验库 / 图谱。
        learnings = self._derive_learnings(summaries)
        return self.reporter.build(
            date=date,
            outcomes=outcomes,
            anomalies=anomalies,
            learnings=learnings,
            health_level=health.level,
        )

    def _derive_learnings(self, summaries: List[ExecutionSummary]) -> List[str]:
        """从本次批量经验库统计，提炼可读学习点。"""
        learnings: List[str] = []
        by_action: Dict[str, List[float]] = {}
        for s in summaries:
            rewards = by_action.setdefault(s.action, [])
            if s.is_real:
                # 仅基于真实执行反馈的学习才有意义（DRY_RUN 不污染）
                rewards.append(1.0 if s.verdict in ("EXECUTED",) else 0.0)
        for action, vals in by_action.items():
            if not vals:
                continue
            rate = sum(vals) / len(vals)
            learnings.append(
                f"动作 {action}：真实执行成功率 {rate:.0%}（n={len(vals)}）"
            )
        return learnings

    # ------------------------------------------------------------------
    # 全链路入口
    # ------------------------------------------------------------------
    def observe_batch(
        self,
        paired: List[Tuple[Optional[ExecutionRequest], SafeExecutionOutcome]],
        date: str = "",
    ) -> Tuple[List[ObservationResult], ExecutionDailyReport]:
        if not date:
            date = "batch"
        results: List[ObservationResult] = []
        outcomes: List[SafeExecutionOutcome] = []
        requests: List[ExecutionRequest] = []
        for req, out in paired:
            results.append(self.observe(req, out))
            outcomes.append(out)
            requests.append(req)
        report = self.report(date, outcomes, requests=requests)
        return results, report


__all__ = [
    # facade
    "ExecutionMonitor",
    "ObservationResult",
    # models
    "ExecutionEvent",
    "ExecutionSummary",
    "ExecutionMetrics",
    "IllegalStateTransitionError",
    "EVENT_CREATED",
    "EVENT_APPROVAL_GRANTED",
    "EVENT_EXECUTION_STARTED",
    "EVENT_PROVIDER_CALLED",
    "EVENT_PROVIDER_SUCCESS",
    "EVENT_PROVIDER_FAILED",
    "EVENT_ROLLBACK_STARTED",
    "EVENT_ROLLBACK_SUCCESS",
    "EVENT_ROLLBACK_FAILED",
    "EVENT_VERIFIED",
    "STATE_CREATED",
    "STATE_AUTHORIZED",
    "STATE_RUNNING",
    "STATE_SUCCESS",
    "STATE_FAILED",
    "STATE_ROLLBACK",
    "STATE_ROLLED_BACK",
    "STATE_BLOCKED",
    "STATE_ESCALATED",
    "HEALTH_GREEN",
    "HEALTH_RED",
    "HEALTH_YELLOW",
    "SEVERITY_RED",
    "SEVERITY_WARNING",
    "SEVERITY_BLOCK",
    "SEVERITY_ALERT",
    "VALID_EVENT_TYPES",
    "VALID_STATES",
    "VALID_HEALTH_LEVELS",
    "TERMINAL_STATES",
    # collector
    "ExecutionEventCollector",
    "JsonlExecutionEventStore",
    # state tracker
    "ExecutionStateTracker",
    "TrackedState",
    "validate_transition",
    "ctx_to_state",
    # health
    "latency_level",
    "latency_score",
    "ProviderHealth",
    "compute_provider_health",
    "compute_metrics",
    "ExecutionHealthScore",
    "compute_health_score",
    # anomaly
    "AnomalyDetector",
    "AnomalyFinding",
    "AnomalyReport",
    # reporter
    "ExecutionDailyReport",
    "ExecutionReporter",
    # feedback
    "ExecutionExperienceRecord",
    "ExecutionExperienceStore",
    "JsonlExecutionExperienceStore",
    "FeedbackBridge",
    "default_reward",
]
