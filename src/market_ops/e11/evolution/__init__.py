"""E11.3 Evolution — 创意进化模块。

E11.3.1 — Fitness & Evaluation Foundation
  - FitnessDirection: MAXIMIZE / MINIMIZE
  - FitnessMetric: 单个评估指标
  - FitnessScore: 综合评分
  - FitnessSnapshot: 时间快照
  - EvaluationResult: 评估输出

E11.3.2 — Population Manager
  - PopulationStatus: 种群状态
  - GenomePopulation: 进化种群
  - PopulationMember: 种群成员
  - PopulationManager: 种群管理器

E11.3.3 — Selection Layer
  - SelectionMode: ELITE / THRESHOLD / DIVERSITY
  - SelectionPolicy: 选择策略
  - Survivor / SelectionResult: 选择结果
  - EliteSelection / ThresholdSelection / DiversitySelection
  - SelectionManager: 选择管理器

E11.4.1 — Evolution Orchestrator
  - EvolutionStatus: 进化任务状态
  - EvolutionConfig: 进化配置
  - EvolutionRun: 进化执行实例
  - GenerationResult: 单代结果
  - EvolutionResult: 最终输出
  - EvolutionOrchestrator: 进化调度器

E11.4.2 — Multi Generation
  - GenerationStatus: 单代状态
  - GenerationRecord: 单代记录
  - EvolutionHistory: 进化历史
  - GenerationManager: 代数管理器
  - EvolutionHistoryRecorder: 历史记录器
  - ConvergenceConfig: 收敛检测配置
  - ConvergenceDetector: 收敛检测器
  - CheckpointRecord: 断点记录
  - CheckpointManager: 断点管理器
"""

from .fitness_schema import (
    FitnessDirection,
    FitnessMetric,
    FitnessScore,
    FitnessSnapshot,
    EvaluationResult,
)
from .population_schema import (
    PopulationStatus,
    GenomePopulation,
    PopulationMember,
)
from .population_manager import PopulationManager
from .selection_schema import (
    SelectionMode,
    SelectionPolicy,
    Survivor,
    SelectionResult,
)
from .selection_policy import (
    EliteSelection,
    ThresholdSelection,
    DiversitySelection,
)
from .selection_manager import SelectionManager
from .orchestrator_schema import (
    EvolutionStatus,
    EvolutionConfig,
    EvolutionRun,
    GenerationResult,
    EvolutionResult,
)
from .evolution_orchestrator import EvolutionOrchestrator
from .generation_schema import (
    GenerationStatus,
    GenerationRecord,
    EvolutionHistory,
)
from .generation_manager import GenerationManager
from .evolution_history import EvolutionHistoryRecorder
from .convergence_detector import (
    ConvergenceConfig,
    ConvergenceDetector,
)
from .checkpoint import (
    CheckpointRecord,
    CheckpointManager,
)

__all__ = [
    # Fitness
    "FitnessDirection",
    "FitnessMetric",
    "FitnessScore",
    "FitnessSnapshot",
    "EvaluationResult",
    # Population
    "PopulationStatus",
    "GenomePopulation",
    "PopulationMember",
    "PopulationManager",
    # Selection
    "SelectionMode",
    "SelectionPolicy",
    "Survivor",
    "SelectionResult",
    "EliteSelection",
    "ThresholdSelection",
    "DiversitySelection",
    "SelectionManager",
    # Orchestrator
    "EvolutionStatus",
    "EvolutionConfig",
    "EvolutionRun",
    "GenerationResult",
    "EvolutionResult",
    "EvolutionOrchestrator",
    # Generation
    "GenerationStatus",
    "GenerationRecord",
    "EvolutionHistory",
    "GenerationManager",
    "EvolutionHistoryRecorder",
    # Convergence
    "ConvergenceConfig",
    "ConvergenceDetector",
    # Checkpoint
    "CheckpointRecord",
    "CheckpointManager",
]