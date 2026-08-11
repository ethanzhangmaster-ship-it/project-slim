"""E11.5.1 — Autonomous Creative Controller。

统一入口：串联 Vision Analysis → Decision → Mutation → Evolution 的完整链路。

一次完整循环：
  1. VisionIntelligenceEngine.analyze()       → VisionInsight
  2. VisionIntelligenceEngine.extract_winner_dna() → WinnerVisualDNA
  3. VisionDecisionEngine.decide()            → VisionDecision
  4. MutationPlanner.create_plan()            → VisionMutationPlan
  5. EvolutionIntegrationEngine.evolve_from_vision() → mutated genome

核心原则：
  - 只做编排，不实现新能力
  - 所有引擎通过依赖注入
  - 每步更新状态机和 CycleRecord
  - 错误时自动标记 FAILED
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from ..intelligence.engine import VisionIntelligenceEngine
from ..intelligence.models import VisionInsight, WinnerVisualDNA
from ..decision.decision_engine import VisionDecisionEngine
from ..decision.models import VisionDecision
from ..mutation.mutation_planner import MutationPlanner
from ..mutation.models import VisionMutationPlan
from ..evolution_bridge.integration_engine import EvolutionIntegrationEngine
from ..evolution_bridge.models import GenomeMutationTask

from .models import CycleRecord, CycleStatus, ControllerConfig
from .state_machine import ControllerStateMachine
from .cycle_manager import CycleManager
from .trigger.trigger_engine import TriggerEngine
from .trigger.models import TriggerDecision
from .feedback.feedback_engine import FeedbackEngine
from .feedback.models import EvolutionFeedback, LearningSignal, FitnessScore
from .policy.policy_engine import EvolutionPolicyEngine
from .policy.models import EvolutionPolicyDecision, PolicyResult
from .orchestrator.scheduler.scheduler import EvolutionScheduler
from .orchestrator.scheduler.models import EvolutionTask, TaskStatus
from .orchestrator.budget.budget_manager import EvolutionBudgetManager
from .orchestrator.budget.models import BudgetDecision
from .orchestrator.population.population_manager import PopulationEvolutionManager
from .orchestrator.population.models import (
    GenomeIndividual,
    GenomeStatus,
    PopulationDecision,
    PopulationSnapshot,
    PopulationSummary,
)
from .orchestrator.memory.memory_engine import EvolutionMemoryEngine
from .orchestrator.memory.models import (
    EvolutionMemoryRecord,
    MemoryOutcome,
    MemoryQuery,
    MemoryQueryResult,
    MemoryInsight,
)
from .knowledge.knowledge_engine import KnowledgeEngine
from .knowledge.models import (
    KnowledgeQuery,
    KnowledgeQueryResult as KnowledgeGraphQueryResult,
)
from .strategy.strategy_planner import EvolutionStrategyPlanner
from .strategy.models import EvolutionStrategy as StrategyOutput
from .strategy.executor.strategy_executor import StrategyExecutor
from .strategy.executor.models import ExecutionResult as StrategyExecutionResult
from .strategy.evaluation.evaluation_engine import EvolutionEvaluationEngine
from .strategy.evaluation.models import EvolutionEvaluation as StrategyEvaluation
from .strategy.evaluation.models import EvolutionRecommendation
from .strategy.orchestrator.evolution_orchestrator import EvolutionOrchestrator
from .strategy.orchestrator.models import (
    EvolutionCycle as OrchestratorCycle,
    EvolutionCycleResult as OrchestratorCycleResult,
    EvolutionCycleStatus as OrchestratorCycleStatus,
    EvolutionDecision as OrchestratorDecision,
    EvolutionOpportunity as OrchestratorOpportunity,
)

# E12 Reality（延迟导入，避免循环引用）
if TYPE_CHECKING:
    from ..reality.meta_ads_reality import MetaAdsReality
    from ..reality.adjust_reality import AdjustReality
    from ..reality.reality_data_hub import RealityDataHub
    from ..reality.feedback_bridge import RealityFeedbackBridge
    from ..reality.models import RealitySnapshot

logger = logging.getLogger(__name__)


class AutonomousCreativeController:
    """自主创意控制器。

    串联 E11.3 → E11.4.1 → E11.4.2 → E11.4.3 的完整链路。

    Attributes:
        intelligence:   VisionIntelligenceEngine（E11.3.5）
        decision:       VisionDecisionEngine（E11.4.1）
        planner:        MutationPlanner（E11.4.2）
        evolution:      EvolutionIntegrationEngine（E11.4.3）
        state_machine:  ControllerStateMachine
        cycle_manager:  CycleManager
        config:         ControllerConfig
    """

    def __init__(
        self,
        intelligence_engine: VisionIntelligenceEngine,
        decision_engine: VisionDecisionEngine | None = None,
        mutation_planner: MutationPlanner | None = None,
        evolution_engine: EvolutionIntegrationEngine | None = None,
        config: ControllerConfig | None = None,
        trigger_engine: TriggerEngine | None = None,
        feedback_engine: FeedbackEngine | None = None,
        policy_engine: EvolutionPolicyEngine | None = None,
        scheduler: EvolutionScheduler | None = None,
        budget_manager: EvolutionBudgetManager | None = None,
        population_manager: PopulationEvolutionManager | None = None,
        memory_engine: EvolutionMemoryEngine | None = None,
        knowledge_engine: KnowledgeEngine | None = None,
        strategy_planner: EvolutionStrategyPlanner | None = None,
        strategy_executor: StrategyExecutor | None = None,
        evaluation_engine: EvolutionEvaluationEngine | None = None,
        orchestrator: EvolutionOrchestrator | None = None,
        # E12 Reality（运行时延迟导入）
        meta_ads: Any = None,
        adjust: Any = None,
        reality_hub: Any = None,
        feedback_bridge: Any = None,
    ) -> None:
        self._intelligence = intelligence_engine
        self._decision = decision_engine or VisionDecisionEngine()
        self._planner = mutation_planner or MutationPlanner()
        self._evolution = evolution_engine or EvolutionIntegrationEngine()
        self._state_machine = ControllerStateMachine()
        self._cycle_manager = CycleManager()
        self._config = config or ControllerConfig()
        self._trigger = trigger_engine or TriggerEngine()
        self._feedback = feedback_engine or FeedbackEngine()
        self._policy = policy_engine or EvolutionPolicyEngine()
        self._budget = budget_manager or EvolutionBudgetManager()
        self._population = population_manager or PopulationEvolutionManager()
        self._memory = memory_engine or EvolutionMemoryEngine()
        self._knowledge = knowledge_engine or KnowledgeEngine()
        self._strategy = strategy_planner or EvolutionStrategyPlanner()
        self._scheduler = scheduler or EvolutionScheduler(
            budget_manager=self._budget,
            population_manager=self._population,
        )
        self._executor = strategy_executor or StrategyExecutor(scheduler=self._scheduler)
        self._evaluation = evaluation_engine or EvolutionEvaluationEngine()
        self._orchestrator = orchestrator or EvolutionOrchestrator(
            strategy_planner=self._strategy,
            strategy_executor=self._executor,
            evaluation_engine=self._evaluation,
            memory_engine=self._memory,
            knowledge_engine=self._knowledge,
        )

        # E12 Reality（延迟导入，避免与 autonomous_controller 循环引用）
        from ..reality.meta_ads_reality import MetaAdsReality
        from ..reality.adjust_reality import AdjustReality
        from ..reality.reality_data_hub import RealityDataHub
        from ..reality.feedback_bridge import RealityFeedbackBridge

        self._meta_ads: MetaAdsReality = meta_ads or MetaAdsReality()
        self._adjust: AdjustReality = adjust or AdjustReality()
        self._reality_hub: RealityDataHub = reality_hub or RealityDataHub(
            meta_ads=self._meta_ads,
            adjust=self._adjust,
        )
        self._feedback_bridge: RealityFeedbackBridge = (feedback_bridge or RealityFeedbackBridge())

    # ── 主入口：run_cycle ────────────────────────────────

    def run_cycle(
        self,
        asset_ids: list[str],
        genomes: dict[str, dict[str, Any]],
        winner_asset_ids: list[str] | None = None,
    ) -> CycleRecord:
        """执行一次完整进化循环。

        完整链路：
          analyze → extract_winner_dna → decide → create_plan → evolve

        Args:
            asset_ids:        素材 ID 列表
            genomes:          genome_id → genome dict 映射
            winner_asset_ids: Winner 素材 ID 列表（可选）

        Returns:
            CycleRecord（含完整链路结果）
        """
        # 1. 开始循环
        record = self._cycle_manager.start_cycle(asset_ids, winner_asset_ids)
        self._state_machine.reset()

        try:
            # 2. Analyze — 视觉分析
            self._state_machine.transition_to_analyzing()
            record.status = CycleStatus.ANALYZING
            record.insights = self._intelligence.analyze_batch(asset_ids)
            record.stats["insight_count"] = record.insight_count

            # 3. Extract Winner DNA — Winner 视觉 DNA
            if winner_asset_ids:
                record.winner_dna = self._intelligence.extract_winner_dna(
                    winner_asset_ids
                )

            # 4. Decide — 视觉决策
            self._state_machine.transition_to_deciding()
            record.status = CycleStatus.DECIDING

            for asset_id in asset_ids:
                insight = record.insights.get(asset_id)
                if insight is None:
                    logger.warning(f"No insight for asset {asset_id}, skipping")
                    continue

                decision = self._decision.decide(insight, record.winner_dna)
                record.decisions[asset_id] = decision

            record.stats["decision_count"] = record.decision_count

            # 5. Create Mutation Plans — 突变计划
            self._state_machine.transition_to_mutating()
            record.status = CycleStatus.MUTATING

            for asset_id, decision in record.decisions.items():
                genome = genomes.get(asset_id)
                if genome is None:
                    logger.warning(f"No genome for asset {asset_id}, skipping")
                    continue

                plan = self._planner.create_plan(decision, genome)
                if plan is not None:
                    record.mutation_plans[asset_id] = plan

            record.stats["plan_count"] = record.plan_count

            # 6. Evolve — 执行突变
            self._state_machine.transition_to_executing()
            record.status = CycleStatus.EXECUTING

            for asset_id, plan in record.mutation_plans.items():
                genome = genomes.get(asset_id)
                if genome is None:
                    continue

                # 转换 Plan → Task
                task = self._evolution._adapter.to_mutation_task(
                    plan,
                    genome_id=genome.get("genome_id", asset_id),
                    genome_context=genome.get("genes", {}),
                )
                record.mutation_tasks[asset_id] = task

                # 应用突变
                mutated = self._evolution.evolve_from_vision(plan, genome)
                genome_id = genome.get("genome_id", asset_id)
                record.mutated_genomes[genome_id] = mutated

            record.stats["task_count"] = record.task_count
            record.stats["genome_count"] = record.genome_count
            record.stats["total_mutations"] = record.total_mutations

            # 7. 完成
            self._state_machine.transition_to_completed()
            self._cycle_manager.complete_cycle()

            return record

        except Exception as e:
            # 失败处理
            logger.error(f"Cycle {record.cycle_id} failed: {e}")
            record.mark_failed(str(e))
            self._state_machine.transition_to_failed()
            self._cycle_manager.fail_cycle(str(e))
            return record

    # ── 多循环入口：run_cycles ───────────────────────────

    def run_cycles(
        self,
        asset_ids: list[str],
        genomes: dict[str, dict[str, Any]],
        winner_asset_ids: list[str] | None = None,
    ) -> list[CycleRecord]:
        """执行多次进化循环。

        每轮循环的输出 genome 成为下一轮的输入。

        Args:
            asset_ids:        素材 ID 列表
            genomes:          初始 genome_id → genome dict 映射
            winner_asset_ids: Winner 素材 ID 列表

        Returns:
            CycleRecord 列表
        """
        results: list[CycleRecord] = []
        current_genomes = dict(genomes)

        for i in range(self._config.max_cycles):
            record = self.run_cycle(asset_ids, current_genomes, winner_asset_ids)
            results.append(record)

            # 检查停止条件
            if record.is_failed:
                logger.warning(f"Stopping at cycle {i + 1} due to failure")
                break

            if self._config.stop_on_no_mutations and record.total_mutations == 0:
                logger.info(f"Stopping at cycle {i + 1}: no mutations generated")
                break

            if self._config.stop_on_max_cycles and i + 1 >= self._config.max_cycles:
                logger.info(f"Stopping at cycle {i + 1}: max cycles reached")
                break

            # 更新 genomes 为下一轮
            current_genomes = dict(record.mutated_genomes)

        return results

    # ── 查询 ────────────────────────────────────────────

    def get_current_state(self) -> CycleStatus:
        return self._state_machine.current_state

    def get_cycle_history(self) -> list[CycleRecord]:
        return self._cycle_manager.get_history()

    def get_active_cycle(self) -> CycleRecord | None:
        return self._cycle_manager.get_active_cycle()

    # ── E11.5.2 Trigger Integration ───────────────────

    def process_signals(
        self,
        raw_signals: list[dict[str, Any]],
        asset_ids: list[str],
        genomes: dict[str, dict[str, Any]],
        winner_asset_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """处理原始信号：检测 → 评估 → 触发进化。

        E11.5.2 完整链路：
          Raw Signals → OpportunityDetector → TriggerEngine → run_cycle()

        Args:
            raw_signals:      原始信号列表
            asset_ids:        素材 ID 列表
            genomes:          genome_id → genome dict 映射
            winner_asset_ids: Winner 素材 ID 列表

        Returns:
            {
                "decisions": list[TriggerDecision],
                "triggered": list[TriggerDecision],
                "cycles": list[CycleRecord],
            }
        """
        # 1. 检测 → 评估
        decisions = self._trigger.process(raw_signals)

        # 2. 获取触发决策
        triggered = self._trigger.get_trigger_signals(decisions)

        # 3. 对每个触发决策运行进化循环
        cycles: list[CycleRecord] = []
        for decision in triggered:
            logger.info(
                f"Triggered evolution: {decision.decision_id} "
                f"(signal={decision.signal_id}, conf={decision.confidence:.2f})"
            )
            record = self.run_cycle(asset_ids, genomes, winner_asset_ids)
            cycles.append(record)

        return {
            "decisions": decisions,
            "triggered": triggered,
            "cycles": cycles,
        }

    def evaluate_opportunities(
        self,
        signals: list[dict[str, Any]],
    ) -> list[TriggerDecision]:
        """仅评估信号，不执行进化。

        Args:
            signals: 原始信号列表

        Returns:
            TriggerDecision 列表
        """
        return self._trigger.process(signals)

    @property
    def trigger_engine(self) -> TriggerEngine:
        """获取 TriggerEngine。"""
        return self._trigger

    # ── E11.5.3 Feedback Integration ──────────────────

    def receive_feedback(
        self,
        experiment_results: list[dict[str, Any]],
    ) -> list[EvolutionFeedback]:
        """接收实验数据，生成反馈。

        完整链路：
          Experiment Result → FeedbackEngine.process() → EvolutionFeedback

        Args:
            experiment_results: 原始实验数据列表

        Returns:
            EvolutionFeedback 列表
        """
        return self._feedback.process_batch(experiment_results)

    def receive_and_evolve(
        self,
        experiment_results: list[dict[str, Any]],
        asset_ids: list[str],
        genomes: dict[str, dict[str, Any]],
        winner_asset_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """接收反馈并根据学习信号触发进化。

        完整闭环：
          Experiment → Feedback → Learning → if MUTATE → run_cycle()

        Args:
            experiment_results: 原始实验数据列表
            asset_ids:          素材 ID 列表
            genomes:            genome_id → genome dict 映射
            winner_asset_ids:   Winner 素材 ID 列表

        Returns:
            {
                "feedbacks": list[EvolutionFeedback],
                "evolution_candidates": list[EvolutionFeedback],
                "cycles": list[CycleRecord],
            }
        """
        # 1. 处理反馈
        feedbacks = self.receive_feedback(experiment_results)

        # 2. 获取需要进化的
        candidates = self._feedback.get_evolution_candidates(feedbacks)

        # 3. 对每个候选运行进化循环
        cycles: list[CycleRecord] = []
        for candidate in candidates:
            logger.info(
                f"Evolution triggered by feedback: {candidate.genome_id} "
                f"(fitness={candidate.fitness.overall_score if candidate.fitness else 'N/A'})"
            )
            record = self.run_cycle(asset_ids, genomes, winner_asset_ids)
            cycles.append(record)

        return {
            "feedbacks": feedbacks,
            "evolution_candidates": candidates,
            "cycles": cycles,
        }

    @property
    def feedback_engine(self) -> FeedbackEngine:
        """获取 FeedbackEngine。"""
        return self._feedback

    # ── E11.6 Policy Integration ────────────────────────

    def apply_learning_policy(
        self,
        learning_signals: list[LearningSignal],
        fitness_map: dict[str, FitnessScore] | None = None,
    ) -> PolicyResult:
        """将 LearningSignal 转换为 EvolutionPolicyDecision。

        完整链路：
          LearningSignal → PolicyEngine.decide_with_population() → PolicyResult

        Args:
            learning_signals: 学习信号列表
            fitness_map:      genome_id → FitnessScore 映射

        Returns:
            PolicyResult（含 decisions + population_decisions + summary）
        """
        return self._policy.decide_with_population(learning_signals, fitness_map)

    def apply_learning_policy_and_evolve(
        self,
        learning_signals: list[LearningSignal],
        fitness_map: dict[str, FitnessScore] | None = None,
        asset_ids: list[str] | None = None,
        genomes: dict[str, dict[str, Any]] | None = None,
        winner_asset_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """应用策略并根据决策触发进化。

        完整闭环：
          LearningSignal → PolicyDecision → if active → run_cycle()

        Args:
            learning_signals: 学习信号列表
            fitness_map:      genome_id → FitnessScore 映射
            asset_ids:        素材 ID 列表
            genomes:          genome_id → genome dict 映射
            winner_asset_ids: Winner 素材 ID 列表

        Returns:
            {
                "policy_result": PolicyResult,
                "cycles": list[CycleRecord],
            }
        """
        # 1. 应用策略
        policy_result = self.apply_learning_policy(learning_signals, fitness_map)

        # 2. 获取需要执行的决策
        active = self._policy.get_active_decisions(policy_result.decisions)

        # 3. 对每个活跃决策运行进化循环
        cycles: list[CycleRecord] = []
        if asset_ids and genomes:
            for decision in active:
                logger.info(
                    f"Evolution triggered by policy: {decision.genome_id} "
                    f"(action={decision.action.value}, "
                    f"strategy={decision.mutation_strategy.value})"
                )
                record = self.run_cycle(asset_ids, genomes, winner_asset_ids)
                cycles.append(record)

        return {
            "policy_result": policy_result,
            "cycles": cycles,
        }

    @property
    def policy_engine(self) -> EvolutionPolicyEngine:
        """获取 EvolutionPolicyEngine。"""
        return self._policy

    # ── E11.7.1 Scheduler Integration ──────────────────

    def schedule_evolution(
        self,
        learning_signals: list[LearningSignal],
        fitness_map: dict[str, FitnessScore] | None = None,
    ) -> dict[str, Any]:
        """将 LearningSignal 经 Policy → Task → Scheduler 调度。

        完整链路：
          LearningSignal → PolicyEngine → TaskFactory → Scheduler.submit → tick

        Args:
            learning_signals: 学习信号列表
            fitness_map:      genome_id → FitnessScore 映射

        Returns:
            {
                "policy_result": PolicyResult,
                "tasks": list[EvolutionTask],
                "scheduled_count": int,
            }
        """
        # 1. Policy 决策
        policy_result = self._policy.decide_with_population(learning_signals, fitness_map)

        # 2. 提交到 Scheduler
        active = self._policy.get_active_decisions(policy_result.decisions)
        task_ids = self._scheduler.submit_policies(active)

        # 3. 获取已提交的任务
        tasks = [self._scheduler.get_task(tid) for tid in task_ids]
        tasks = [t for t in tasks if t is not None]

        return {
            "policy_result": policy_result,
            "tasks": tasks,
            "scheduled_count": len(tasks),
        }

    def schedule_evolution_and_tick(
        self,
        learning_signals: list[LearningSignal],
        fitness_map: dict[str, FitnessScore] | None = None,
    ) -> dict[str, Any]:
        """调度进化并立即执行一次 tick。

        适用于需要同步执行结果的场景。

        Returns:
            {
                "policy_result": PolicyResult,
                "tasks": list[EvolutionTask],
                "scheduled_count": int,
                "started_count": int,
            }
        """
        result = self.schedule_evolution(learning_signals, fitness_map)
        started = self._scheduler.tick()
        result["started_count"] = len(started)
        return result

    @property
    def scheduler(self) -> EvolutionScheduler:
        """获取 EvolutionScheduler。"""
        return self._scheduler

    # ── E11.7.2 Budget Integration ─────────────────────

    def check_budget(self) -> BudgetDecision:
        """检查当前预算是否允许执行新任务。

        Returns:
            BudgetDecision
        """
        return self._budget.check()

    def can_evolve(self) -> bool:
        """是否还有预算配额可以进化。"""
        return self._budget.can_execute()

    @property
    def budget_manager(self) -> EvolutionBudgetManager:
        """获取 EvolutionBudgetManager。"""
        return self._budget

    # ── E11.7.3 Population Evolution Integration ───────

    def manage_population(
        self,
        genomes: list[dict[str, Any]],
        fitness_map: dict[str, float] | None = None,
        tick: bool = False,
    ) -> dict[str, Any]:
        """管理种群进化。

        完整闭环：
          Population → Fitness → Diversity → Select → Decision → Scheduler

        步骤：
          1. 注册基因组到 PopulationEvolutionManager
          2. 应用 fitness_map 更新适应度
          3. 执行 evolve() → PopulationDecision
          4. 将 PopulationDecision 提交到 Scheduler
          5. （可选）立即 tick 执行

        Args:
            genomes: 基因组列表，每项包含 genome_id, fitness_score, features, parent_id, metadata
            fitness_map: genome_id → fitness_score 映射（用于更新适应度）
            tick: 是否立即执行调度

        Returns:
            {
                "decision": PopulationDecision,
                "snapshot": PopulationSnapshot,
                "summary": PopulationSummary,
                "scheduler_result": dict,
                "started_tasks": list[EvolutionTask] | None,
            }
        """
        # 1. 注册种群
        self._population.create_population(genomes)

        # 2. 应用 fitness_map
        if fitness_map:
            for genome_id, score in fitness_map.items():
                ind = self._population.get_individual(genome_id)
                if ind is not None:
                    ind.fitness_score = score

        # 3. 执行进化 → PopulationDecision
        decision = self._population.evolve()

        # 4. 获取快照和汇总
        snapshot = self._population.get_population_snapshot()
        summary = self._population.get_summary()

        # 5. 将 PopulationDecision 提交到 Scheduler
        scheduler_result = self._scheduler.submit_population_decision(decision)

        # 6. 可选：立即 tick
        started_tasks: list[EvolutionTask] | None = None
        if tick:
            started_tasks = self._scheduler.tick()

        return {
            "decision": decision,
            "snapshot": snapshot,
            "summary": summary,
            "scheduler_result": scheduler_result,
            "started_tasks": started_tasks,
        }

    def manage_population_and_tick(
        self,
        genomes: list[dict[str, Any]],
        fitness_map: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """管理种群进化并立即执行调度。

        manage_population() + tick() 的便捷方法。

        Returns:
            同 manage_population()，但 started_tasks 必有值。
        """
        return self.manage_population(genomes, fitness_map, tick=True)

    def register_genome(
        self,
        genome_id: str,
        fitness_score: float = 0.0,
        features: dict[str, Any] | None = None,
        parent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> GenomeIndividual:
        """向 PopulationManager 注册单个基因组。

        Returns:
            GenomeIndividual
        """
        return self._population.register(
            genome_id=genome_id,
            fitness_score=fitness_score,
            features=features,
            parent_id=parent_id,
            metadata=metadata,
        )

    def get_population_summary(self) -> PopulationSummary:
        """获取当前种群汇总。"""
        return self._population.get_summary()

    @property
    def population_manager(self) -> PopulationEvolutionManager:
        """获取 PopulationEvolutionManager。"""
        return self._population

    # ── E11.7.4 Evolution Memory Integration ────────────

    def remember_evolution(
        self,
        genome_id: str,
        mutation_type: str,
        fitness_before: float,
        fitness_after: float,
        category: str = "",
        parent_genome_id: str | None = None,
        mutation_params: dict[str, Any] | None = None,
        creative_id: str | None = None,
        outcome: MemoryOutcome | None = None,
        success_patterns: list[str] | None = None,
        failure_patterns: list[str] | None = None,
        generation: int = 0,
        notes: str = "",
    ) -> EvolutionMemoryRecord:
        """记录一次进化经验。

        将 Feedback 数据编码为 EvolutionMemoryRecord 并存入长期记忆。

        Args:
            genome_id:         基因组 ID
            mutation_type:     突变类型 (hook, visual, gameplay, ...)
            fitness_before:    突变前适应度
            fitness_after:     突变后适应度
            category:          分类 (merge, purge, explore, ...)
            parent_genome_id:  父代 ID
            mutation_params:   突变参数
            creative_id:       创意 ID
            outcome:           结果 (None 则自动推断)
            success_patterns:  成功模式
            failure_patterns:  失败模式
            generation:        代数
            notes:             备注

        Returns:
            EvolutionMemoryRecord
        """
        return self._memory.remember(
            genome_id=genome_id,
            mutation_type=mutation_type,
            fitness_before=fitness_before,
            fitness_after=fitness_after,
            category=category,
            parent_genome_id=parent_genome_id,
            mutation_params=mutation_params,
            creative_id=creative_id,
            outcome=outcome,
            success_patterns=success_patterns,
            failure_patterns=failure_patterns,
            generation=generation,
            notes=notes,
        )

    def remember_evolution_from_feedback(
        self, feedback: dict[str, Any]
    ) -> EvolutionMemoryRecord:
        """从 feedback dict 记录进化经验。

        feedback dict 格式：
          {
            "genome_id": str,
            "mutation_type": str,
            "fitness_before": float,
            "fitness_after": float,
            ...
          }
        """
        return self._memory.remember_from_feedback(feedback)

    def recall_memory(
        self,
        mutation_type: str | None = None,
        category: str | None = None,
        patterns: list[str] | None = None,
        min_fitness_gain: float = 0.0,
        outcome: MemoryOutcome | None = None,
        max_records: int = 100,
    ) -> MemoryQueryResult:
        """检索历史进化经验。

        为 Policy 和 Population 层提供基于经验的决策支持。

        例如：
          recall_memory(mutation_type="hook", category="merge")
          → 过去 50 次类似 mutation，成功率 74%，平均提升 CTR +18%

        Args:
            mutation_type:   突变类型
            category:        分类
            patterns:        模式列表
            min_fitness_gain: 最低适应度提升
            outcome:         结果过滤
            max_records:     最大返回记录数

        Returns:
            MemoryQueryResult（含匹配记录、成功率、平均提升、推荐）
        """
        return self._memory.recall(
            mutation_type=mutation_type,
            category=category,
            patterns=patterns,
            min_fitness_gain=min_fitness_gain,
            outcome=outcome,
            max_records=max_records,
        )

    def recall_memory_by_query(self, query: MemoryQuery) -> MemoryQueryResult:
        """通过 MemoryQuery 对象检索。"""
        return self._memory.recall_by_query(query)

    def learn_from_memory(self) -> MemoryInsight:
        """从所有记忆生成全局洞察。

        Returns:
            MemoryInsight（含总体成功率、最佳/最差突变类型、推荐）
        """
        return self._memory.learn()

    @property
    def memory_engine(self) -> EvolutionMemoryEngine:
        """获取 EvolutionMemoryEngine。"""
        return self._memory

    # ── E11.7.5 Knowledge Graph Integration ──────────────

    def update_knowledge(
        self,
        memory_record: EvolutionMemoryRecord,
    ) -> dict[str, Any]:
        """将一条 MemoryRecord 摄入知识图谱。

        流程：
          Experiment Result → Feedback → Memory → Knowledge Graph

        Args:
            memory_record: EvolutionMemoryRecord（来自 E11.7.4 Memory）

        Returns:
            {"nodes_added": int, "edges_added": int}
        """
        return self._knowledge.ingest(memory_record)

    def update_knowledge_from_memory(
        self,
        records: list[EvolutionMemoryRecord],
    ) -> dict[str, Any]:
        """批量摄入 MemoryRecord。"""
        return self._knowledge.ingest_batch(records)

    def query_knowledge(
        self,
        mutation_type: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        """查询知识图谱，获取策略推荐。

        提供给 Policy 层使用的知识查询接口。

        例如：
          query_knowledge(mutation_type="hook")
          → {"action": "EXPLOIT", "success_rate": 0.72, "avg_fitness_gain": 21.0}

        Args:
            mutation_type: 突变类型
            category:      分类

        Returns:
            {
                "mutation_type": str,
                "success_rate": float | None,
                "avg_fitness_gain": float | None,
                "top_patterns": list[str],
                "avoid_patterns": list[str],
                "recommendation": str,
                "action": str,  # EXPLOIT / EXPLORE / AVOID
            }
        """
        return self._knowledge.recommend(
            mutation_type=mutation_type,
            category=category,
        )

    def query_knowledge_graph(self, query: KnowledgeQuery) -> KnowledgeGraphQueryResult:
        """通过 KnowledgeQuery 对象查询知识图谱。"""
        return self._knowledge.query(query)

    def analyze_knowledge(self, mutation_type: str) -> KnowledgeGraphQueryResult:
        """分析某 mutation 的历史表现。"""
        return self._knowledge.analyze(mutation_type)

    def recommend_from_knowledge(self) -> dict[str, Any]:
        """对所有已知 mutation 进行知识推荐。"""
        return self._knowledge.recommend_all()

    @property
    def knowledge_engine(self) -> KnowledgeEngine:
        """获取 KnowledgeEngine。"""
        return self._knowledge

    # ── E11.8.1 Strategy Planner Integration ──────────────

    def generate_strategy(
        self,
        feedback: dict[str, Any] | None = None,
        knowledge: dict[str, Any] | None = None,
        population: dict[str, Any] | None = None,
    ) -> list[StrategyOutput]:
        """生成进化策略。

        完整链路：
          Feedback + Knowledge + Population → StrategyPlanner.plan() → list[EvolutionStrategy]

        例如：
          generate_strategy(
            feedback={"metrics": {"CTR": 0.035, "ROI": 1.2}},
            knowledge={"mutation_performance": {"hook": {"success_rate": 0.8}}},
            population={"diversity_score": 0.25, "avg_fitness": 55.0},
          )
          → [EvolutionStrategy(EXPLOIT_WINNER, focus=HOOK, ...)]

        Args:
            feedback:   反馈数据
            knowledge:  知识图谱数据
            population: 种群状态

        Returns:
            EvolutionStrategy 列表（按优先级降序）
        """
        return self._strategy.plan(
            feedback=feedback,
            knowledge=knowledge,
            population=population,
        )

    def generate_strategy_single(
        self,
        feedback: dict[str, Any] | None = None,
        knowledge: dict[str, Any] | None = None,
        population: dict[str, Any] | None = None,
    ) -> StrategyOutput | None:
        """生成单一最高优先级策略。"""
        return self._strategy.plan_single(feedback, knowledge, population)

    def plan_and_schedule(
        self,
        feedback: dict[str, Any] | None = None,
        knowledge: dict[str, Any] | None = None,
        population: dict[str, Any] | None = None,
        learning_signals: list[LearningSignal] | None = None,
        fitness_map: dict[str, FitnessScore] | None = None,
    ) -> dict[str, Any]:
        """策略规划 → 策略执行 → 调度。

        完整链路：
          Strategy → Policy → Budget → Scheduler

        步骤：
          1. generate_strategy() → list[EvolutionStrategy]
          2. apply_learning_policy() → PolicyResult（如果提供 learning_signals）
          3. schedule_evolution() → 调度

        Args:
            feedback:         反馈数据
            knowledge:        知识图谱数据
            population:       种群状态
            learning_signals: 学习信号（可选，用于 Policy 层）
            fitness_map:      适应度映射（可选）

        Returns:
            {
                "strategies": list[EvolutionStrategy],
                "strategy_summary": dict,
                "policy_result": PolicyResult | None,
                "scheduler_result": dict | None,
            }
        """
        result: dict[str, Any] = {}

        # 1. 生成策略
        strategies = self.generate_strategy(feedback, knowledge, population)
        result["strategies"] = strategies
        result["strategy_summary"] = self._strategy.summarize(strategies)

        # 2. 应用 Policy（如果提供了 learning_signals）
        if learning_signals:
            policy_result = self.apply_learning_policy(learning_signals, fitness_map)
            result["policy_result"] = policy_result

            # 3. 调度
            scheduler_result = self.schedule_evolution(learning_signals, fitness_map)
            result["scheduler_result"] = scheduler_result
        else:
            result["policy_result"] = None
            result["scheduler_result"] = None

        return result

    @property
    def strategy_planner(self) -> EvolutionStrategyPlanner:
        """获取 EvolutionStrategyPlanner。"""
        return self._strategy

    # ── E11.8.2 Strategy Executor Integration ──────────────

    def execute_strategy(
        self,
        strategy: StrategyOutput,
    ) -> StrategyExecutionResult:
        """执行一个 EvolutionStrategy。

        完整链路：
          Strategy → ExecutionPlanner → MutationPlan → Tasks → Scheduler

        流程：
          1. ExecutionPlanner.create_plan(strategy) → MutationPlan
          2. 为每个 mutation 创建 EvolutionTask
          3. submit 到 Scheduler
          4. 返回 ExecutionResult

        Args:
            strategy: EvolutionStrategy（来自 generate_strategy()）

        Returns:
            StrategyExecutionResult（含 tasks_created, task_ids, success）
        """
        return self._executor.execute(strategy)

    def execute_strategies(
        self,
        strategies: list[StrategyOutput],
    ) -> list[StrategyExecutionResult]:
        """批量执行策略。"""
        return self._executor.execute_batch(strategies)

    def plan_and_execute(
        self,
        feedback: dict[str, Any] | None = None,
        knowledge: dict[str, Any] | None = None,
        population: dict[str, Any] | None = None,
        learning_signals: list[LearningSignal] | None = None,
        fitness_map: dict[str, FitnessScore] | None = None,
        tick: bool = False,
    ) -> dict[str, Any]:
        """策略规划 → 执行 → 调度，完整闭环。

        完整链路：
          StrategyPlanner → StrategyExecutor → Budget → Scheduler → Evolution

        步骤：
          1. generate_strategy() → list[EvolutionStrategy]
          2. execute_strategies() → list[ExecutionResult]
          3. create PolicyResult from strategies（如果提供了 learning_signals）
          4. 可选 tick 执行

        Args:
            feedback:         反馈数据
            knowledge:        知识图谱数据
            population:       种群状态
            learning_signals: 学习信号（可选）
            fitness_map:      适应度映射（可选）
            tick:             是否立即执行调度

        Returns:
            {
                "strategies": list[EvolutionStrategy],
                "strategy_summary": dict,
                "execution_results": list[ExecutionResult],
                "total_tasks": int,
                "policy_result": PolicyResult | None,
                "scheduler_result": dict | None,
                "started_tasks": list | None,
            }
        """
        result: dict[str, Any] = {}

        # 1. 生成策略
        strategies = self.generate_strategy(feedback, knowledge, population)
        result["strategies"] = strategies
        result["strategy_summary"] = self._strategy.summarize(strategies)

        # 2. 执行策略
        executions = self.execute_strategies(strategies)
        result["execution_results"] = executions
        result["total_tasks"] = sum(e.tasks_created for e in executions)

        # 3. 应用 Policy（如果提供了 learning_signals）
        if learning_signals:
            policy_result = self.apply_learning_policy(learning_signals, fitness_map)
            result["policy_result"] = policy_result

            scheduler_result = self.schedule_evolution(learning_signals, fitness_map)
            result["scheduler_result"] = scheduler_result
        else:
            result["policy_result"] = None
            result["scheduler_result"] = None

        # 4. 可选 tick
        if tick:
            result["started_tasks"] = self._scheduler.tick()
        else:
            result["started_tasks"] = None

        return result

    @property
    def strategy_executor(self) -> StrategyExecutor:
        """获取 StrategyExecutor。"""
        return self._executor

    # ── E11.8.3 Evaluation Engine Integration ──────────────

    def evaluate_evolution(
        self,
        before: dict[str, float],
        after: dict[str, float],
        strategy: StrategyOutput | None = None,
        consecutive_failures: int = 0,
    ) -> StrategyEvaluation:
        """评估进化结果。

        完整链路：
          Before/After Metrics → MetricEvaluator → ImprovementDetector → StrategyJudge → EvolutionEvaluation

        流程：
          1. 指标对比（before vs after）
          2. 检测改善（SUCCESS / PARTIAL / FAILED / INCONCLUSIVE）
          3. 策略评判（SCALE / KEEP / ITERATE / ROLLBACK / RETIRE）
          4. 返回 EvolutionEvaluation

        Args:
            before:               进化前指标 {"ROI": 0.45, "CTR": 0.03, ...}
            after:                进化后指标 {"ROI": 0.62, "CTR": 0.035, ...}
            strategy:             原始策略（可选）
            consecutive_failures: 连续失败次数

        Returns:
            StrategyEvaluation
        """
        return self._evaluation.evaluate(
            before=before,
            after=after,
            strategy=strategy,
            consecutive_failures=consecutive_failures,
        )

    def evaluate_and_learn(
        self,
        before: dict[str, float],
        after: dict[str, float],
        strategy: StrategyOutput | None = None,
        consecutive_failures: int = 0,
    ) -> dict[str, Any]:
        """评估进化 → 写入记忆 → 更新知识图谱 → 生成新策略。

        完整闭环：
          Evaluation → Memory → Knowledge → Strategy

        步骤：
          1. evaluate_evolution() → StrategyEvaluation
          2. 根据结果写入 EvolutionMemory
          3. 更新 Knowledge Graph
          4. 如有必要，生成新策略

        Args:
            before:               进化前指标
            after:                进化后指标
            strategy:             原始策略
            consecutive_failures: 连续失败次数

        Returns:
            {
                "evaluation": StrategyEvaluation,
                "memory_record": EvolutionMemoryRecord | None,
                "new_strategies": list[StrategyOutput] | None,
            }
        """
        result: dict[str, Any] = {}

        # 1. 评估
        evaluation = self.evaluate_evolution(
            before, after, strategy, consecutive_failures
        )
        result["evaluation"] = evaluation

        # 2. 写入记忆
        memory_record = self._record_evaluation_to_memory(evaluation, strategy)
        result["memory_record"] = memory_record

        # 3. 更新知识图谱
        if memory_record:
            self.update_knowledge_from_memory([memory_record])

        # 4. 如果失败或部分成功，生成修正策略
        if evaluation.recommendation in (
            EvolutionRecommendation.ITERATE,
            EvolutionRecommendation.ROLLBACK,
        ):
            # 需要修正时生成新策略
            new_strategies = self.generate_strategy(
                feedback={
                    "metrics": after,
                    "failure_count": consecutive_failures + 1 if evaluation.is_failed else 0,
                    "success_count": 1 if evaluation.is_success else 0,
                }
            )
            result["new_strategies"] = new_strategies
        else:
            result["new_strategies"] = None

        return result

    def _record_evaluation_to_memory(
        self,
        evaluation: StrategyEvaluation,
        strategy: StrategyOutput | None,
    ) -> Any:
        """将评估结果写入 EvolutionMemory。"""
        # 从评估中提取记忆数据
        fitness_before = 0.0
        fitness_after = 0.0

        for imp in evaluation.improvements:
            if imp.metric == "ROI":
                fitness_before = imp.before * 50
                fitness_after = imp.after * 50
                break

        if fitness_before == 0.0 and fitness_after == 0.0:
            fitness_before = 50.0
            fitness_after = 50.0 + evaluation.score

        return self.remember_evolution(
            genome_id=strategy.strategy_id if strategy else "unknown",
            mutation_type=strategy.strategy_type.value if strategy else "unknown",
            fitness_before=fitness_before,
            fitness_after=fitness_after,
            success_patterns=[],  # 由 evaluator 填充
            failure_patterns=[],  # 由 evaluator 填充
        )

    @property
    def evaluation_engine(self) -> EvolutionEvaluationEngine:
        """获取 EvolutionEvaluationEngine。"""
        return self._evaluation

    # ── E11.9 Autonomous Evolution Orchestrator ────────────

    def run_evolution_cycle(
        self,
        market_signal: dict[str, Any] | None = None,
        knowledge: dict[str, Any] | None = None,
        population: dict[str, Any] | None = None,
        budget: dict[str, Any] | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """执行一次自主进化周期。

        完整闭环：
          OpportunityDetector → DecisionEngine → EvolutionCycleRunner
          → StrategyPlanner → StrategyExecutor → EvaluationEngine
          → Memory → Knowledge → Next Cycle

        这是 E11 系统从"被调用式进化"升级为"自主进化循环"的核心入口。

        流程：
          1. 检测进化机会（OpportunityDetector）
          2. 决策是否启动（DecisionEngine）
          3. 生成策略（StrategyPlanner, E11.8.1）
          4. 执行策略（StrategyExecutor, E11.8.2）
          5. 评估结果（EvaluationEngine, E11.8.3）
          6. 写入记忆（MemoryEngine, E11.7.4）
          7. 更新知识图谱（KnowledgeEngine, E11.7.5）

        Args:
            market_signal: 市场信号（含 metrics, trends）
            knowledge:     知识图谱数据
            population:    种群状态
            budget:        预算状态
            force:         强制运行（跳过决策）

        Returns:
            {
                "cycle": {
                    "id": str,
                    "status": str,
                },
                "decision": {
                    "action": str,
                    "confidence": float,
                },
                "learning": {
                    "new_patterns": int,
                },
                "success": bool,
                "summary": str,
            }
        """
        result = self._orchestrator.run(
            market_signal=market_signal,
            knowledge=knowledge,
            population=population,
            budget=budget,
            force=force,
        )

        # 构建友好返回格式
        cycle_dict = result.cycle.to_dict() if result.cycle else None
        decision_dict = (
            result.cycle.decision.to_dict()
            if result.cycle and result.cycle.decision
            else None
        )

        return {
            "cycle": cycle_dict,
            "decision": decision_dict,
            "learning": {
                "new_patterns": len(result.strategies),
            },
            "success": result.success,
            "summary": result.summary,
        }

    def run_evolution_loop(
        self,
        market_signal: dict[str, Any] | None = None,
        knowledge: dict[str, Any] | None = None,
        population: dict[str, Any] | None = None,
        budget: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """循环执行自主进化，直到无机会或达到上限。

        每次循环后重新检测机会，自动决定是否继续。

        Returns:
            结果列表
        """
        results = self._orchestrator.run_loop(
            market_signal=market_signal,
            knowledge=knowledge,
            population=population,
            budget=budget,
        )

        return [
            {
                "cycle": r.cycle.to_dict() if r.cycle else None,
                "success": r.success,
                "summary": r.summary,
            }
            for r in results
        ]

    def detect_evolution_opportunity(
        self,
        market_signal: dict[str, Any] | None = None,
        knowledge: dict[str, Any] | None = None,
        population: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """检测进化机会（不执行进化）。

        Args:
            market_signal: 市场信号
            knowledge:     知识图谱数据
            population:    种群状态

        Returns:
            机会字典列表
        """
        opportunities = self._orchestrator._detector.detect(
            market_signal=market_signal,
            knowledge=knowledge,
            population=population,
        )
        return [opp.to_dict() for opp in opportunities]

    def get_orchestrator_status(self) -> dict[str, Any]:
        """获取编排器状态。"""
        return self._orchestrator.get_status()

    @property
    def evolution_orchestrator(self) -> EvolutionOrchestrator:
        """获取 EvolutionOrchestrator。"""
        return self._orchestrator

    # ── E12 Reality Integration Layer ────────────────────

    def poll_reality(
        self,
        campaign_ids: list[str],
        lookback_days: int = 7,
        creative_dna_map: dict[str, dict] | None = None,
    ) -> RealitySnapshot:
        """拉取真实世界数据并生成快照。

        合并 Meta Ads + Adjust 数据，生成 E11 Evolution 可消费
        的统一 RealitySnapshot。

        Args:
            campaign_ids:       Campaign ID 列表
            lookback_days:      回溯天数
            creative_dna_map:   Creative ID → DNA 映射

        Returns:
            RealitySnapshot
        """
        return self._reality_hub.poll(
            campaign_ids=campaign_ids,
            lookback_days=lookback_days,
            creative_dna_map=creative_dna_map,
        )

    def reality_to_feedback(
        self,
        snapshot: RealitySnapshot,
    ) -> list[dict[str, Any]]:
        """将 RealitySnapshot 转换为 EvolutionFeedback。

        Args:
            snapshot: RealitySnapshot

        Returns:
            EvolutionFeedback 字典列表
        """
        feedbacks = self._feedback_bridge.generate_feedback(snapshot)
        return [f.to_dict() for f in feedbacks]

    def reality_to_market_signal(
        self,
        snapshot: RealitySnapshot,
    ) -> dict[str, Any]:
        """将 RealitySnapshot 转换为 E11.9 市场信号。

        Args:
            snapshot: RealitySnapshot

        Returns:
            market_signal dict
        """
        return self._feedback_bridge.generate_market_signal(snapshot)

    def poll_and_evolve(
        self,
        campaign_ids: list[str],
        lookback_days: int = 7,
        creative_dna_map: dict[str, dict] | None = None,
    ) -> dict[str, Any]:
        """完整闭环：拉取现实数据 → 检测机会 → 自主进化。

        这是 E12 + E11.9 的完整集成流程：
          1. poll_reality() → RealitySnapshot
          2. reality_to_market_signal() → market_signal
          3. run_evolution_cycle(market_signal) → 自主进化

        Args:
            campaign_ids:     Campaign ID 列表
            lookback_days:    回溯天数
            creative_dna_map: Creative ID → DNA 映射

        Returns:
            {
                "snapshot": RealitySnapshot dict,
                "evolution": run_evolution_cycle() result,
                "feedbacks": EvolutionFeedback dict list,
            }
        """
        # 1. 拉取现实数据
        snapshot = self.poll_reality(
            campaign_ids=campaign_ids,
            lookback_days=lookback_days,
            creative_dna_map=creative_dna_map,
        )

        # 2. 生成市场信号
        market_signal = self.reality_to_market_signal(snapshot)

        # 3. 检测机会 + 自主进化
        evolution_result = self.run_evolution_cycle(
            market_signal=market_signal,
        )

        # 4. 生成反馈
        feedbacks = self.reality_to_feedback(snapshot)

        return {
            "snapshot": snapshot.to_dict(),
            "evolution": evolution_result,
            "feedbacks": feedbacks,
        }

    @property
    def reality_hub(self) -> RealityDataHub:
        """获取 RealityDataHub。"""
        return self._reality_hub

    @property
    def feedback_bridge(self) -> RealityFeedbackBridge:
        """获取 RealityFeedbackBridge。"""
        return self._feedback_bridge

    @property
    def meta_ads(self) -> MetaAdsReality:
        """获取 MetaAdsReality。"""
        return self._meta_ads

    @property
    def adjust(self) -> AdjustReality:
        """获取 AdjustReality。"""
        return self._adjust

    # ── Stats ──────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        return {
            "state_machine": self._state_machine.get_stats(),
            "cycle_manager": self._cycle_manager.get_stats(),
            "config": self._config.to_dict(),
        }

    def __repr__(self) -> str:
        return (
            f"AutonomousCreativeController("
            f"state={self._state_machine.current_state.value}, "
            f"cycles={self._cycle_manager.total_cycles})"
        )