"""E11.4.2 Evolution Orchestrator — 多代进化调度器。

将 E11 已有模块串联为多代 Evolution Pipeline。

多代 Cycle 流程：
  1. 创建 EvolutionRun
  2. 循环 max_generations 代：
     a. Mutation: 为种群中每个 Genome 产生子代（可接收 winner_genes 指导变异）
     b. Fitness: 评估子代评分
     c. Population: 子代加入种群
     d. Selection: 精英选择
     e. 记录 GenerationResult
     f. 检测收敛 → 提前停止
  3. 输出 EvolutionResult

变异策略（E11.6.4 集成）：
  - 默认：轮转 5 个基因槽位（hook/visual/reward/emotion/gameplay）
  - 有 winner_genes 时：高 impact 基因优先被选中
  - 高评分成员 → ENHANCE（增强现有基因）
  - 低评分成员 → REPLACE（替换基因值）

停止条件：
  - generation >= max_generations
  - convergence == True

数据流：
  GenomePopulation + EvolutionConfig + winner_genes
      → EvolutionOrchestrator.run()
      → EvolutionResult

Usage:
    orchestrator = EvolutionOrchestrator()
    result = orchestrator.run(population, config)
    # 带 winner genes 指导：
    result = orchestrator.run(population, config, winner_genes=["hook:rescue", "reward:dragon"])
"""

from __future__ import annotations

from ..genome.schema import CreativeGenome, GENE_SLOTS
from ..mutation.mutation_operator import MutationOperator
from ..mutation.mutation_schema import MutationType, MutationRule
from ..mutation.mutation_strategy import StrategyContext
from ..mutation.strategy_selector import StrategySelector
from .fitness_schema import (
    FitnessDirection,
    FitnessMetric,
    FitnessScore,
)
from .population_schema import GenomePopulation, PopulationMember
from .population_manager import PopulationManager
from .selection_schema import SelectionMode, SelectionPolicy
from .selection_manager import SelectionManager
from .orchestrator_schema import (
    EvolutionStatus,
    EvolutionConfig,
    EvolutionRun,
    GenerationResult,
    EvolutionResult,
)
from .generation_schema import (
    GenerationStatus,
    GenerationRecord,
    EvolutionHistory,
)
from .generation_manager import GenerationManager
from .evolution_history import EvolutionHistoryRecorder
from .convergence_detector import ConvergenceDetector, ConvergenceConfig
from .checkpoint import CheckpointManager


