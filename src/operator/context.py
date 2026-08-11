"""P3.1 — Operator Context（一次装配全部依赖）。

复用不重写：
- E17.9 DailyGrowthOperatorAgent（Reality→Opportunity→Decision→Simulation→SIM 执行→晨报→跨日记忆）
- P1.7 RealityAuditor（对账 + 新鲜度 + 可信分）
- P2.1 CapabilityRegistry / build_contract（Decision→Contract）
- P2.3 ApprovalService（policy→ApprovalRequest→ExecutionAuthorization）
- P2.2+P2.4 build_execution_router + build_safe_executor（唯一执行出口）
- P2.5 ExecutionMonitor（观察 + 经验回流）
- P2.6 build_recovery_engine（失败自愈，绝不绕过 P2.3）

安全默认：mode=DRY_RUN，全链路 real_api_called 恒 False；
PRODUCTION 必经 P2.3 授权 + P2.4 七步（本层不放松任何门）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from src.ceo_intelligence.daily_operator.agent import DailyGrowthOperatorAgent
from src.ceo_intelligence.daily_operator.notifier import FileNotifier
from src.ceo_intelligence.daily_operator.pipeline import DailyGrowthPipeline
from src.execution.approval.service import ApprovalService
from src.execution.approval.store import InMemoryApprovalStore
from src.execution.models import ExecutionMode
from src.execution.monitor import ExecutionMonitor
from src.execution.providers import (
    build_default_registry,
    build_execution_router,
)
from src.execution.recovery import build_recovery_engine
from src.execution.registry import CapabilityRegistry
from src.execution.safe_executor import build_safe_executor
from src.growth_reality.validation.auditor import RealityAuditor

DEFAULT_OUT_DIR = "outputs/operator"


@dataclass
class OperatorContext:
    """P3.1 全部依赖（测试可逐项注入 mock）。"""

    agent: DailyGrowthOperatorAgent
    auditor: RealityAuditor
    registry: CapabilityRegistry
    approval_service: ApprovalService
    safe_executor: Any            # P2.4 SafeExecutor（唯一执行出口）
    monitor: ExecutionMonitor
    recovery: Any                 # P2.6 RecoveryEngine
    game_ids: List[str] = field(default_factory=list)
    mode: ExecutionMode = ExecutionMode.DRY_RUN
    out_dir: str = DEFAULT_OUT_DIR
    company: Any = None           # 预置 CompanySnapshot（demo / 测试 / 回放）
    memory_controller: Any = None # P3.6.1 Memory Brain（读侧检索编排；None → 知识不进生产决策）
    liveops_agent: Any = None     # 跨 Agent 协同：LiveOpsAgent（None → STAGE_LIVEOPS 跳过）


def build_operator_context(
    *,
    game_ids: Optional[List[str]] = None,
    company: Any = None,
    hub: Any = None,
    agent: Optional[DailyGrowthOperatorAgent] = None,
    mode: ExecutionMode = ExecutionMode.DRY_RUN,
    data_dir: str = "data",
    out_dir: str = DEFAULT_OUT_DIR,
    feature_store: Any = None,
    memory_graph: Any = None,
    approval_store: Any = None,
    approval_queue_path: str = "data/ceo/approval_queue.jsonl",
    audit_dir: str = "data/ceo/audit",
    operator_memory: Any = None,
    report_dir: str = "reports/daily",
    registry: Optional[CapabilityRegistry] = None,
    monitor: Optional[ExecutionMonitor] = None,
    memory_controller: Any = None,
    liveops_agent: Any = None,
) -> OperatorContext:
    """工厂：全默认 = SIM/DRY_RUN 可离线跑；生产可注入 hub/真实 store。

    装配链（P2 执行链共享同一 approval store，单一授权真相源）：
        ApprovalService(store)
            → build_execution_router(authorization_gate=service.gate)
            → build_safe_executor(router)
            → build_recovery_engine(safe_executor, service.workflow)
    """
    reg = registry or build_default_registry()

    service = ApprovalService(
        store=approval_store if approval_store is not None
        else InMemoryApprovalStore()
    )
    router = build_execution_router(
        registry=reg, authorization_gate=service.gate
    )
    service.router = router
    safe_exec = build_safe_executor(router)
    mon = monitor or ExecutionMonitor()
    recovery = build_recovery_engine(
        safe_exec, approval_workflow=service.workflow
    )

    e179_agent = agent or DailyGrowthOperatorAgent(
        hub=hub,
        pipeline=DailyGrowthPipeline(
            store=feature_store,
            memory_graph=memory_graph,
            approval_queue_path=approval_queue_path,
            audit_dir=audit_dir,
        ),
        notifier=FileNotifier(report_dir=report_dir),
        operator_memory=operator_memory,
    )

    return OperatorContext(
        agent=e179_agent,
        auditor=RealityAuditor(data_dir=data_dir),
        registry=reg,
        approval_service=service,
        safe_executor=safe_exec,
        monitor=mon,
        recovery=recovery,
        game_ids=list(game_ids or []),
        mode=mode,
        out_dir=out_dir,
        company=company,
        memory_controller=memory_controller,
        liveops_agent=liveops_agent,
    )


__all__ = ["OperatorContext", "build_operator_context", "DEFAULT_OUT_DIR"]
