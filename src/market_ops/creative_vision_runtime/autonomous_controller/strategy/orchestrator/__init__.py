"""E11.9 — Autonomous Evolution Orchestrator。

将 E11 系统从"被调用式进化"升级为"自主进化循环"。

核心流程：
  OpportunityDetector → DecisionEngine → EvolutionCycleRunner → EvolutionOrchestrator

模块：
  - models:                  EvolutionCycleStatus, EvolutionOpportunity, EvolutionDecision, EvolutionCycle, EvolutionCycleResult
  - opportunity_detector:    机会检测器（回答"为什么现在需要进化？"）
  - decision_engine:         决策引擎（决定是否启动进化）
  - lifecycle_manager:       生命周期管理器（状态转换、并发控制）
  - evolution_cycle:         周期执行器（一次完整自主进化循环）
  - evolution_orchestrator:  编排器（顶层入口，run / run_loop）
"""

from .models import (
    EvolutionAction,
    EvolutionCycle,
    EvolutionCycleResult,
    EvolutionCycleStatus,
    EvolutionDecision,
    EvolutionOpportunity,
    OpportunityType,
)
from .opportunity_detector import OpportunityDetector
from .decision_engine import DecisionEngine
from .lifecycle_manager import LifecycleManager
from .evolution_cycle import EvolutionCycleRunner
from .evolution_orchestrator import EvolutionOrchestrator

__all__ = [
    # Models
    "EvolutionCycleStatus",
    "OpportunityType",
    "EvolutionAction",
    "EvolutionOpportunity",
    "EvolutionDecision",
    "EvolutionCycle",
    "EvolutionCycleResult",
    # Engines
    "OpportunityDetector",
    "DecisionEngine",
    "LifecycleManager",
    "EvolutionCycleRunner",
    "EvolutionOrchestrator",
]