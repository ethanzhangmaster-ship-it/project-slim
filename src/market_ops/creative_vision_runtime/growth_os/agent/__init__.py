"""E12.7.2 — Autonomous Growth Agent。

自主增长 Agent —— 可以自主感知、分析、推理、提出增长动作的 AI Growth Operator。

模块:
  - models:                GrowthObservation, RootCause, GrowthHypothesis, AgentDecision
  - perception:            感知层（多源信号融合）
  - reasoning_engine:      推理引擎（根因诊断）
  - hypothesis_generator:  假设生成器（可验证假设）
  - decision_adapter:      决策适配器（AI 推理 → 可执行决策）
  - agent_controller:      Agent 控制器（全流程编排）
"""

from .models import (
    AgentDecision,
    CreativeState,
    GrowthHypothesis,
    GrowthObservation,
    HypothesisStatus,
    MarketState,
    ObservationSeverity,
    ProductMetrics,
    RootCause,
)
from .perception import PerceptionLayer
from .reasoning_engine import ReasoningEngine
from .hypothesis_generator import HypothesisGenerator
from .decision_adapter import DecisionAdapter
from .agent_controller import AutonomousGrowthAgent

__all__ = [
    # Enums
    "ObservationSeverity",
    "HypothesisStatus",
    # Models
    "ProductMetrics",
    "CreativeState",
    "MarketState",
    "GrowthObservation",
    "RootCause",
    "GrowthHypothesis",
    "AgentDecision",
    # Layers
    "PerceptionLayer",
    "ReasoningEngine",
    "HypothesisGenerator",
    "DecisionAdapter",
    "AutonomousGrowthAgent",
]