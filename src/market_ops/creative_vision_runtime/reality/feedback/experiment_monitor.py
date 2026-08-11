"""E12.4 Phase 2 — Experiment Monitor。

监控实验生命周期，跟踪 6 阶段状态转换。

状态机:
  CREATED → GENERATING → READY → RUNNING → COMPLETED
     ↓          ↓          ↓         ↓
  FAILED     FAILED     FAILED    FAILED

核心功能:
  - 创建实验（create）
  - 状态转换（transition）
  - 查询实验（get_experiment, get_active, get_by_creative）
  - 更新指标（update_metrics）
"""

from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    VALID_EXPERIMENT_TRANSITIONS,
    ExperimentRun,
    ExperimentStatus,
    MutationRequest,
)


class ExperimentMonitor:
    """实验监控引擎。

    管理 ExperimentRun 的完整生命周期。

    Usage:
        >>> monitor = ExperimentMonitor()
        >>> exp = monitor.create(request, creative_id="c001")
        >>> monitor.transition(exp.experiment_id, ExperimentStatus.GENERATING)
        >>> monitor.update_metrics(exp.experiment_id, {"ctr": 0.031, "spend": 520})
        >>> active = monitor.get_active_experiments()
    """

    def __init__(self) -> None:
        self._experiments: dict[str, ExperimentRun] = {}

        # 统计
        self.total_experiments_created: int = 0
        self.total_transitions: int = 0

    # ── Create ─────────────────────────────────────────────

    def create(
        self,
        request: MutationRequest,
        creative_id: str | None = None,
        start_time: str | None = None,
    ) -> ExperimentRun:
        """创建新实验。

        Args:
            request:     突变请求
            creative_id: 创意 ID（默认使用 request.creative_id）
            start_time:  开始时间

        Returns:
            ExperimentRun
        """
        cid = creative_id or request.creative_id

        if start_time is None:
            start_time = datetime.now(timezone.utc).isoformat()

        experiment = ExperimentRun(
            creative_id=cid,
            mutation_request_id=request.request_id,
            status=ExperimentStatus.CREATED,
            start_time=start_time,
            metadata={
                "intent": request.intent.value,
                "generation_count": request.generation_count,
                "dna_constraints": request.dna_constraints,
            },
        )

        self._experiments[experiment.experiment_id] = experiment
        self.total_experiments_created += 1
        return experiment

    def create_batch(
        self,
        requests: list[MutationRequest],
        start_time: str | None = None,
    ) -> list[ExperimentRun]:
        """批量创建实验。

        Args:
            requests:   突变请求列表
            start_time: 开始时间

        Returns:
            ExperimentRun 列表
        """
        experiments: list[ExperimentRun] = []
        for request in requests:
            experiments.append(
                self.create(request, start_time=start_time)
            )
        return experiments

    # ── Transition ─────────────────────────────────────────

    def transition(
        self,
        experiment_id: str,
        target_status: ExperimentStatus,
        end_time: str | None = None,
    ) -> ExperimentRun:
        """状态转换。

        Args:
            experiment_id: 实验 ID
            target_status: 目标状态
            end_time:      结束时间（用于 COMPLETED/FAILED）

        Returns:
            更新后的 ExperimentRun

        Raises:
            ValueError: 实验不存在或状态转换无效
        """
        experiment = self._get_or_raise(experiment_id)

        if not experiment.can_transition_to(target_status):
            valid = VALID_EXPERIMENT_TRANSITIONS.get(experiment.status, [])
            raise ValueError(
                f"Invalid transition: {experiment.status.value} → "
                f"{target_status.value}. "
                f"Valid targets: {[v.value for v in valid]}"
            )

        old_status = experiment.status
        experiment.status = target_status
        self.total_transitions += 1

        # 记录时间
        if target_status == ExperimentStatus.RUNNING and not experiment.start_time:
            experiment.start_time = datetime.now(timezone.utc).isoformat()

        if target_status in (ExperimentStatus.COMPLETED, ExperimentStatus.FAILED):
            experiment.end_time = end_time or datetime.now(timezone.utc).isoformat()

        # 记录状态转换历史
        if "status_history" not in experiment.metadata:
            experiment.metadata["status_history"] = []
        experiment.metadata["status_history"].append({
            "from": old_status.value,
            "to": target_status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return experiment

    def transition_to_generating(self, experiment_id: str) -> ExperimentRun:
        """CREATED → GENERATING。"""
        return self.transition(experiment_id, ExperimentStatus.GENERATING)

    def transition_to_ready(
        self,
        experiment_id: str,
        variants: list[str] | None = None,
    ) -> ExperimentRun:
        """GENERATING → READY。

        可选：设置变体 ID 列表。
        """
        exp = self.transition(experiment_id, ExperimentStatus.READY)
        if variants:
            exp.variants = list(variants)
        return exp

    def transition_to_running(self, experiment_id: str) -> ExperimentRun:
        """READY → RUNNING。"""
        return self.transition(experiment_id, ExperimentStatus.RUNNING)

    def transition_to_completed(self, experiment_id: str) -> ExperimentRun:
        """RUNNING → COMPLETED。"""
        return self.transition(experiment_id, ExperimentStatus.COMPLETED)

    def transition_to_failed(
        self,
        experiment_id: str,
        reason: str = "",
    ) -> ExperimentRun:
        """任何状态 → FAILED。"""
        exp = self.transition(experiment_id, ExperimentStatus.FAILED)
        if reason:
            exp.metadata["failure_reason"] = reason
        return exp

    # ── Metrics ────────────────────────────────────────────

    def update_metrics(
        self,
        experiment_id: str,
        metrics: dict,
    ) -> ExperimentRun:
        """更新实验指标。

        Args:
            experiment_id: 实验 ID
            metrics:       指标 dict（如 {"ctr": 0.031, "roas": 0.72, "spend": 520}）

        Returns:
            更新后的 ExperimentRun
        """
        experiment = self._get_or_raise(experiment_id)
        experiment.metrics.update(metrics)
        return experiment

    def set_variants(
        self,
        experiment_id: str,
        variants: list[str],
    ) -> ExperimentRun:
        """设置变体列表。"""
        experiment = self._get_or_raise(experiment_id)
        experiment.variants = list(variants)
        return experiment

    # ── Query ──────────────────────────────────────────────

    def get_experiment(self, experiment_id: str) -> ExperimentRun | None:
        """获取实验。"""
        return self._experiments.get(experiment_id)

    def get_active_experiments(self) -> list[ExperimentRun]:
        """获取所有活跃实验。"""
        return [e for e in self._experiments.values() if e.is_active]

    def get_completed_experiments(self) -> list[ExperimentRun]:
        """获取所有已完成实验。"""
        return [e for e in self._experiments.values() if e.is_terminal]

    def get_by_creative(self, creative_id: str) -> list[ExperimentRun]:
        """获取指定创意的所有实验。"""
        return [
            e for e in self._experiments.values()
            if e.creative_id == creative_id
        ]

    def get_by_status(self, status: ExperimentStatus) -> list[ExperimentRun]:
        """获取指定状态的所有实验。"""
        return [e for e in self._experiments.values() if e.status == status]

    def get_by_mutation_request(self, request_id: str) -> ExperimentRun | None:
        """获取指定突变请求的实验。"""
        for e in self._experiments.values():
            if e.mutation_request_id == request_id:
                return e
        return None

    def get_all_experiments(self) -> list[ExperimentRun]:
        """获取所有实验。"""
        return list(self._experiments.values())

    # ── Stats ──────────────────────────────────────────────

    def get_stats(self) -> dict:
        """获取实验统计。"""
        total = len(self._experiments)
        active = len(self.get_active_experiments())
        completed = len(self.get_completed_experiments())

        status_counts: dict[str, int] = {}
        for status in ExperimentStatus:
            count = len(self.get_by_status(status))
            if count > 0:
                status_counts[status.value] = count

        return {
            "total_experiments": total,
            "active_experiments": active,
            "completed_experiments": completed,
            "status_counts": status_counts,
            "total_created": self.total_experiments_created,
            "total_transitions": self.total_transitions,
        }

    def clear(self) -> None:
        """清空所有实验。"""
        self._experiments.clear()

    # ── Private ────────────────────────────────────────────

    def _get_or_raise(self, experiment_id: str) -> ExperimentRun:
        """获取实验或抛出异常。"""
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment not found: {experiment_id}")
        return experiment

    def __len__(self) -> int:
        return len(self._experiments)

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"ExperimentMonitor(total={stats['total_experiments']}, "
            f"active={stats['active_experiments']}, "
            f"completed={stats['completed_experiments']})"
        )