"""P2.6 Execution Recovery Layer — 执行恢复层（自愈）。

完整链路（用户契约）：

    Execution Failure -> RecoveryEngine -> Diagnose(Classifier)
    -> Choose Strategy(Planner) -> Execute Recovery(经 P2.3+P2.4)
    -> Verify(Verifier) -> Escalate/Close -> Learn(Memory Bridge)

纪律红线：
- 恢复动作绝不绕过 P2.3——RecoveryExecutor 的唯一出口是 SafeExecutor
- 本层不决策（决策属 E17.3）、不授权（授权属 P2.3）
- CRITICAL 升级 -> halt_automation：停止所有自动执行

Memory 回流：RecoveryResult -> E16 经验库(JSONL) + E17.7 Growth Memory Graph，
记录 {failure, action, recovery, result, reward}，
让 AI 学到「Meta timeout 通常 retry 有效」。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.execution.recovery.models import (  # noqa: F401
    FAILURE_AUTH,
    FAILURE_ROLLBACK_FAILED,
    FAILURE_STATE_DRIFT,
    FAILURE_TIMEOUT,
    FAILURE_UNKNOWN,
    INCIDENT_CLASSIFIED,
    INCIDENT_CLOSED,
    INCIDENT_DETECTED,
    INCIDENT_ESCALATED,
    INCIDENT_PLANNED,
    INCIDENT_RECOVERING,
    INCIDENT_VERIFIED,
    RECOVERY_ESCALATED,
    RECOVERY_NOT_RECOVERED,
    RECOVERY_RECOVERED,
    RECOVERY_REWARDS,
    RECOVERY_SKIPPED,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    STRATEGY_ESCALATION,
    STRATEGY_RECONCILE,
    STRATEGY_RETRY,
    STRATEGY_ROLLBACK_RETRY,
    TERMINAL_INCIDENT_STATUSES,
    TREATMENT_EMERGENCY_ESCALATE,
    TREATMENT_ESCALATE,
    TREATMENT_RECONCILE,
    TREATMENT_RETRY,
    TREATMENT_ROLLBACK_RETRY,
    VALID_FAILURE_TYPES,
    VALID_INCIDENT_STATUSES,
    VALID_RECOVERY_STATUSES,
    VALID_SEVERITIES,
    VALID_STRATEGIES,
    VALID_TREATMENTS,
    VALID_VERIFY_STATUSES,
    VERIFY_NOT_RECOVERED,
    VERIFY_RECOVERED,
    VERIFY_UNVERIFIABLE,
    EscalationTicket,
    FailureClassification,
    IllegalIncidentTransitionError,
    RecoveryAttempt,
    RecoveryExperienceRecord,
    RecoveryIncident,
    RecoveryPlan,
    RecoveryResult,
    VerificationResult,
    _as_str,
    reward_for,
    severity_rank,
)
from src.execution.recovery.classifier import FailureClassifier  # noqa: F401
from src.execution.recovery.strategy import (  # noqa: F401
    DEFAULT_RETRY_BACKOFF,
    DEFAULT_RETRY_MAX_ATTEMPTS,
    DEFAULT_ROLLBACK_MAX_RETRY,
    EscalationPolicy,
    ReconcilePolicy,
    RetryPolicy,
    RollbackRetryPolicy,
    backoff_for,
    policy_for_treatment,
)
from src.execution.recovery.planner import (  # noqa: F401
    RISK_ESCALATE_THRESHOLD,
    RecoveryPlanner,
)
from src.execution.recovery.executor import RecoveryExecutor  # noqa: F401
from src.execution.recovery.verifier import RecoveryVerifier  # noqa: F401
from src.execution.recovery.escalation import (  # noqa: F401
    ESCALATION_LEVELS,
    EscalationManager,
    InMemoryEscalationStore,
    JsonlEscalationStore,
)


# ---------------------------------------------------------------------------
# RecoveryMemoryBridge — 恢复经验回流 E16 + E17.7
# ---------------------------------------------------------------------------


class JsonlRecoveryExperienceStore:
    """append-only 恢复经验库（E16 风格 JSONL）。"""

    def __init__(self, path: str = "data/ceo/recovery_experience.jsonl"):
        self.path = Path(path)

    def add(self, record: RecoveryExperienceRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def all(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        out: List[Dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def for_failure(self, failure: str) -> List[Dict[str, Any]]:
        failure = _as_str(failure)
        return [e for e in self.all() if e.get("failure") == failure]

    def stats(self, failure: str, recovery: str = "") -> Dict[str, Any]:
        """某类故障（可选限定策略）的恢复成功率——「timeout 通常 retry 有效」。"""
        rows = self.for_failure(failure)
        if recovery:
            recovery = _as_str(recovery)
            rows = [r for r in rows if r.get("recovery") == recovery]
        n = len(rows)
        if n == 0:
            return {"n": 0, "success_rate": 0.0, "avg_reward": 0.0}
        successes = sum(1 for r in rows if r.get("success"))
        avg_reward = sum(float(r.get("reward", 0.0)) for r in rows) / n
        return {
            "n": n,
            "success_rate": round(successes / n, 4),
            "avg_reward": round(avg_reward, 4),
        }


class InMemoryRecoveryExperienceStore(JsonlRecoveryExperienceStore):
    """同契约内存版（测试用）。"""

    def __init__(self):  # noqa: D107
        self._records: List[Dict[str, Any]] = []

    def add(self, record: RecoveryExperienceRecord) -> None:
        self._records.append(record.to_dict())

    def all(self) -> List[Dict[str, Any]]:
        return list(self._records)


class RecoveryMemoryBridge:
    """恢复经验回流 Memory（E16 经验库 + E17.7 图谱）。

    与 P2.5 FeedbackBridge 同纪律：只回流，不决策；图谱懒导入。
    """

    def __init__(
        self,
        store: Optional[JsonlRecoveryExperienceStore] = None,
        graph: Any = None,
    ):
        self.store = store or JsonlRecoveryExperienceStore()
        self.graph = graph

    def push(
        self,
        incident: RecoveryIncident,
        plan: Optional[RecoveryPlan],
        result: RecoveryResult,
    ) -> RecoveryExperienceRecord:
        """RecoveryResult -> RecoveryExperienceRecord -> 经验库。"""
        record = RecoveryExperienceRecord(
            failure=incident.failure_type,
            action=incident.action,
            recovery=(plan.strategy if plan is not None else STRATEGY_ESCALATION),
            result=result.status,
            reward=reward_for(result.status),
            provider=incident.provider,
            incident_id=incident.incident_id,
            attempts=result.attempts,
            metadata={
                "severity": incident.severity,
                "execution_id": incident.execution_id,
            },
        )
        self.store.add(record)
        return record

    def push_to_graph(
        self, record: RecoveryExperienceRecord, graph: Any = None
    ) -> Dict[str, Any]:
        """恢复经验推入 E17.7 图谱（execution -> action -> result 链路）。

        懒导入避免循环依赖；graph 缺失/非法时优雅降级。
        """
        target = graph or self.graph
        if target is None:
            return {"skipped": True, "reason": "no_graph"}
        try:
            from src.ceo_intelligence.growth_memory_graph.models import (
                EdgeType,
                GraphEdge,
                GraphNode,
                NodeType,
                node_id,
            )
            from src.ceo_intelligence.growth_memory_graph.store import (
                GrowthMemoryGraph,
            )
        except Exception:  # noqa: BLE001
            return {"skipped": True, "reason": "import_error"}

        if not isinstance(target, GrowthMemoryGraph):
            return {"skipped": True, "reason": "not_a_graph"}

        rid = record.incident_id or f"rec_{record.created_at}"
        exe_node = GraphNode(
            id=node_id(NodeType.EXECUTION, rid),
            type=NodeType.EXECUTION,
            label=f"recovery:{rid}",
            payload={
                "failure": record.failure,
                "action": record.action,
                "provider": record.provider,
            },
        )
        act_node = GraphNode(
            id=node_id(NodeType.ACTION, rid),
            type=NodeType.ACTION,
            label=f"recovery_action:{rid}",
            payload={"recovery": record.recovery, "attempts": record.attempts},
        )
        res_node = GraphNode(
            id=node_id(NodeType.RESULT, rid),
            type=NodeType.RESULT,
            label=f"recovery_result:{rid}",
            payload={
                "result": record.result,
                "reward": record.reward,
                "success": record.success,
            },
        )
        added = []
        for n in (exe_node, act_node, res_node):
            if target.add_node(n):
                added.append(n.id)
        target.add_edge(GraphEdge(exe_node.id, act_node.id, EdgeType.INCLUDES_ACTION))
        target.add_edge(GraphEdge(act_node.id, res_node.id, EdgeType.PRODUCES_RESULT))
        return {"skipped": False, "nodes_added": added, "edges": 2}


# ---------------------------------------------------------------------------
# RecoveryEngine — 门面编排
# ---------------------------------------------------------------------------


class RecoveryEngine:
    """恢复引擎门面：classify -> plan -> recover -> verify -> escalate -> learn。

    Args:
        safe_executor : P2.4 SafeExecutor（恢复执行唯一出口）
        classifier    : FailureClassifier（可注入定制）
        planner       : RecoveryPlanner
        verifier      : RecoveryVerifier
        escalation    : EscalationManager（含 P2.3 接口 / 工单库）
        memory        : RecoveryMemoryBridge（E16 + E17.7 回流）
        executor      : RecoveryExecutor（缺省用 safe_executor 构造）
    """

    def __init__(
        self,
        safe_executor: Any = None,
        classifier: Optional[FailureClassifier] = None,
        planner: Optional[RecoveryPlanner] = None,
        verifier: Optional[RecoveryVerifier] = None,
        escalation: Optional[EscalationManager] = None,
        memory: Optional[RecoveryMemoryBridge] = None,
        executor: Optional[RecoveryExecutor] = None,
        **executor_kwargs: Any,
    ):
        if executor is None and safe_executor is None:
            raise ValueError(
                "RecoveryEngine requires safe_executor or executor"
            )
        self.classifier = classifier or FailureClassifier()
        self.planner = planner or RecoveryPlanner()
        self.verifier = verifier or RecoveryVerifier()
        self.escalation = escalation or EscalationManager()
        self.memory = memory or RecoveryMemoryBridge()
        self.executor = executor or RecoveryExecutor(
            safe_executor, **executor_kwargs
        )

    # ------------------------------------------------------------------

    def handle(
        self,
        outcome: Any,
        request: Any,
        alert: Any = None,
        expected_state: Optional[Dict[str, Any]] = None,
    ) -> RecoveryResult:
        """处理一次失败的执行（P2.6 全链路编排）。

        成功执行（outcome.ok）不需要恢复 -> RECOVERY_SKIPPED。
        automation_halted（CRITICAL 未 resolve）-> 一律直接升级，不自动恢复。
        """
        # 0) 成功执行无需恢复
        if bool(getattr(outcome, "ok", False)):
            return RecoveryResult(
                incident_id="",
                status=RECOVERY_SKIPPED,
                message="execution succeeded — nothing to recover",
            )

        incident = RecoveryIncident.from_outcome(outcome, request)

        # 1) Diagnose
        classification = self.classifier.classify(
            outcome, request=request, alert=alert, incident=incident
        )

        # 2) Plan
        intent = getattr(request, "intent", None)
        risk = float(getattr(intent, "risk_level", 0.5) or 0.5)
        plan = self.planner.plan(
            classification,
            action=incident.action,
            target=incident.target,
            provider=incident.provider,
            risk=risk,
            expected_state=expected_state,
            incident=incident,
        )

        # 全局熔断：CRITICAL 工单未 resolve -> 停止所有自动恢复
        if self.escalation.automation_halted() and not plan.escalate_only:
            plan.escalate_only = True
            plan.notes = "automation halted by open CRITICAL ticket"

        # 3) Execute Recovery（经 P2.3 + P2.4，绝不直调 API）
        result = self.executor.recover(incident, plan, request)

        # 4) Verify（仅对声称已恢复的结果做状态验证）
        if result.recovered:
            last_outcome = result.outcome
            verification = self.verifier.verify(
                plan, outcome=last_outcome, expected_state=expected_state
            )
            result.verification = verification
            if verification.status == VERIFY_NOT_RECOVERED:
                # 验证不过 -> 降级为未恢复，走升级
                result.status = RECOVERY_NOT_RECOVERED
                result.message += " | verification failed"
            elif incident.status in (INCIDENT_RECOVERING, INCIDENT_PLANNED):
                # PLANNED 出现在「无操作恢复」（reconcile 已一致）场景：
                # 仍需收敛到 VERIFIED -> CLOSED，避免事件悬在 PLANNED
                if incident.status == INCIDENT_PLANNED:
                    incident.transition(INCIDENT_RECOVERING, reason="recovery-noop")
                incident.transition(INCIDENT_VERIFIED, reason=verification.message)

        # 5) Escalate（未恢复 / 升级计划）
        if result.status in (RECOVERY_NOT_RECOVERED, RECOVERY_ESCALATED):
            severity = classification.severity
            if classification.treatment == TREATMENT_EMERGENCY_ESCALATE:
                severity = SEVERITY_CRITICAL
            ticket = self.escalation.escalate(
                incident,
                severity=severity,
                reason=result.message or plan.notes,
                request=request,
            )
            result.escalation = ticket.to_dict()
            result.status = RECOVERY_ESCALATED

        # 终态收敛
        if incident.status in (INCIDENT_VERIFIED, INCIDENT_ESCALATED):
            incident.transition(INCIDENT_CLOSED)

        # 6) Learn：回流 E16 + E17.7
        record = self.memory.push(incident, plan, result)
        self.memory.push_to_graph(record)

        return result


def build_recovery_engine(
    safe_executor: Any,
    approval_workflow: Any = None,
    escalation_store: Optional[JsonlEscalationStore] = None,
    experience_store: Optional[JsonlRecoveryExperienceStore] = None,
    graph: Any = None,
    **executor_kwargs: Any,
) -> RecoveryEngine:
    """一键装配 RecoveryEngine（生产默认 Jsonl 存储）。"""
    return RecoveryEngine(
        safe_executor=safe_executor,
        escalation=EscalationManager(
            store=escalation_store, approval_workflow=approval_workflow
        ),
        memory=RecoveryMemoryBridge(store=experience_store, graph=graph),
        **executor_kwargs,
    )


__all__ = [
    # models re-export
    "RecoveryIncident",
    "FailureClassification",
    "RecoveryPlan",
    "RecoveryAttempt",
    "RecoveryResult",
    "VerificationResult",
    "EscalationTicket",
    "RecoveryExperienceRecord",
    "IllegalIncidentTransitionError",
    "reward_for",
    "severity_rank",
    "RECOVERY_REWARDS",
    # 常量组
    "FAILURE_TIMEOUT",
    "FAILURE_AUTH",
    "FAILURE_STATE_DRIFT",
    "FAILURE_ROLLBACK_FAILED",
    "FAILURE_UNKNOWN",
    "TREATMENT_RETRY",
    "TREATMENT_RECONCILE",
    "TREATMENT_ROLLBACK_RETRY",
    "TREATMENT_ESCALATE",
    "TREATMENT_EMERGENCY_ESCALATE",
    "SEVERITY_LOW",
    "SEVERITY_MEDIUM",
    "SEVERITY_HIGH",
    "SEVERITY_CRITICAL",
    "STRATEGY_RETRY",
    "STRATEGY_RECONCILE",
    "STRATEGY_ROLLBACK_RETRY",
    "STRATEGY_ESCALATION",
    "RECOVERY_RECOVERED",
    "RECOVERY_NOT_RECOVERED",
    "RECOVERY_ESCALATED",
    "RECOVERY_SKIPPED",
    "VERIFY_RECOVERED",
    "VERIFY_NOT_RECOVERED",
    "VERIFY_UNVERIFIABLE",
    "INCIDENT_DETECTED",
    "INCIDENT_CLASSIFIED",
    "INCIDENT_PLANNED",
    "INCIDENT_RECOVERING",
    "INCIDENT_VERIFIED",
    "INCIDENT_ESCALATED",
    "INCIDENT_CLOSED",
    # 组件
    "FailureClassifier",
    "RetryPolicy",
    "ReconcilePolicy",
    "RollbackRetryPolicy",
    "EscalationPolicy",
    "policy_for_treatment",
    "backoff_for",
    "RecoveryPlanner",
    "RISK_ESCALATE_THRESHOLD",
    "RecoveryExecutor",
    "RecoveryVerifier",
    "EscalationManager",
    "JsonlEscalationStore",
    "InMemoryEscalationStore",
    "ESCALATION_LEVELS",
    "JsonlRecoveryExperienceStore",
    "InMemoryRecoveryExperienceStore",
    "RecoveryMemoryBridge",
    "RecoveryEngine",
    "build_recovery_engine",
]
