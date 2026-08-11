"""P3.4.1–P3.4.4 — Portfolio Model / Ranking / Allocation-Simulation / Decision-Proposal Layer（src.operator.portfolio）。

公开 API（按阶段归属分层，import 路径即边界）：

- P3.4.1 ``models``          GamePortfolioSnapshot / PortfolioSnapshot / PortfolioSignal
                             + StrategySource / ExecutionSource / RecoverySource / LifecycleSource
- P3.4.1 ``assembler``       PortfolioAssembler + build_*_source 适配器
- P3.4.2+ ``ranking_models`` PortfolioScore / PortfolioVerdict / AllocationCandidate
                             / PortfolioRecommendation
- P3.4.2 ``ranker``          PortfolioRanker
- P3.4.3 ``allocation_models``  AllocationSimulationResult / GameAllocation / AllocationDelta
                             / ConstraintCheck / ConstraintStatus / SimulationVerdict / RiskLevel
                             / REAL_API_CALLED（结果模型，只模拟不执行）
- P3.4.3 ``constraints``     AllocationConstraints（total_budget / max_shift_ratio / min_reserve_ratio）
- P3.4.3 ``simulator``       AllocationSimulator（what-if 资源迁移模拟器）
- P3.4.4 ``proposal``        PortfolioProposal / ProposalItem / ProposalGuardVerdict
                             / PortfolioGuard（Rule0~3 内嵌闸门）/ ProposalGenerator
                             （SimulationResult → PortfolioProposal，只建议不执行）
- P3.4.5 ``optimizer_models`` OptimizationStatus / PortfolioOptimizationInput
                             / PortfolioOptimizationResult（编排 I/O 壳）
- P3.4.5 ``optimizer``        PortfolioOptimizer（编排：validate→rank→simulate→
                             propose→assemble；只编排不决策；real_api_called 恒 False）

注意：评分 / 排序 / Action 类模型**不在** ``models`` 中（P3.4.1 是纯快照层）。
本包 ``__init__`` 为兼容统一出口，新代码请按阶段从对应子模块导入。

边界：本包只消费既有 Reality / Strategy / Monitor / Recovery / Lifecycle 数据，
不重算 ROAS、不替代 E17.3 Decision、不调 Provider、不产生执行动作、不预测收入。
P3.4.3 模拟器与 P3.4.4 提案 ``real_api_called`` 恒为 ``False``。
"""

from .allocation_models import (
    AllocationDelta,
    AllocationSimulationResult,
    ConstraintCheck,
    ConstraintStatus,
    GameAllocation,
    REAL_API_CALLED,
    RiskLevel,
    SimulationVerdict,
)
from .assembler import (
    PortfolioAssembler,
    build_execution_source,
    build_lifecycle_source,
    build_recovery_source,
    build_strategy_source,
)
from .constraints import AllocationConstraints
from .models import (
    ExecutionSource,
    GamePortfolioSnapshot,
    LifecycleSource,
    PortfolioSignal,
    PortfolioSnapshot,
    RecoverySource,
    StrategySource,
)
from .proposal import (
    PortfolioGuard,
    PortfolioProposal,
    ProposalGenerator,
    ProposalGuardVerdict,
    ProposalItem,
    build_proposal_generator,
)
from .optimizer_models import (
    OptimizationStatus,
    PortfolioOptimizationInput,
    PortfolioOptimizationResult,
)
from .optimizer import PortfolioOptimizer, build_portfolio_optimizer
from .ranker import PortfolioRanker, build_portfolio_ranker
from .ranking_models import (
    AllocationCandidate,
    PortfolioRecommendation,
    PortfolioScore,
    PortfolioVerdict,
)
from .simulator import AllocationSimulator, build_allocation_simulator

__all__ = [
    # 装配
    "PortfolioAssembler",
    # 模型（输入）
    "PortfolioSnapshot",
    "GamePortfolioSnapshot",
    "PortfolioSignal",
    "StrategySource",
    "ExecutionSource",
    "RecoverySource",
    "LifecycleSource",
    # 模型（输出）
    "PortfolioScore",
    "AllocationCandidate",
    "PortfolioRecommendation",
    "PortfolioVerdict",
    # 适配器
    "build_strategy_source",
    "build_execution_source",
    "build_recovery_source",
    "build_lifecycle_source",
    # 排序
    "PortfolioRanker",
    "build_portfolio_ranker",
    # P3.4.3 模拟（只模拟不执行）
    "AllocationSimulator",
    "build_allocation_simulator",
    "AllocationConstraints",
    "AllocationSimulationResult",
    "GameAllocation",
    "AllocationDelta",
    "ConstraintCheck",
    "ConstraintStatus",
    "SimulationVerdict",
    "RiskLevel",
    "REAL_API_CALLED",
    # P3.4.4 决策建议（只建议不执行）
    "PortfolioProposal",
    "ProposalItem",
    "ProposalGuardVerdict",
    "PortfolioGuard",
    "ProposalGenerator",
    "build_proposal_generator",
    # P3.4.5 编排（只编排不决策）
    "PortfolioOptimizer",
    "build_portfolio_optimizer",
    "PortfolioOptimizationInput",
    "PortfolioOptimizationResult",
    "OptimizationStatus",
]
