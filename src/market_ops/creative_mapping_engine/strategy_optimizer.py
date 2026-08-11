"""DeliveryStrategyOptimizer — 基于成效的投放策略优化器 (v1.8).

基于历史 performance 自动选择投放素材（mapping confidence + performance 联合排序），
自动暂停低效素材。

核心流程:
  1. compute_performance_score(): 归一化成效得分 [0, 1]
  2. compute_priority(): 联合排序 (confidence * 0.4 + performance_score * 0.6)
  3. evaluate_and_archive(): 评估所有 PUBLISHED 记录，自动归档低效素材
  4. rank_dispatchable(): 按 delivery_priority 降序返回待投递记录

暂停阈值:
  - CTR < 0.5% (CTR_PAUSE_THRESHOLD)
  - CPI > $50 (CPI_PAUSE_THRESHOLD)
  - 最少 impressions >= 1000 (MIN_DATA_POINTS) 才评估

Usage::

    optimizer = DeliveryStrategyOptimizer(engine=engine)
    result = optimizer.evaluate_and_archive(dry_run=True)
    ranking = optimizer.rank_dispatchable(limit=20)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from .models import MappingDeliveryStatus, MappingStatus, now_iso

if TYPE_CHECKING:
    from .engine import CreativeMappingEngine
    from .insights_ingester import CreativePerformance

logger = logging.getLogger(__name__)


# ── 常量 ──────────────────────────────────────────────────────

CTR_PAUSE_THRESHOLD = 0.005       # CTR < 0.5% 自动暂停
CPI_PAUSE_THRESHOLD = 50.0        # CPI > $50 自动暂停
MIN_DATA_POINTS = 1000            # 最少 impressions 才评估
CONFIDENCE_WEIGHT = 0.4           # confidence 权重
PERFORMANCE_WEIGHT = 0.6          # performance_score 权重


# ── 结果数据结构 ──────────────────────────────────────────────


@dataclass
class ArchiveResult:
    """自动归档结果。"""

    total_evaluated: int = 0
    total_archived: int = 0
    total_skipped: int = 0
    archives: list[dict[str, Any]] = field(default_factory=list)
    dry_run: bool = True
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_evaluated": self.total_evaluated,
            "total_archived": self.total_archived,
            "total_skipped": self.total_skipped,
            "archives": self.archives,
            "dry_run": self.dry_run,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
        }


# ── DeliveryStrategyOptimizer ─────────────────────────────────


class DeliveryStrategyOptimizer:
    """基于成效的投放策略优化器 (v1.8)。

    Args:
        engine: CreativeMappingEngine 实例
        data_dir: 数据目录（默认 engine 的 data_dir）
        ctr_threshold: CTR 暂停阈值 (默认 0.005)
        cpi_threshold: CPI 暂停阈值 (默认 50.0)
        min_data_points: 最少 impressions (默认 1000)
    """

    def __init__(
        self,
        engine: CreativeMappingEngine,
        data_dir: Optional[str] = None,
        ctr_threshold: float = CTR_PAUSE_THRESHOLD,
        cpi_threshold: float = CPI_PAUSE_THRESHOLD,
        min_data_points: int = MIN_DATA_POINTS,
    ) -> None:
        self._engine = engine
        self._ctr_threshold = ctr_threshold
        self._cpi_threshold = cpi_threshold
        self._min_data_points = min_data_points
        if data_dir:
            from pathlib import Path
            self._data_dir = Path(data_dir)
        else:
            store = engine.store
            self._data_dir = store._dir  # type: ignore[attr-defined]

    # ── 属性 ──────────────────────────────────────────────

    @property
    def engine(self) -> CreativeMappingEngine:
        return self._engine

    @property
    def ctr_threshold(self) -> float:
        return self._ctr_threshold

    @property
    def cpi_threshold(self) -> float:
        return self._cpi_threshold

    @property
    def min_data_points(self) -> int:
        return self._min_data_points

    # ── 公共 API ──────────────────────────────────────────

    def compute_performance_score(self, perf: CreativePerformance) -> float:
        """计算归一化成效得分 [0, 1]。

        评分维度:
          - CTR: 点击率 (ctr / 0.05 归一化, 上限 1.0)
          - CPI: 安装成本 (反向: cpi_threshold / max(cpi, 0.01))
          - IR: 安装率 (installs / clicks)

        综合分 = CTR_score * 0.4 + CPI_score * 0.4 + IR_score * 0.2
        """
        if perf is None or perf.impressions == 0:
            return 0.0

        # CTR 得分: ctr / 0.05 (5% CTR 为满分)
        ctr_score = min(perf.ctr / 0.05, 1.0)

        # CPI 得分: cpi_threshold / cpi (CPI 越低分越高)
        cpi = self._compute_cpi(perf)
        if cpi > 0:
            cpi_score = min(self._cpi_threshold / cpi, 1.0)
        else:
            # 无 installs → CPI 无意义，给中等分
            cpi_score = 0.5 if perf.spend > 0 else 0.0

        # IR 得分: installs / clicks (安装率)
        if perf.clicks > 0:
            ir_score = min(perf.installs / perf.clicks, 1.0)
        else:
            ir_score = 0.0

        score = ctr_score * 0.4 + cpi_score * 0.4 + ir_score * 0.2
        return round(min(max(score, 0.0), 1.0), 4)

    def compute_priority(self, record: Any) -> float:
        """联合排序: confidence * 0.4 + performance_score * 0.6。"""
        confidence = record.confidence
        perf_score = 0.0
        if record.performance is not None:
            perf_score = self.compute_performance_score(record.performance)

        priority = confidence * CONFIDENCE_WEIGHT + perf_score * PERFORMANCE_WEIGHT
        return round(min(max(priority, 0.0), 1.0), 4)

    def evaluate_and_archive(
        self,
        dry_run: bool = True,
    ) -> ArchiveResult:
        """评估所有 PUBLISHED 记录，自动归档低效素材。

        归档条件 (需同时满足):
          - impressions >= min_data_points (数据量充足)
          - CTR < ctr_threshold 或 CPI > cpi_threshold

        Args:
            dry_run: True=仅评估不归档 (默认)

        Returns:
            ArchiveResult
        """
        import time
        t0 = time.time()
        result = ArchiveResult(dry_run=dry_run)

        # 查询所有 PUBLISHED 记录
        all_records = self._engine.store.list_all_records(limit=10000)
        published = [
            r for r in all_records
            if r.delivery_status == MappingDeliveryStatus.PUBLISHED
            and not r.auto_archived
        ]

        for record in published:
            result.total_evaluated += 1

            # 无 performance 数据 → 跳过
            if record.performance is None:
                result.total_skipped += 1
                continue

            perf = record.performance

            # 数据量不足 → 跳过
            if perf.impressions < self._min_data_points:
                result.total_skipped += 1
                continue

            # 计算指标
            should_archive = False
            reasons: list[str] = []

            if perf.ctr < self._ctr_threshold:
                should_archive = True
                reasons.append(
                    f"CTR {perf.ctr:.4f} < {self._ctr_threshold}"
                )

            cpi = self._compute_cpi(perf)
            if perf.installs > 0 and cpi > self._cpi_threshold:
                should_archive = True
                reasons.append(
                    f"CPI {cpi:.2f} > {self._cpi_threshold}"
                )

            if not should_archive:
                result.total_skipped += 1
                continue

            reason = "; ".join(reasons)

            # 回写归档 (dry_run 不回写)
            if not dry_run:
                ok = self._engine.store.update_strategy_fields(
                    mapping_id=record.mapping_id,
                    auto_archived=True,
                    auto_archived_reason=reason,
                )
                if not ok:
                    continue

            result.total_archived += 1
            result.archives.append({
                "mapping_id": record.mapping_id,
                "facebook_creative_id": record.facebook_creative_id,
                "ad_id": record.ad_id,
                "ctr": perf.ctr,
                "cpi": round(cpi, 2),
                "impressions": perf.impressions,
                "installs": perf.installs,
                "spend": perf.spend,
                "reason": reason,
                "dry_run": dry_run,
            })

        result.elapsed_seconds = time.time() - t0
        return result

    def rank_dispatchable(
        self,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """按 delivery_priority 降序返回待投递记录。

        排序键: delivery_priority (confidence * 0.4 + performance_score * 0.6)
        过滤: 未归档 + 可投递状态 (MATCHED/REVIEW_APPROVED + UNDISPATCHED/FAILED)
        """
        all_records = self._engine.store.list_all_records(limit=10000)

        # 过滤可投递记录
        dispatchable = [
            r for r in all_records
            if r.status in (MappingStatus.MATCHED, MappingStatus.REVIEW_APPROVED)
            and r.delivery_status in (
                MappingDeliveryStatus.UNDISPATCHED,
                MappingDeliveryStatus.FAILED,
            )
            and not r.auto_archived
        ]

        # 计算 priority 并排序
        ranked: list[tuple[float, Any, float, float]] = []
        for r in dispatchable:
            priority = self.compute_priority(r)
            perf_score = 0.0
            if r.performance is not None:
                perf_score = self.compute_performance_score(r.performance)
            ranked.append((priority, r, perf_score, r.confidence))

        # 降序排序
        ranked.sort(key=lambda x: x[0], reverse=True)

        return [
            {
                "mapping_id": r.mapping_id,
                "facebook_creative_id": r.facebook_creative_id,
                "facebook_creative_name": r.facebook_creative_name,
                "confidence": round(conf, 4),
                "performance_score": round(perf_score, 4),
                "delivery_priority": round(priority, 4),
                "delivery_status": r.delivery_status.value,
                "eagle_filename": r.eagle_filename,
            }
            for priority, r, perf_score, conf in ranked[:limit]
        ]

    def get_strategy_summary(self) -> dict[str, Any]:
        """获取策略优化摘要统计。"""
        all_records = self._engine.store.list_all_records(limit=10000)
        published = [
            r for r in all_records
            if r.delivery_status == MappingDeliveryStatus.PUBLISHED
        ]
        archived = [r for r in published if r.auto_archived]
        with_perf = [r for r in published if r.performance is not None]

        return {
            "total_published": len(published),
            "total_archived": len(archived),
            "total_with_performance": len(with_perf),
            "ctr_threshold": self._ctr_threshold,
            "cpi_threshold": self._cpi_threshold,
            "min_data_points": self._min_data_points,
            "confidence_weight": CONFIDENCE_WEIGHT,
            "performance_weight": PERFORMANCE_WEIGHT,
        }

    # ── 内部方法 ──────────────────────────────────────────

    def _compute_cpi(self, perf: CreativePerformance) -> float:
        """计算 CPI (Cost Per Install)。"""
        if perf.installs == 0:
            return 0.0
        return perf.spend / perf.installs


__all__ = [
    "DeliveryStrategyOptimizer",
    "ArchiveResult",
    "CTR_PAUSE_THRESHOLD",
    "CPI_PAUSE_THRESHOLD",
    "MIN_DATA_POINTS",
    "CONFIDENCE_WEIGHT",
    "PERFORMANCE_WEIGHT",
]
