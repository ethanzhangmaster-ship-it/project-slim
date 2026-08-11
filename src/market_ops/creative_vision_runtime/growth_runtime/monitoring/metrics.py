"""E15.0.5 Growth Metrics — 增长指标采集.

采集三类指标:
  - Agent 指标:   decision_count, success_rate, failure_rate
  - Execution 指标: action_success, rollback_count, approval_waiting
  - Business 指标: spend, revenue, ROAS, LTV

E15.0.8 升级: 支持 StorageService 持久化到 PostgreSQL.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage.service import StorageService

logger = logging.getLogger(__name__)


@dataclass
class GrowthMetrics:
    """增长指标快照.

    Attributes:
        timestamp:      采集时间
        game_id:        游戏 ID
        agent_metrics:  Agent 指标
        exec_metrics:   执行指标
        business_metrics: 业务指标
    """

    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    game_id: str = ""

    # Agent 指标
    decision_count: int = 0
    success_rate: float = 0.0
    failure_rate: float = 0.0

    # Execution 指标
    action_success: int = 0
    action_failed: int = 0
    rollback_count: int = 0
    approval_waiting: int = 0

    # Business 指标
    spend: float = 0.0
    revenue: float = 0.0
    roas: float = 0.0
    ltv: float = 0.0
    installs: int = 0
    purchases: int = 0
    impressions: int = 0
    clicks: int = 0

    @property
    def action_total(self) -> int:
        return self.action_success + self.action_failed

    @property
    def action_success_rate(self) -> float:
        total = self.action_total
        if total == 0:
            return 1.0
        return self.action_success / total

    @property
    def ctr(self) -> float:
        if self.impressions == 0:
            return 0.0
        return self.clicks / self.impressions

    @property
    def cpa(self) -> float:
        if self.action_total == 0:
            return 0.0
        return self.spend / self.action_total

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "game_id": self.game_id,
            "agent": {
                "decision_count": self.decision_count,
                "success_rate": self.success_rate,
                "failure_rate": self.failure_rate,
            },
            "execution": {
                "action_success": self.action_success,
                "action_failed": self.action_failed,
                "action_total": self.action_total,
                "action_success_rate": self.action_success_rate,
                "rollback_count": self.rollback_count,
                "approval_waiting": self.approval_waiting,
            },
            "business": {
                "spend": self.spend,
                "revenue": self.revenue,
                "roas": self.roas,
                "ltv": self.ltv,
                "installs": self.installs,
                "purchases": self.purchases,
                "impressions": self.impressions,
                "clicks": self.clicks,
                "ctr": self.ctr,
                "cpa": self.cpa,
            },
        }


class MetricsCollector:
    """指标采集器 — 收集和聚合增长指标.

    用法:
        collector = MetricsCollector()
        collector.record_decision(success=True)
        collector.record_execution(success=True)
        collector.record_business(spend=100, revenue=200, roas=2.0)
        metrics = collector.snapshot()

    E15.0.8 持久化:
        collector = MetricsCollector(storage=storage)
        collector.snapshot()  # 自动双写 (内存 + PostgreSQL)
    """

    def __init__(
        self,
        game_id: str = "",
        storage: "StorageService | None" = None,
    ):
        self._game_id = game_id
        self._storage = storage

        # Agent
        self._decision_count: int = 0
        self._decision_success: int = 0
        self._decision_failed: int = 0

        # Execution
        self._action_success: int = 0
        self._action_failed: int = 0
        self._rollback_count: int = 0
        self._approval_waiting: int = 0

        # Business
        self._spend: float = 0.0
        self._revenue: float = 0.0
        self._ltv: float = 0.0
        self._installs: int = 0
        self._purchases: int = 0
        self._impressions: int = 0
        self._clicks: int = 0

        self._snapshots: list[GrowthMetrics] = []

    # ── Record ───────────────────────────────────────────────

    def record_decision(self, success: bool = True) -> None:
        self._decision_count += 1
        if success:
            self._decision_success += 1
        else:
            self._decision_failed += 1

    def record_execution(
        self,
        success: bool = True,
        rollback: bool = False,
        approval_waiting: bool = False,
    ) -> None:
        if success:
            self._action_success += 1
        else:
            self._action_failed += 1
        if rollback:
            self._rollback_count += 1
        if approval_waiting:
            self._approval_waiting += 1

    def record_business(
        self,
        spend: float = 0.0,
        revenue: float = 0.0,
        ltv: float = 0.0,
        installs: int = 0,
        purchases: int = 0,
        impressions: int = 0,
        clicks: int = 0,
    ) -> None:
        self._spend += spend
        self._revenue += revenue
        self._ltv = max(self._ltv, ltv)  # 取最新
        self._installs += installs
        self._purchases += purchases
        self._impressions += impressions
        self._clicks += clicks

    # ── Snapshot ─────────────────────────────────────────────

    def snapshot(self) -> GrowthMetrics:
        """生成当前指标快照."""
        total = self._decision_count
        roas = self._revenue / self._spend if self._spend > 0 else 0.0

        metrics = GrowthMetrics(
            game_id=self._game_id,
            decision_count=self._decision_count,
            success_rate=self._decision_success / total if total > 0 else 0.0,
            failure_rate=self._decision_failed / total if total > 0 else 0.0,
            action_success=self._action_success,
            action_failed=self._action_failed,
            rollback_count=self._rollback_count,
            approval_waiting=self._approval_waiting,
            spend=self._spend,
            revenue=self._revenue,
            roas=roas,
            ltv=self._ltv,
            installs=self._installs,
            purchases=self._purchases,
            impressions=self._impressions,
            clicks=self._clicks,
        )
        self._snapshots.append(metrics)

        # E15.0.8: 持久化到 PostgreSQL
        if self._storage is not None:
            try:
                self._storage.metrics.save(metrics.to_dict())
            except Exception as e:
                logger.warning(f"Failed to persist metrics snapshot to PostgreSQL: {e}")

        return metrics

    # ── Query ────────────────────────────────────────────────

    def get_snapshots(self, limit: int = 50) -> list[GrowthMetrics]:
        return self._snapshots[-limit:]

    def get_latest(self) -> GrowthMetrics | None:
        return self._snapshots[-1] if self._snapshots else None

    def get_roas_trend(self, n: int = 10) -> list[float]:
        return [s.roas for s in self._snapshots[-n:]]

    # ── Reset ────────────────────────────────────────────────

    def reset(self) -> None:
        self._decision_count = 0
        self._decision_success = 0
        self._decision_failed = 0
        self._action_success = 0
        self._action_failed = 0
        self._rollback_count = 0
        self._approval_waiting = 0
        self._spend = 0.0
        self._revenue = 0.0
        self._ltv = 0.0
        self._installs = 0
        self._purchases = 0
        self._impressions = 0
        self._clicks = 0
        self._snapshots.clear()