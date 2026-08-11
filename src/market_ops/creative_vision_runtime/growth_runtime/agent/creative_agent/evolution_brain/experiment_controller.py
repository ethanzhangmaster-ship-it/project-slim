"""E14.6.2 Evolution Experiment Controller — 进化实验控制器.

职责:
  1. 将 E14.6.1 生成的 CreativeGenome 组织为可控实验 (Control + Variant)
  2. 管理实验生命周期 (DRAFT → RUNNING → COMPLETED → FEEDBACK)
  3. 连接广告平台 API (Meta Ads / Google Ads) 部署实验
  4. 收集实验结果 (CTR, CVR, ROAS, D1, D7, D30, LTV) 并计算适应度评分
  5. 将结果回流到 Evolution Memory (E14.5.6) 形成闭环

核心概念:
  - Experiment: 一个完整实验 (包含 Control + Variant Groups)
  - ExperimentGroup: 实验组 (Control / Variant, 包含多个 Genome)
  - ExperimentResult: 单个 Genome 的实验结果
  - ExperimentReport: 实验汇总报告 (Winner 判定, 推荐)

数据流:
  E14.6.1 ExecutionResult (genome_ids)
       ↓
  ExperimentController.create_experiment()
       ↓
  Experiment (DRAFT → RUNNING)
       ↓
  [Meta Ads API 部署]
       ↓
  ExperimentController.record_result(metrics)
       ↓
  ExperimentController.compute_fitness()
       ↓
  ExperimentReport (Winner, FitnessScore)
       ↓
  E14.5.6 EvolutionMemoryGraph (回流)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.decision_executor import (
    ExecutionResult,
    EvolutionAction,
)
from market_ops.e11.evolution.fitness_schema import (
    FitnessScore,
    FitnessMetric,
    FitnessDirection,
    EvaluationResult,
)
from market_ops.e11.evolution.population_manager import PopulationManager
from market_ops.e11.evolution.population_schema import GenomePopulation


# ═══════════════════════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════════════════════

class ExperimentStatus(str, Enum):
    """实验生命周期状态.

    DRAFT     — 草稿，尚未部署
    RUNNING   — 运行中，广告已在投放
    PAUSED    — 已暂停
    COMPLETED — 已完成，结果已收集
    FAILED    — 失败 (预算耗尽 / 技术错误 / 无数据)
    """
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class GroupType(str, Enum):
    """实验组类型."""
    CONTROL = "control"   # 对照组 (原始创意)
    VARIANT = "variant"   # 实验组 (变异创意)


class PlatformType(str, Enum):
    """广告平台类型."""
    META_ADS = "meta_ads"
    GOOGLE_ADS = "google_ads"
    TIKTOK_ADS = "tiktok_ads"
    INTERNAL = "internal"  # 内部模拟 / 沙箱


# 可用的状态转换
VALID_TRANSITIONS: dict[ExperimentStatus, set[ExperimentStatus]] = {
    ExperimentStatus.DRAFT: {ExperimentStatus.RUNNING, ExperimentStatus.FAILED},
    ExperimentStatus.RUNNING: {ExperimentStatus.PAUSED, ExperimentStatus.COMPLETED, ExperimentStatus.FAILED},
    ExperimentStatus.PAUSED: {ExperimentStatus.RUNNING, ExperimentStatus.COMPLETED, ExperimentStatus.FAILED},
    ExperimentStatus.COMPLETED: set(),
    ExperimentStatus.FAILED: set(),
}


# ═══════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════

@dataclass
class ExperimentGroup:
    """实验组 — 包含 Control 或 Variant 基因组集合.

    Attributes:
        group_id: 组 ID
        group_type: CONTROL / VARIANT
        genome_ids: 该组包含的基因组 ID 列表
        budget: 该组预算
        expected_impact: 预期影响描述
        status: 组状态
    """
    group_id: str = field(default_factory=lambda: f"group_{uuid.uuid4().hex[:8]}")
    group_type: GroupType = GroupType.VARIANT
    genome_ids: list[str] = field(default_factory=list)
    budget: float = 0.0
    expected_impact: str = ""
    status: str = "pending"

    @property
    def genome_count(self) -> int:
        return len(self.genome_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "group_type": self.group_type.value,
            "genome_ids": self.genome_ids,
            "genome_count": self.genome_count,
            "budget": self.budget,
            "expected_impact": self.expected_impact,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentGroup:
        return cls(
            group_id=data.get("group_id", ""),
            group_type=GroupType(data.get("group_type", "variant")),
            genome_ids=data.get("genome_ids", []),
            budget=data.get("budget", 0.0),
            expected_impact=data.get("expected_impact", ""),
            status=data.get("status", "pending"),
        )


@dataclass
class ExperimentConfig:
    """实验配置参数.

    Attributes:
        budget_total: 总预算
        budget_per_group: 每组预算
        duration_days: 实验持续天数
        min_sample_size: 最小样本量 (用于统计显著性)
        confidence_threshold: 置信度阈值 (默认 0.95)
        platform: 目标广告平台
        auto_start: 是否自动部署
        auto_complete: 是否自动收集结果
    """
    budget_total: float = 500.0
    budget_per_group: float = 100.0
    duration_days: int = 7
    min_sample_size: int = 5000
    confidence_threshold: float = 0.95
    platform: PlatformType = PlatformType.INTERNAL
    auto_start: bool = False
    auto_complete: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "budget_total": self.budget_total,
            "budget_per_group": self.budget_per_group,
            "duration_days": self.duration_days,
            "min_sample_size": self.min_sample_size,
            "confidence_threshold": self.confidence_threshold,
            "platform": self.platform.value,
            "auto_start": self.auto_start,
            "auto_complete": self.auto_complete,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentConfig:
        return cls(
            budget_total=data.get("budget_total", 500.0),
            budget_per_group=data.get("budget_per_group", 100.0),
            duration_days=data.get("duration_days", 7),
            min_sample_size=data.get("min_sample_size", 5000),
            confidence_threshold=data.get("confidence_threshold", 0.95),
            platform=PlatformType(data.get("platform", "internal")),
            auto_start=data.get("auto_start", False),
            auto_complete=data.get("auto_complete", False),
        )


@dataclass
class Experiment:
    """一个完整进化实验.

    Attributes:
        experiment_id: 实验 ID
        name: 实验名称
        hypothesis: 实验假设 (来自 EvolutionPlan)
        control_group: 对照组
        variant_groups: 实验组列表
        config: 实验配置
        status: 实验状态
        plan_id: 来源进化计划 ID
        population_id: 关联种群 ID
        campaign_ids: 外部平台广告系列 ID
        created_at: 创建时间
        started_at: 开始时间
        completed_at: 完成时间
        tags: 标签
        metadata: 额外元数据
    """
    experiment_id: str = field(default_factory=lambda: f"exp_{uuid.uuid4().hex[:8]}")
    name: str = ""
    hypothesis: str = ""
    control_group: ExperimentGroup = field(default_factory=lambda: ExperimentGroup(group_type=GroupType.CONTROL))
    variant_groups: list[ExperimentGroup] = field(default_factory=list)
    config: ExperimentConfig = field(default_factory=ExperimentConfig)
    status: ExperimentStatus = ExperimentStatus.DRAFT
    plan_id: str = ""
    population_id: str = ""
    campaign_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str = ""
    completed_at: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── 属性 ──────────────────────────────────────────

    @property
    def total_genomes(self) -> int:
        """实验中所有基因组总数."""
        control_count = self.control_group.genome_count
        variant_count = sum(g.genome_count for g in self.variant_groups)
        return control_count + variant_count

    @property
    def all_genome_ids(self) -> list[str]:
        """实验中所有基因组 ID."""
        ids = list(self.control_group.genome_ids)
        for g in self.variant_groups:
            ids.extend(g.genome_ids)
        return ids

    @property
    def total_budget(self) -> float:
        """实验总预算."""
        budget = self.control_group.budget
        for g in self.variant_groups:
            budget += g.budget
        return budget or self.config.budget_total

    @property
    def is_active(self) -> bool:
        return self.status == ExperimentStatus.RUNNING

    @property
    def is_terminal(self) -> bool:
        return self.status in (ExperimentStatus.COMPLETED, ExperimentStatus.FAILED)

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "hypothesis": self.hypothesis,
            "control_group": self.control_group.to_dict(),
            "variant_groups": [g.to_dict() for g in self.variant_groups],
            "config": self.config.to_dict(),
            "status": self.status.value,
            "plan_id": self.plan_id,
            "population_id": self.population_id,
            "campaign_ids": self.campaign_ids,
            "total_genomes": self.total_genomes,
            "total_budget": self.total_budget,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Experiment:
        control_data = data.get("control_group", {})
        control = ExperimentGroup.from_dict(control_data) if control_data else ExperimentGroup(group_type=GroupType.CONTROL)
        variants = [ExperimentGroup.from_dict(g) for g in data.get("variant_groups", [])]
        config_data = data.get("config", {})
        config = ExperimentConfig.from_dict(config_data) if config_data else ExperimentConfig()
        return cls(
            experiment_id=data.get("experiment_id", ""),
            name=data.get("name", ""),
            hypothesis=data.get("hypothesis", ""),
            control_group=control,
            variant_groups=variants,
            config=config,
            status=ExperimentStatus(data.get("status", "draft")),
            plan_id=data.get("plan_id", ""),
            population_id=data.get("population_id", ""),
            campaign_ids=data.get("campaign_ids", []),
            created_at=data.get("created_at", ""),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at", ""),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ExperimentResult:
    """单个 Genome 的实验结果.

    Attributes:
        result_id: 结果 ID
        experiment_id: 所属实验 ID
        genome_id: 基因组 ID
        group_id: 所属实验组 ID
        group_type: Control / Variant
        metrics: 性能指标 (ctr, cvr, roas, cpi, d1, d7, d30, ltv, etc.)
        fitness_score: 适应度评分
        is_winner: 是否为 Winner
        statistical_significance: 统计显著性
        sample_size: 样本量
        created_at: 创建时间
    """
    result_id: str = field(default_factory=lambda: f"er_{uuid.uuid4().hex[:8]}")
    experiment_id: str = ""
    genome_id: str = ""
    group_id: str = ""
    group_type: GroupType = GroupType.VARIANT
    metrics: dict[str, float] = field(default_factory=dict)
    fitness_score: FitnessScore | None = None
    is_winner: bool = False
    statistical_significance: float = 0.0
    sample_size: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def ctr(self) -> float:
        return self.metrics.get("ctr", 0.0)

    @property
    def cvr(self) -> float:
        return self.metrics.get("cvr", 0.0)

    @property
    def roas(self) -> float:
        return self.metrics.get("roas", 0.0)

    @property
    def cpi(self) -> float:
        return self.metrics.get("cpi", 0.0)

    @property
    def d1_retention(self) -> float:
        return self.metrics.get("d1_retention", 0.0)

    @property
    def d7_retention(self) -> float:
        return self.metrics.get("d7_retention", 0.0)

    @property
    def d30_ltv(self) -> float:
        return self.metrics.get("d30_ltv", 0.0)

    @property
    def payer_rate(self) -> float:
        return self.metrics.get("payer_rate", 0.0)

    @property
    def score(self) -> float:
        return self.fitness_score.score if self.fitness_score else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "experiment_id": self.experiment_id,
            "genome_id": self.genome_id,
            "group_id": self.group_id,
            "group_type": self.group_type.value,
            "metrics": self.metrics,
            "ctr": self.ctr,
            "cvr": self.cvr,
            "roas": self.roas,
            "cpi": self.cpi,
            "d1_retention": self.d1_retention,
            "d7_retention": self.d7_retention,
            "d30_ltv": self.d30_ltv,
            "payer_rate": self.payer_rate,
            "fitness_score": self.fitness_score.to_dict() if self.fitness_score else None,
            "score": self.score,
            "is_winner": self.is_winner,
            "statistical_significance": self.statistical_significance,
            "sample_size": self.sample_size,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentResult:
        fs_data = data.get("fitness_score")
        fitness = FitnessScore.from_dict(fs_data) if fs_data else None
        return cls(
            result_id=data.get("result_id", ""),
            experiment_id=data.get("experiment_id", ""),
            genome_id=data.get("genome_id", ""),
            group_id=data.get("group_id", ""),
            group_type=GroupType(data.get("group_type", "variant")),
            metrics=data.get("metrics", {}),
            fitness_score=fitness,
            is_winner=data.get("is_winner", False),
            statistical_significance=data.get("statistical_significance", 0.0),
            sample_size=data.get("sample_size", 0),
            created_at=data.get("created_at", ""),
        )


@dataclass
class ExperimentReport:
    """实验汇总报告.

    Attributes:
        report_id: 报告 ID
        experiment_id: 实验 ID
        experiment_name: 实验名称
        status: 实验状态
        total_results: 结果总数
        winner_genome_id: 获胜基因组 ID
        winner_score: 获胜者评分
        winner_lift: 相对 Control 的提升幅度
        results: 各基因组结果列表
        recommendations: 进化建议
        summary: 报告摘要
        created_at: 创建时间
    """
    report_id: str = field(default_factory=lambda: f"report_{uuid.uuid4().hex[:8]}")
    experiment_id: str = ""
    experiment_name: str = ""
    status: ExperimentStatus = ExperimentStatus.DRAFT
    total_results: int = 0
    winner_genome_id: str = ""
    winner_score: float = 0.0
    winner_lift: float = 0.0
    results: list[ExperimentResult] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def has_winner(self) -> bool:
        return bool(self.winner_genome_id)

    @property
    def variant_results(self) -> list[ExperimentResult]:
        return [r for r in self.results if r.group_type == GroupType.VARIANT]

    @property
    def control_results(self) -> list[ExperimentResult]:
        return [r for r in self.results if r.group_type == GroupType.CONTROL]

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "experiment_id": self.experiment_id,
            "experiment_name": self.experiment_name,
            "status": self.status.value,
            "total_results": self.total_results,
            "winner_genome_id": self.winner_genome_id,
            "winner_score": self.winner_score,
            "winner_lift": self.winner_lift,
            "has_winner": self.has_winner,
            "results": [r.to_dict() for r in self.results],
            "recommendations": self.recommendations,
            "summary": self.summary,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════
# ExperimentController — 核心引擎
# ═══════════════════════════════════════════════════════════

class ExperimentController:
    """进化实验控制器 — 管理实验生命周期与结果回流.

    核心职责:
      1. 从 ExecutionResult 创建实验 (Control + Variant 分组)
      2. 管理实验状态 (DRAFT → RUNNING → COMPLETED)
      3. 记录实验结果 (CTR, CVR, ROAS, D1-D30, LTV)
      4. 计算适应度评分 (FitnessScore)
      5. 判定 Winner 并生成进化建议
      6. 将结果回流到 Evolution Memory

    用法:
        controller = ExperimentController(population_manager)
        exp = controller.create_experiment(
            name="Hook Mutation Test #023",
            hypothesis="rescue hook 提升 CTR",
            control_genomes=[control_genome],
            variant_genomes=[v1, v2, v3],
            config=ExperimentConfig(budget_total=500, duration_days=7),
        )
        controller.start_experiment(exp.experiment_id)
        # ... 等待广告平台数据 ...
        controller.record_result(exp.experiment_id, "genome_001", {"ctr": 0.035, "roas": 0.42})
        report = controller.compute_fitness(exp.experiment_id)
    """

    # 适应度评分权重 (E11.6.3 公式: revenue×0.4 + efficiency×0.3 + payer×0.3)
    FITNESS_WEIGHTS = {
        "roas": 0.4,        # 收入权重
        "ctr": 0.15,        # 效率权重
        "cvr": 0.15,        # 效率权重
        "payer_rate": 0.3,  # 付费权重
    }

    def __init__(
        self,
        population_manager: PopulationManager | None = None,
        default_config: ExperimentConfig | None = None,
    ):
        self._population_manager = population_manager or PopulationManager()
        self._default_config = default_config or ExperimentConfig()
        self._experiments: dict[str, Experiment] = {}
        self._results: dict[str, list[ExperimentResult]] = {}  # experiment_id → results
        self._reports: dict[str, ExperimentReport] = {}

    # ── 实验创建 ──────────────────────────────────────────

    def create_experiment(
        self,
        name: str,
        hypothesis: str = "",
        control_genomes: list[str] | None = None,
        variant_genomes: list[str] | None = None,
        config: ExperimentConfig | None = None,
        plan_id: str = "",
        population_id: str = "",
        tags: list[str] | None = None,
    ) -> Experiment:
        """创建新实验.

        Args:
            name: 实验名称
            hypothesis: 实验假设
            control_genomes: 对照组基因组 ID 列表
            variant_genomes: 实验组基因组 ID 列表
            config: 实验配置
            plan_id: 来源进化计划 ID
            population_id: 关联种群 ID
            tags: 标签

        Returns:
            Experiment: 新创建的实验 (DRAFT 状态)
        """
        cfg = config or self._default_config
        control_ids = list(control_genomes) if control_genomes else []
        variant_ids = list(variant_genomes) if variant_genomes else []

        # 确保至少有一组基因组
        if not control_ids and not variant_ids:
            raise ValueError("至少需要一组基因组 (control_genomes 或 variant_genomes)")

        # 如果没有对照组，从 variant 中取第一个作为对照组
        if not control_ids and variant_ids:
            control_ids = [variant_ids[0]]
            variant_ids = variant_ids[1:]

        # 计算每组预算
        total_groups = 1 + len(variant_ids)  # control + variants
        group_budget = cfg.budget_per_group or (cfg.budget_total / max(total_groups, 1))

        control_group = ExperimentGroup(
            group_type=GroupType.CONTROL,
            genome_ids=control_ids,
            budget=group_budget,
            expected_impact="baseline",
        )

        # 每个 variant genome 单独成组
        variant_groups = [
            ExperimentGroup(
                group_type=GroupType.VARIANT,
                genome_ids=[gid],
                budget=group_budget,
                expected_impact=hypothesis,
            )
            for gid in variant_ids
        ]

        experiment = Experiment(
            name=name,
            hypothesis=hypothesis,
            control_group=control_group,
            variant_groups=variant_groups,
            config=cfg,
            plan_id=plan_id,
            population_id=population_id,
            tags=list(tags) if tags else [],
        )

        self._experiments[experiment.experiment_id] = experiment
        self._results[experiment.experiment_id] = []

        return experiment

    def create_experiment_from_execution(
        self,
        name: str,
        execution_result: ExecutionResult,
        hypothesis: str = "",
        config: ExperimentConfig | None = None,
        plan_id: str = "",
        control_genome_ids: list[str] | None = None,
    ) -> Experiment:
        """从 E14.6.1 ExecutionResult 创建实验.

        Args:
            name: 实验名称
            execution_result: E14.6.1 的执行结果
            hypothesis: 实验假设
            config: 实验配置
            plan_id: 来源计划 ID
            control_genome_ids: 手动指定对照组 (默认取第一个 genome)

        Returns:
            Experiment: 新创建的实验
        """
        all_genomes = list(execution_result.genome_ids)

        if control_genome_ids:
            controls = control_genome_ids
            variants = [g for g in all_genomes if g not in controls]
        elif all_genomes:
            controls = [all_genomes[0]]
            variants = all_genomes[1:]
        else:
            raise ValueError("ExecutionResult 中无基因组")

        return self.create_experiment(
            name=name,
            hypothesis=hypothesis,
            control_genomes=controls,
            variant_genomes=variants,
            config=config,
            plan_id=plan_id or execution_result.action_id,
            population_id=execution_result.population_id,
        )

    def create_experiment_batch(
        self,
        name: str,
        actions: list[EvolutionAction],
        execution_results: list[ExecutionResult],
        hypothesis: str = "",
        config: ExperimentConfig | None = None,
        plan_id: str = "",
    ) -> Experiment:
        """从多个 E14.6.1 动作和结果批量创建实验.

        Args:
            name: 实验名称
            actions: 进化动作列表
            execution_results: 执行结果列表
            hypothesis: 实验假设
            config: 配置
            plan_id: 计划 ID

        Returns:
            Experiment: 新创建的实验 (包含所有 variant groups)
        """
        all_genomes: list[str] = []
        for er in execution_results:
            all_genomes.extend(er.genome_ids)

        if not all_genomes:
            raise ValueError("无基因组可创建实验")

        controls = [all_genomes[0]]
        variants = all_genomes[1:]

        return self.create_experiment(
            name=name,
            hypothesis=hypothesis,
            control_genomes=controls,
            variant_genomes=variants,
            config=config,
            plan_id=plan_id,
        )

    # ── 状态管理 ──────────────────────────────────────────

    def _transition(self, experiment: Experiment, target: ExperimentStatus) -> Experiment:
        """执行状态转换，验证合法性."""
        if target not in VALID_TRANSITIONS.get(experiment.status, set()):
            raise ValueError(
                f"无效状态转换: {experiment.status.value} → {target.value}. "
                f"允许: {[s.value for s in VALID_TRANSITIONS.get(experiment.status, set())]}"
            )
        experiment.status = target
        return experiment

    def start_experiment(self, experiment_id: str) -> Experiment:
        """启动实验 (DRAFT → RUNNING).

        Args:
            experiment_id: 实验 ID

        Returns:
            Experiment: 更新后的实验
        """
        exp = self._get_experiment(experiment_id)
        self._transition(exp, ExperimentStatus.RUNNING)
        exp.started_at = datetime.now(timezone.utc).isoformat()
        return exp

    def pause_experiment(self, experiment_id: str) -> Experiment:
        """暂停实验 (RUNNING → PAUSED)."""
        exp = self._get_experiment(experiment_id)
        self._transition(exp, ExperimentStatus.PAUSED)
        return exp

    def resume_experiment(self, experiment_id: str) -> Experiment:
        """恢复实验 (PAUSED → RUNNING)."""
        exp = self._get_experiment(experiment_id)
        self._transition(exp, ExperimentStatus.RUNNING)
        return exp

    def complete_experiment(self, experiment_id: str) -> Experiment:
        """完成实验 (RUNNING/PAUSED → COMPLETED)."""
        exp = self._get_experiment(experiment_id)
        self._transition(exp, ExperimentStatus.COMPLETED)
        exp.completed_at = datetime.now(timezone.utc).isoformat()
        return exp

    def fail_experiment(self, experiment_id: str, reason: str = "") -> Experiment:
        """标记实验失败 (DRAFT/RUNNING/PAUSED → FAILED)."""
        exp = self._get_experiment(experiment_id)
        self._transition(exp, ExperimentStatus.FAILED)
        exp.completed_at = datetime.now(timezone.utc).isoformat()
        if reason:
            exp.metadata["failure_reason"] = reason
        return exp

    # ── 结果记录 ──────────────────────────────────────────

    def record_result(
        self,
        experiment_id: str,
        genome_id: str,
        metrics: dict[str, float],
        sample_size: int = 0,
    ) -> ExperimentResult:
        """记录单个 Genome 的实验结果.

        Args:
            experiment_id: 实验 ID
            genome_id: 基因组 ID
            metrics: 性能指标 (ctr, cvr, roas, cpi, d1_retention, d7_retention, d30_ltv, payer_rate)
            sample_size: 样本量

        Returns:
            ExperimentResult: 记录的结果

        Raises:
            ValueError: 实验不存在或 genome_id 不在实验中
        """
        exp = self._get_experiment(experiment_id)

        if genome_id not in exp.all_genome_ids:
            raise ValueError(
                f"Genome {genome_id!r} 不在实验 {experiment_id!r} 中"
            )

        # 确定所属组
        group_type = GroupType.VARIANT
        group_id = ""
        if genome_id in exp.control_group.genome_ids:
            group_type = GroupType.CONTROL
            group_id = exp.control_group.group_id
        else:
            for g in exp.variant_groups:
                if genome_id in g.genome_ids:
                    group_id = g.group_id
                    break

        result = ExperimentResult(
            experiment_id=experiment_id,
            genome_id=genome_id,
            group_id=group_id,
            group_type=group_type,
            metrics=metrics,
            sample_size=sample_size,
        )

        if experiment_id not in self._results:
            self._results[experiment_id] = []
        self._results[experiment_id].append(result)

        return result

    def record_results_batch(
        self,
        experiment_id: str,
        metrics_map: dict[str, dict[str, float]],
    ) -> list[ExperimentResult]:
        """批量记录实验结果.

        Args:
            experiment_id: 实验 ID
            metrics_map: {genome_id: {metric_name: value}}

        Returns:
            list[ExperimentResult]: 记录的结果列表
        """
        results = []
        for genome_id, metrics in metrics_map.items():
            r = self.record_result(experiment_id, genome_id, metrics)
            results.append(r)
        return results

    # ── 适应度计算 ────────────────────────────────────────

    def compute_fitness(
        self,
        experiment_id: str,
        weights: dict[str, float] | None = None,
    ) -> ExperimentReport:
        """计算实验适应度评分并生成报告.

        使用 E11.6.3 加权公式:
          fitness = roas×0.4 + (ctr+cvr)×0.15 + payer_rate×0.3

        Args:
            experiment_id: 实验 ID
            weights: 自定义权重 (默认使用 E11.6.3 公式)

        Returns:
            ExperimentReport: 实验报告 (含 Winner 判定)
        """
        exp = self._get_experiment(experiment_id)
        results = self._results.get(experiment_id, [])
        w = weights or self.FITNESS_WEIGHTS

        if not results:
            return ExperimentReport(
                experiment_id=experiment_id,
                experiment_name=exp.name,
                status=exp.status,
                summary="无实验结果数据",
            )

        # 为每个结果计算 FitnessScore
        for r in results:
            r.fitness_score = self._compute_single_fitness(r, w)

        # 找出 Winner (最高评分)
        best = max(results, key=lambda r: r.score)
        best.is_winner = True

        # 计算相对 Control 的 lift
        control_results = [r for r in results if r.group_type == GroupType.CONTROL]
        control_avg = sum(r.score for r in control_results) / max(len(control_results), 1)
        winner_lift = (best.score - control_avg) / max(control_avg, 0.001) if control_avg > 0 else 0.0

        # 生成建议
        recommendations = self._generate_recommendations(results, best, winner_lift)

        summary = (
            f"实验 {exp.name}: Winner={best.genome_id} "
            f"(score={best.score:.3f}, lift={winner_lift*100:+.1f}%), "
            f"共 {len(results)} 个结果"
        )

        report = ExperimentReport(
            experiment_id=experiment_id,
            experiment_name=exp.name,
            status=exp.status,
            total_results=len(results),
            winner_genome_id=best.genome_id,
            winner_score=best.score,
            winner_lift=winner_lift,
            results=results,
            recommendations=recommendations,
            summary=summary,
        )

        self._reports[experiment_id] = report
        return report

    def _compute_single_fitness(
        self,
        result: ExperimentResult,
        weights: dict[str, float],
    ) -> FitnessScore:
        """计算单个基因组的适应度评分."""
        metrics = result.metrics

        fitness_metrics = []

        # ROAS (收入维度)
        if "roas" in metrics:
            fitness_metrics.append(FitnessMetric(
                name="roas",
                value=min(metrics["roas"], 1.0),  # 归一化到 0-1
                weight=weights.get("roas", 0.4),
                direction=FitnessDirection.MAXIMIZE,
            ))

        # CTR (效率维度)
        if "ctr" in metrics:
            fitness_metrics.append(FitnessMetric(
                name="ctr",
                value=min(metrics["ctr"] * 10, 1.0),  # 0.1 → 1.0
                weight=weights.get("ctr", 0.15),
                direction=FitnessDirection.MAXIMIZE,
            ))

        # CVR (效率维度)
        if "cvr" in metrics:
            fitness_metrics.append(FitnessMetric(
                name="cvr",
                value=min(metrics["cvr"], 1.0),
                weight=weights.get("cvr", 0.15),
                direction=FitnessDirection.MAXIMIZE,
            ))

        # Payer Rate (付费维度)
        if "payer_rate" in metrics:
            fitness_metrics.append(FitnessMetric(
                name="payer_rate",
                value=min(metrics["payer_rate"], 1.0),
                weight=weights.get("payer_rate", 0.3),
                direction=FitnessDirection.MAXIMIZE,
            ))

        # CPI (成本维度, MINIMIZE)
        if "cpi" in metrics and metrics["cpi"] > 0:
            normalized_cpi = min(metrics["cpi"] / 10.0, 1.0)
            fitness_metrics.append(FitnessMetric(
                name="cpi",
                value=normalized_cpi,
                weight=0.1,
                direction=FitnessDirection.MINIMIZE,
            ))

        if not fitness_metrics:
            fitness_metrics = [
                FitnessMetric(name="default", value=0.0, weight=1.0, direction=FitnessDirection.MAXIMIZE)
            ]

        return FitnessScore(
            genome_id=result.genome_id,
            metrics=fitness_metrics,
        )

    def _generate_recommendations(
        self,
        results: list[ExperimentResult],
        winner: ExperimentResult,
        winner_lift: float,
    ) -> list[str]:
        """基于实验结果生成进化建议."""
        recs: list[str] = []

        if winner_lift > 0.1:
            recs.append(f"AMPLIFY: {winner.genome_id} 表现显著优于对照 (+{winner_lift*100:.1f}%), 建议放大该基因方向")
        elif winner_lift > 0:
            recs.append(f"EXPLORE: {winner.genome_id} 略有提升 (+{winner_lift*100:.1f}%), 建议在该方向继续探索")
        else:
            recs.append("SUPPRESS: 无显著提升, 建议回归对照方向或探索新方向")

        # 检查是否有高 CTR 但低 ROAS 的
        for r in results:
            if r.ctr > 0.03 and r.roas < 0.3:
                recs.append(f"WARNING: {r.genome_id} 高 CTR({r.ctr:.3f}) 但低 ROAS({r.roas:.2f}), 可能存在吸引非付费用户的问题")

        # 检查 payer_rate
        high_payer = [r for r in results if r.payer_rate > 0.05]
        if high_payer:
            best_payer = max(high_payer, key=lambda r: r.payer_rate)
            recs.append(f"INSIGHT: {best_payer.genome_id} 付费率最高 ({best_payer.payer_rate:.3f}), 建议分析其基因特征")

        return recs

    # ── 查询 ──────────────────────────────────────────────

    def _get_experiment(self, experiment_id: str) -> Experiment:
        """获取实验，不存在则抛异常."""
        exp = self._experiments.get(experiment_id)
        if exp is None:
            raise ValueError(f"实验 {experiment_id!r} 不存在")
        return exp

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        """获取实验."""
        return self._experiments.get(experiment_id)

    def get_experiments_by_status(self, status: ExperimentStatus) -> list[Experiment]:
        """按状态获取实验."""
        return [e for e in self._experiments.values() if e.status == status]

    def get_active_experiments(self) -> list[Experiment]:
        """获取所有活跃实验 (RUNNING)."""
        return self.get_experiments_by_status(ExperimentStatus.RUNNING)

    def get_draft_experiments(self) -> list[Experiment]:
        """获取所有草稿实验 (DRAFT)."""
        return self.get_experiments_by_status(ExperimentStatus.DRAFT)

    def get_results(self, experiment_id: str) -> list[ExperimentResult]:
        """获取实验结果."""
        return self._results.get(experiment_id, [])

    def get_report(self, experiment_id: str) -> ExperimentReport | None:
        """获取实验报告."""
        return self._reports.get(experiment_id)

    def get_genome_result(self, experiment_id: str, genome_id: str) -> ExperimentResult | None:
        """获取特定基因组的结果."""
        for r in self._results.get(experiment_id, []):
            if r.genome_id == genome_id:
                return r
        return None

    # ── 统计 ──────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """获取控制器统计信息."""
        experiments = self._experiments.values()
        return {
            "total_experiments": len(self._experiments),
            "experiments_by_status": {
                s.value: len(self.get_experiments_by_status(s))
                for s in ExperimentStatus
            },
            "active_experiments": len(self.get_active_experiments()),
            "total_results": sum(len(v) for v in self._results.values()),
            "total_reports": len(self._reports),
            "experiments_with_winner": sum(
                1 for r in self._reports.values() if r.has_winner
            ),
        }

    def reset(self) -> None:
        """重置所有状态."""
        self._experiments.clear()
        self._results.clear()
        self._reports.clear()

    # ── 平台连接 (抽象层) ─────────────────────────────────

    def deploy_to_platform(
        self,
        experiment_id: str,
        platform: PlatformType | None = None,
    ) -> Experiment:
        """部署实验到广告平台 (抽象接口).

        将 Experiment 中的基因组转换为广告平台的实际 Campaign/Ad Set.
        当前为抽象层，实际平台实现通过 Adapter 模式注入.

        Args:
            experiment_id: 实验 ID
            platform: 目标平台 (默认使用实验配置中的平台)

        Returns:
            Experiment: 更新后的实验 (含 campaign_ids)
        """
        exp = self._get_experiment(experiment_id)
        target_platform = platform or exp.config.platform

        # 生成模拟 campaign_id 并存储 genome_id 映射
        campaign_ids = []
        genome_map: dict[str, str] = {}  # campaign_id → genome_id
        for g in [exp.control_group] + exp.variant_groups:
            for genome_id in g.genome_ids:
                cid = f"{target_platform.value}::{genome_id}::{uuid.uuid4().hex[:4]}"
                campaign_ids.append(cid)
                genome_map[cid] = genome_id

        exp.campaign_ids = campaign_ids
        exp.metadata["platform"] = target_platform.value
        exp.metadata["deployed_at"] = datetime.now(timezone.utc).isoformat()
        exp.metadata["campaign_genome_map"] = genome_map

        return exp

    def collect_platform_results(
        self,
        experiment_id: str,
        platform_data: dict[str, dict[str, float]],
    ) -> list[ExperimentResult]:
        """从广告平台收集实验结果 (抽象接口).

        Args:
            experiment_id: 实验 ID
            platform_data: {campaign_id: {metric: value}} 格式的平台数据

        Returns:
            list[ExperimentResult]: 收集的结果列表
        """
        exp = self._get_experiment(experiment_id)
        results: list[ExperimentResult] = []

        # 从 metadata 中获取 campaign_id → genome_id 映射
        genome_map: dict[str, str] = exp.metadata.get("campaign_genome_map", {})

        for campaign_id, metrics in platform_data.items():
            genome_id = genome_map.get(campaign_id)
            if genome_id:
                r = self.record_result(experiment_id, genome_id, metrics)
                results.append(r)

        return results


# ═══════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════

def create_experiment_controller(
    population_manager: PopulationManager | None = None,
    default_config: ExperimentConfig | None = None,
) -> ExperimentController:
    """创建默认 ExperimentController."""
    return ExperimentController(
        population_manager=population_manager,
        default_config=default_config,
    )