class EvolutionOrchestrator:
    """进化调度器。

    将 Genome → Mutation → Fitness → Population → Selection
    串联为多代 Evolution Cycle。

    Usage:
        orchestrator = EvolutionOrchestrator()
        result = orchestrator.run(population, config)
    """

    def __init__(self) -> None:
        self._mutation_operator = MutationOperator()
        self._strategy_selector = StrategySelector()
        self._population_manager = PopulationManager()
        self._selection_manager = SelectionManager()
        self._generation_manager = GenerationManager()
        self._convergence_detector = ConvergenceDetector()
        self._checkpoint_manager = CheckpointManager()

    # ── 主入口 ────────────────────────────────────────

    def run(
        self,
        population: GenomePopulation,
        config: EvolutionConfig | None = None,
        convergence_config: ConvergenceConfig | None = None,
        checkpoint_interval: int = 0,
        winner_genes: list[str] | None = None,
    ) -> EvolutionResult:
        """执行多代进化 Cycle。

        Args:
            population: 初始种群（含 Genome 成员）
            config: 进化配置（默认使用 EvolutionConfig()）
            convergence_config: 收敛检测配置（默认使用 ConvergenceConfig()）
            checkpoint_interval: 断点保存间隔代数（0 = 不保存）
            winner_genes: E11.6.3 的 Winner DNA 列表 (e.g. ["hook:rescue", "reward:dragon"])
                          用于指导变异策略，高 impact 基因优先被选中

        Returns:
            EvolutionResult
        """
        config = config or EvolutionConfig()
        convergence_config = convergence_config or ConvergenceConfig()
        self._convergence_detector = ConvergenceDetector(convergence_config)

        # 创建运行实例
        run = EvolutionRun(
            population_id=population.population_id,
            generation=population.generation,
            config=config,
        )
        run.start()

        # 初始化历史记录器
        history_recorder = EvolutionHistoryRecorder(run_id=run.run_id)

        try:
            total_children = 0
            generation_results: list[GenerationResult] = []

            for gen_num in range(1, config.max_generations + 1):
                # 创建代记录
                gen_record = self._generation_manager.create_generation(
                    population, generation=gen_num,
                )
                gen_record.start()

                try:
                    # 执行一代
                    gen_result = self._execute_generation(
                        population, config, gen_num, winner_genes,
                    )
                    total_children += gen_result.children_created

                    # 完成代记录
                    self._generation_manager.complete_generation(
                        gen_record, population,
                    )
                    gen_record.mutation_count = gen_result.children_created
                    generation_results.append(gen_result)

                except Exception as gen_error:
                    gen_record.fail()
                    gen_result = GenerationResult(
                        generation=gen_num,
                        children_created=0,
                        survivors=population.size,
                    )
                    generation_results.append(gen_result)

                # 记录到历史
                history_recorder.record(gen_record)

                # 保存断点
                if checkpoint_interval > 0 and gen_num % checkpoint_interval == 0:
                    self._checkpoint_manager.save(
                        run, population,
                        history_recorder.history,
                        config,
                    )

                # 收敛检测
                if gen_num >= 2:
                    conv_result = self._convergence_detector.detect(
                        history_recorder.history,
                    )
                    if conv_result["converged"]:
                        break

                # 更新 run 的 generation
                run.generation = gen_num

            # 选择最优
            self._apply_selection(population, config)

            run.complete()

            best = population.best_member
            return EvolutionResult(
                run_id=run.run_id,
                best_genome_id=best.genome_id if best else "",
                best_score=best.score if best else 0.0,
                generations=generation_results,
                success=True,
                total_generations=len(generation_results),
                total_children=total_children,
            )

        except Exception as e:
            run.fail()
            return EvolutionResult(
                run_id=run.run_id,
                success=False,
                total_generations=0,
                total_children=0,
                error_message=str(e),
            )

    # ── 单代执行 ──────────────────────────────────────

    def _execute_generation(
        self,
        population: GenomePopulation,
        config: EvolutionConfig,
        generation: int,
        winner_genes: list[str] | None = None,
    ) -> GenerationResult:
        """执行单代进化 Cycle。

        流程：
          1. 对每个成员执行 Mutation → 产生子代
          2. 评估子代 Fitness
          3. 子代加入种群
        """
        children_created = 0
        original_members = list(population.members)

        # 计算基因轮转索引（基于generation）
        gene_index = (generation - 1) % len(GENE_SLOTS)

        for member in original_members:
            if children_created >= config.population_size:
                break

            # 创建子代
            child = self._mutate_member(
                member, population, winner_genes, gene_index, generation,
            )
            if child is None:
                continue

            # 评估
            fitness = self._evaluate_fitness(child)

            # 加入种群
            self._population_manager.add_genome(
                population, child.genome_id, fitness=fitness,
            )
            children_created += 1

        # 排名
        self._population_manager.rank_members(population)

        best = population.best_member
        return GenerationResult(
            generation=generation,
            children_created=children_created,
            survivors=population.size,
            best_score=best.score if best else 0.0,
            avg_score=population.avg_score,
            best_genome_id=best.genome_id if best else "",
        )

    def _mutate_member(
        self,
        member: PopulationMember,
        population: GenomePopulation,
        winner_genes: list[str] | None = None,
        gene_index: int = 0,
        generation: int = 1,
    ) -> CreativeGenome | None:
        """对种群成员执行变异，产生子代。

        策略：
          - 有 winner_genes 时，优先选高 impact 基因
          - 无 winner_genes 时，按 gene_index 轮转 5 个基因槽位
          - 高评分成员（score >= 0.7）→ ENHANCE（增强）
          - 低评分成员（score < 0.7）→ REPLACE（替换）
        """
        parent = CreativeGenome(
            genome_id=member.genome_id,
            generation=0,
            genes={
                slot: {"type": "default", "strength": member.score}
                for slot in GENE_SLOTS
            },
            fitness={"ctr": member.score},
        )

        # 选择目标基因
        gene_name = self._select_mutation_target(winner_genes, gene_index)
        # 选择变异类型
        mutation_type = self._select_mutation_type(member.score)

        try:
            if mutation_type == MutationType.ENHANCE:
                child, _ = self._mutation_operator.enhance(
                    parent,
                    gene_name=gene_name,
                    boost=0.1,
                )
            elif mutation_type == MutationType.COMBINE and winner_genes:
                child, _ = self._mutation_operator.combine(
                    parent,
                    source_genome=parent,
                    target_genes=[gene_name],
                )
            else:
                # REPLACE: 用 winner gene 值或默认值
                new_value = self._get_mutation_value(gene_name, winner_genes)
                child, _ = self._mutation_operator.replace(
                    parent,
                    gene_name=gene_name,
                    new_value=new_value,
                    confidence=0.8,
                )
            return child
        except Exception:
            return None

    def _select_mutation_target(
        self,
        winner_genes: list[str] | None,
        gene_index: int,
    ) -> str:
        """选择变异目标基因。

        规则：
          1. 有 winner_genes 时，从中随机选一个基因名
          2. 无 winner_genes 时，按 gene_index 轮转
        """
        if winner_genes:
            gene_names = list({g.split(":")[0] for g in winner_genes if ":" in g})
            if gene_names:
                return gene_names[gene_index % len(gene_names)]
        # 默认轮转
        keys = list(GENE_SLOTS.keys())
        return keys[gene_index % len(keys)]

    def _select_mutation_type(self, score: float) -> MutationType:
        """根据评分选择变异类型。

        - score >= 0.7: ENHANCE（增强好基因，不破坏）
        - score < 0.7:  REPLACE（替换差基因，探索新方向）
        """
        return MutationType.ENHANCE if score >= 0.7 else MutationType.REPLACE

    @staticmethod
    def _get_mutation_value(
        gene_name: str,
        winner_genes: list[str] | None,
    ) -> dict[str, Any]:
        """获取变异值。

        如果有 winner_genes，使用 winner gene 的值；
        否则使用默认值。
        """
        if winner_genes:
            for wg in winner_genes:
                parts = wg.split(":", 1)
                if len(parts) == 2 and parts[0] == gene_name:
                    return {"type": parts[1], "strength": 0.8}
        return {"type": "evolved", "strength": 0.5}

    def _evaluate_fitness(self, genome: CreativeGenome) -> FitnessScore:
        """评估 Genome 的 Fitness。

        使用 genome 中存储的 fitness 数据构建 FitnessScore。
        如果 genome.fitness 为空，使用默认评分。
        """
        metrics: list[FitnessMetric] = []

        if genome.fitness:
            if "roas_d7" in genome.fitness:
                metrics.append(FitnessMetric(
                    name="roas_d7",
                    value=genome.fitness["roas_d7"],
                    weight=0.5,
                    direction=FitnessDirection.MAXIMIZE,
                ))
            if "ctr" in genome.fitness:
                metrics.append(FitnessMetric(
                    name="ctr",
                    value=genome.fitness["ctr"],
                    weight=0.3,
                    direction=FitnessDirection.MAXIMIZE,
                ))
            if "cpi" in genome.fitness:
                metrics.append(FitnessMetric(
                    name="cpi",
                    value=genome.fitness["cpi"],
                    weight=0.2,
                    direction=FitnessDirection.MINIMIZE,
                ))

        # 如果没有明确指标，从基因中提取评分
        if not metrics:
            gene_values = []
            for gene_data in genome.genes.values():
                for v in gene_data.values():
                    if isinstance(v, (int, float)):
                        gene_values.append(v)

            if gene_values:
                avg_strength = sum(gene_values) / len(gene_values)
                metrics.append(FitnessMetric(
                    name="gene_strength",
                    value=avg_strength,
                    weight=1.0,
                    direction=FitnessDirection.MAXIMIZE,
                ))

        return FitnessScore(
            genome_id=genome.genome_id,
            metrics=metrics,
        )

    def _apply_selection(
        self,
        population: GenomePopulation,
        config: EvolutionConfig,
    ) -> None:
        """对种群执行选择，保留精英。"""
        self._population_manager.mark_elite(
            population,
            top_k=config.elite_count,
            min_score=config.min_fitness_threshold,
        )