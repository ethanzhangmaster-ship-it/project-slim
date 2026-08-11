"""E14.4.3.3 Experiment Manager — 创意实验生命周期管理.

管理创意实验的完整生命周期:

  Creative Generated → Upload → Campaign → Spend → Measure → Winner/Loser

核心能力:
  - 实验创建: 根据 CreativePlan 创建实验
  - 状态管理: DRAFT → CREATED → RUNNING → COMPLETED/FAILED
  - 对照组管理: 管理原始组 vs 变体组
  - 结果收集: 汇总实验各组表现指标
  - 赢家判定: 基于 ROAS/CTR/疲劳度判定赢家

设计原则:
  - 确定性判定逻辑
  - 与 UA Agent 投放层对齐
  - 支持 A/B Test, Multi-Variant, Exploration, Scale-Up
  - 实验可追溯、可复现
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .planner import CreativePlan, PlanStatus, ExperimentType
from .strategy import CreativeStrategyType
from .opportunity import OpportunityPriority


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class ExperimentStatus(str, Enum):
    """实验状态."""
    DRAFT = "draft"            # 草稿
    CREATED = "created"        # 已创建 (已上传素材)
    RUNNING = "running"        # 运行中 (投放中)
    PAUSED = "paused"          # 暂停
    COMPLETED = "completed"    # 完成
    FAILED = "failed"          # 失败
    CANCELLED = "cancelled"    # 取消


class VariantGroupType(str, Enum):
    """变体组类型."""
    CONTROL = "control"        # 对照组 (原始素材)
    VARIANT = "variant"        # 变体组
    EXPLORATION = "exploration"  # 探索组


class ExperimentResult(str, Enum):
    """实验结果."""
    WINNER_FOUND = "winner_found"        # 发现赢家
    NO_SIGNIFICANT_DIFF = "no_diff"      # 无显著差异
    ALL_FAILED = "all_failed"            # 全部失败
    INCONCLUSIVE = "inconclusive"        # 数据不足
    PENDING = "pending"                  # 等待中


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class VariantMetrics:
    """变体指标.

    Attributes:
        variant_id: 变体 ID
        creative_id: 创意 ID (投放后)
        group_type: 组类型
        roas: ROAS
        ctr: CTR
        cvr: CVR
        fatigue: 疲劳度
        spend: 花费
        revenue: 收入
        installs: 安装量
        payer_rate: 付费率
        ltv: D7 LTV
        is_winner: 是否为赢家
    """
    variant_id: str = ""
    creative_id: str = ""
    group_type: VariantGroupType = VariantGroupType.VARIANT
    roas: float = 0.0
    ctr: float = 0.0
    cvr: float = 0.0
    fatigue: float = 0.0
    spend: float = 0.0
    revenue: float = 0.0
    installs: int = 0
    payer_rate: float = 0.0
    ltv: float = 0.0
    is_winner: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "creative_id": self.creative_id,
            "group_type": self.group_type.value,
            "roas": self.roas,
            "ctr": self.ctr,
            "cvr": self.cvr,
            "fatigue": self.fatigue,
            "spend": self.spend,
            "revenue": self.revenue,
            "installs": self.installs,
            "payer_rate": self.payer_rate,
            "ltv": self.ltv,
            "is_winner": self.is_winner,
        }


@dataclass
class CreativeExperiment:
    """创意实验 — 完整实验生命周期.

    Attributes:
        experiment_id: 实验 ID
        plan_id: 关联计划 ID
        creative_id: 原始素材 ID
        experiment_type: 实验类型
        status: 实验状态
        priority: 优先级
        control_group: 对照组 (原始素材)
        variant_groups: 变体组列表
        variant_ids: 变体 ID 列表
        success_criteria: 成功标准
        max_budget: 最大预算
        min_duration_days: 最少运行天数
        result: 实验结果
        winner_variant_id: 赢家变体 ID
        summary: 实验摘要
        created_at: 创建时间
        started_at: 开始时间
        completed_at: 完成时间
        metadata: 扩展元数据
    """
    experiment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str = ""
    creative_id: str = ""
    experiment_type: ExperimentType = ExperimentType.A_B_TEST
    status: ExperimentStatus = ExperimentStatus.DRAFT
    priority: OpportunityPriority = OpportunityPriority.MEDIUM
    control_group: VariantMetrics | None = None
    variant_groups: list[VariantMetrics] = field(default_factory=list)
    variant_ids: list[str] = field(default_factory=list)
    success_criteria: dict[str, float] = field(default_factory=dict)
    max_budget: float = 0.0
    min_duration_days: int = 3
    result: ExperimentResult = ExperimentResult.PENDING
    winner_variant_id: str = ""
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str = ""
    completed_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "plan_id": self.plan_id,
            "creative_id": self.creative_id,
            "experiment_type": self.experiment_type.value,
            "status": self.status.value,
            "priority": self.priority.value,
            "control_group": self.control_group.to_dict() if self.control_group else None,
            "variant_groups": [v.to_dict() for v in self.variant_groups],
            "variant_ids": self.variant_ids,
            "success_criteria": self.success_criteria,
            "max_budget": self.max_budget,
            "min_duration_days": self.min_duration_days,
            "result": self.result.value,
            "winner_variant_id": self.winner_variant_id,
            "summary": self.summary,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }

    @property
    def is_active(self) -> bool:
        return self.status == ExperimentStatus.RUNNING

    @property
    def is_completed(self) -> bool:
        return self.status == ExperimentStatus.COMPLETED

    @property
    def has_winner(self) -> bool:
        return self.result == ExperimentResult.WINNER_FOUND

    @property
    def variant_count(self) -> int:
        return len(self.variant_groups)


@dataclass
class ExperimentReport:
    """实验报告 — 批量实验汇总.

    Attributes:
        report_id: 报告 ID
        experiments: 实验列表
        total_experiments: 总实验数
        active: 运行中
        completed: 已完成
        winners_found: 发现赢家数
        success_rate: 成功率
        summary: 报告摘要
        created_at: 创建时间
    """
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    experiments: list[CreativeExperiment] = field(default_factory=list)
    total_experiments: int = 0
    active: int = 0
    completed: int = 0
    winners_found: int = 0
    success_rate: float = 0.0
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "experiments": [e.to_dict() for e in self.experiments],
            "total_experiments": self.total_experiments,
            "active": self.active,
            "completed": self.completed,
            "winners_found": self.winners_found,
            "success_rate": round(self.success_rate, 4),
            "summary": self.summary,
            "created_at": self.created_at,
        }

    @property
    def experiment_count(self) -> int:
        return len(self.experiments)


# ═══════════════════════════════════════════════════════════════
# Experiment Manager
# ═══════════════════════════════════════════════════════════════


class ExperimentManager:
    """实验管理器 — 创意实验生命周期管理.

    职责:
      1. 实验创建: 根据 CreativePlan 创建实验
      2. 状态管理: 管理实验生命周期
      3. 结果收集: 汇总各组表现指标
      4. 赢家判定: 基于 ROAS/CTR/疲劳度判定赢家

    用法:
        manager = ExperimentManager()
        experiment = manager.create_experiment(plan, variant_ids)
        manager.start(experiment)
        manager.collect_results(experiment, metrics)
        winner = manager.determine_winner(experiment)
    """

    def __init__(self):
        self._experiments: dict[str, CreativeExperiment] = {}
        self._history: list[CreativeExperiment] = []

    # ── 核心方法 ──────────────────────────────────────────────

    def create_experiment(
        self,
        plan: CreativePlan,
        variant_ids: list[str] | None = None,
        control_creative_id: str | None = None,
    ) -> CreativeExperiment:
        """从计划创建实验.

        Args:
            plan: 执行计划
            variant_ids: 变体 ID 列表
            control_creative_id: 对照组素材 ID

        Returns:
            CreativeExperiment: 实验
        """
        success_criteria = {}
        if plan.experiment_config:
            success_criteria = plan.experiment_config.success_criteria

        max_budget = plan.experiment_config.max_budget if plan.experiment_config else 0.0
        min_duration = plan.experiment_config.min_duration_days if plan.experiment_config else 3

        experiment = CreativeExperiment(
            plan_id=plan.plan_id,
            creative_id=plan.creative_id,
            experiment_type=plan.experiment_config.experiment_type if plan.experiment_config else ExperimentType.A_B_TEST,
            priority=plan.priority,
            variant_ids=variant_ids or [],
            success_criteria=success_criteria,
            max_budget=max_budget,
            min_duration_days=min_duration,
            summary=f"实验: {plan.strategy_type.value} for {plan.creative_id}",
        )

        if control_creative_id:
            experiment.control_group = VariantMetrics(
                creative_id=control_creative_id,
                group_type=VariantGroupType.CONTROL,
            )

        self._experiments[experiment.experiment_id] = experiment
        self._history.append(experiment)
        return experiment

    def start(self, experiment: CreativeExperiment) -> bool:
        """启动实验.

        Args:
            experiment: 实验

        Returns:
            bool: 是否成功启动
        """
        if experiment.status not in (ExperimentStatus.DRAFT, ExperimentStatus.CREATED):
            return False
        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = datetime.now(timezone.utc).isoformat()
        return True

    def pause(self, experiment: CreativeExperiment) -> bool:
        """暂停实验."""
        if experiment.status != ExperimentStatus.RUNNING:
            return False
        experiment.status = ExperimentStatus.PAUSED
        return True

    def resume(self, experiment: CreativeExperiment) -> bool:
        """恢复实验."""
        if experiment.status != ExperimentStatus.PAUSED:
            return False
        experiment.status = ExperimentStatus.RUNNING
        return True

    def collect_results(
        self,
        experiment: CreativeExperiment,
        variant_metrics: list[VariantMetrics],
        control_metrics: VariantMetrics | None = None,
    ) -> bool:
        """收集实验结果.

        Args:
            experiment: 实验
            variant_metrics: 变体组指标列表
            control_metrics: 对照组指标

        Returns:
            bool: 是否成功收集
        """
        if experiment.status != ExperimentStatus.RUNNING:
            return False

        experiment.variant_groups = variant_metrics
        if control_metrics:
            experiment.control_group = control_metrics

        return True

    def determine_winner(self, experiment: CreativeExperiment) -> ExperimentResult:
        """判定赢家.

        基于 ROAS/CTR/疲劳度的综合判定:
          - 赢家: ROAS > 1.0 AND CTR > 对照组 AND 疲劳度 < 0.5
          - 无显著差异: 所有变体与对照组差异 < 10%
          - 全部失败: 所有变体 ROAS < 0.5
          - 数据不足: 样本量 < 500

        Args:
            experiment: 实验

        Returns:
            ExperimentResult: 实验结果
        """
        if not experiment.variant_groups:
            experiment.result = ExperimentResult.INCONCLUSIVE
            return experiment.result

        control = experiment.control_group
        winners = []

        for vg in experiment.variant_groups:
            # 样本量检查
            if vg.installs < 500:
                continue

            # 赢家判定条件
            is_winner = True

            # ROAS 检查
            if vg.roas < 1.0:
                is_winner = False

            # 与对照组比较
            if control and control.ctr > 0:
                if vg.ctr < control.ctr * 0.9:  # 下降超过10%
                    is_winner = False

            # 疲劳度检查
            if vg.fatigue > 0.5:
                is_winner = False

            if is_winner:
                vg.is_winner = True
                winners.append(vg)

        if winners:
            # 选最佳赢家 (按 ROAS 排序)
            best = max(winners, key=lambda w: w.roas)
            experiment.winner_variant_id = best.variant_id
            experiment.result = ExperimentResult.WINNER_FOUND
        elif all(vg.installs < 500 for vg in experiment.variant_groups):
            experiment.result = ExperimentResult.INCONCLUSIVE
        elif all(vg.roas < 0.5 for vg in experiment.variant_groups):
            experiment.result = ExperimentResult.ALL_FAILED
        else:
            experiment.result = ExperimentResult.NO_SIGNIFICANT_DIFF

        experiment.status = ExperimentStatus.COMPLETED
        experiment.completed_at = datetime.now(timezone.utc).isoformat()
        experiment.summary = self._build_result_summary(experiment)

        return experiment.result

    def complete(self, experiment: CreativeExperiment) -> bool:
        """完成实验 (手动标记)."""
        experiment.status = ExperimentStatus.COMPLETED
        experiment.completed_at = datetime.now(timezone.utc).isoformat()
        return True

    def fail(self, experiment: CreativeExperiment, reason: str = "") -> bool:
        """标记实验失败."""
        experiment.status = ExperimentStatus.FAILED
        experiment.completed_at = datetime.now(timezone.utc).isoformat()
        experiment.summary = f"实验失败: {reason}" if reason else "实验失败"
        return True

    def cancel(self, experiment: CreativeExperiment) -> bool:
        """取消实验."""
        if experiment.status == ExperimentStatus.COMPLETED:
            return False
        experiment.status = ExperimentStatus.CANCELLED
        experiment.completed_at = datetime.now(timezone.utc).isoformat()
        return True

    # ── 内部方法 ──────────────────────────────────────────────

    def _build_result_summary(self, experiment: CreativeExperiment) -> str:
        """构建结果摘要."""
        parts = []
        result_labels = {
            ExperimentResult.WINNER_FOUND: f"发现赢家: {experiment.winner_variant_id[:8]}",
            ExperimentResult.NO_SIGNIFICANT_DIFF: "无显著差异",
            ExperimentResult.ALL_FAILED: "全部变体未达标",
            ExperimentResult.INCONCLUSIVE: "数据不足，无法判定",
        }
        parts.append(result_labels.get(experiment.result, "未知"))

        if experiment.variant_groups:
            avg_roas = sum(v.roas for v in experiment.variant_groups) / len(experiment.variant_groups)
            parts.append(f"平均ROAS={avg_roas:.2f}")

        return " | ".join(parts)

    # ── 查询 ──────────────────────────────────────────────────

    def get_experiment(self, experiment_id: str) -> CreativeExperiment | None:
        return self._experiments.get(experiment_id)

    def get_experiments_by_plan(self, plan_id: str) -> list[CreativeExperiment]:
        return [e for e in self._experiments.values() if e.plan_id == plan_id]

    def get_experiments_by_creative(self, creative_id: str) -> list[CreativeExperiment]:
        return [e for e in self._experiments.values() if e.creative_id == creative_id]

    def get_active_experiments(self) -> list[CreativeExperiment]:
        return [e for e in self._experiments.values() if e.is_active]

    def get_completed_experiments(self) -> list[CreativeExperiment]:
        return [e for e in self._experiments.values() if e.is_completed]

    def get_winners(self) -> list[CreativeExperiment]:
        return [e for e in self._experiments.values() if e.has_winner]

    def get_history(self, n: int = 20) -> list[CreativeExperiment]:
        return self._history[-n:]

    def generate_report(self) -> ExperimentReport:
        """生成实验汇总报告."""
        experiments = list(self._experiments.values())
        active = len(self.get_active_experiments())
        completed = len(self.get_completed_experiments())
        winners = len(self.get_winners())

        success_rate = (winners / completed) if completed > 0 else 0.0

        return ExperimentReport(
            experiments=experiments,
            total_experiments=len(experiments),
            active=active,
            completed=completed,
            winners_found=winners,
            success_rate=success_rate,
            summary=f"共 {len(experiments)} 个实验, {active} 运行中, {completed} 已完成, {winners} 发现赢家",
        )

    def stats(self) -> dict[str, Any]:
        total = len(self._experiments)
        if total == 0:
            return {"total": 0}
        status_counts: dict[str, int] = {}
        for e in self._experiments.values():
            s = e.status.value
            status_counts[s] = status_counts.get(s, 0) + 1
        return {
            "total": total,
            "by_status": status_counts,
            "active": len(self.get_active_experiments()),
            "completed": len(self.get_completed_experiments()),
            "winners": len(self.get_winners()),
        }

    def reset(self) -> None:
        self._experiments.clear()
        self._history.clear()


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_experiment_manager() -> ExperimentManager:
    """创建默认实验管理器."""
    return ExperimentManager()