"""E15.0.8 Metric Repository — 指标快照持久化.

替代: MetricsCollector._snapshots (内存) → Postgres
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, func, select

from ..database import DatabaseManager
from ..models import MetricSnapshot


class MetricRepository:
    """指标仓库 — GrowthMetrics 快照的持久化 CRUD.

    用法:
        repo = MetricRepository(db)
        repo.save(metrics_dict)
        snapshots = repo.find_by_game("P04", limit=50)
    """

    def __init__(self, db: DatabaseManager):
        self._db = db

    # ── Create ───────────────────────────────────────────────

    def save(self, metrics: dict[str, Any]) -> MetricSnapshot:
        """保存指标快照."""
        agent = metrics.get("agent", {})
        execution = metrics.get("execution", {})
        business = metrics.get("business", {})

        record = MetricSnapshot(
            game_id=metrics.get("game_id", ""),
            decision_count=agent.get("decision_count", 0),
            success_rate=agent.get("success_rate", 0.0),
            failure_rate=agent.get("failure_rate", 0.0),
            action_success=execution.get("action_success", 0),
            action_failed=execution.get("action_failed", 0),
            rollback_count=execution.get("rollback_count", 0),
            approval_waiting=execution.get("approval_waiting", 0),
            spend=business.get("spend", 0.0),
            revenue=business.get("revenue", 0.0),
            roas=business.get("roas", 0.0),
            ltv=business.get("ltv", 0.0),
            installs=business.get("installs", 0),
            purchases=business.get("purchases", 0),
            impressions=business.get("impressions", 0),
            clicks=business.get("clicks", 0),
        )
        with self._db.session() as session:
            session.add(record)
        return record

    # ── Read ─────────────────────────────────────────────────

    def find_by_game(
        self, game_id: str, limit: int = 50, offset: int = 0,
    ) -> list[MetricSnapshot]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(MetricSnapshot)
                    .where(MetricSnapshot.game_id == game_id)
                    .order_by(desc(MetricSnapshot.created_at))
                    .limit(limit)
                    .offset(offset)
                )
                .scalars()
                .all()
            )

    def get_latest(self, game_id: str) -> MetricSnapshot | None:
        with self._db.session() as session:
            return (
                session.execute(
                    select(MetricSnapshot)
                    .where(MetricSnapshot.game_id == game_id)
                    .order_by(desc(MetricSnapshot.created_at))
                    .limit(1)
                )
                .scalars()
                .first()
            )

    def get_recent(self, limit: int = 50) -> list[MetricSnapshot]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(MetricSnapshot)
                    .order_by(desc(MetricSnapshot.created_at))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    def get_roas_trend(self, game_id: str, n: int = 10) -> list[float]:
        """获取 ROAS 趋势."""
        with self._db.session() as session:
            rows = (
                session.execute(
                    select(MetricSnapshot.roas)
                    .where(MetricSnapshot.game_id == game_id)
                    .order_by(desc(MetricSnapshot.created_at))
                    .limit(n)
                )
                .scalars()
                .all()
            )
            return list(reversed(rows))

    def get_spend_trend(self, game_id: str, n: int = 10) -> list[float]:
        """获取花费趋势."""
        with self._db.session() as session:
            rows = (
                session.execute(
                    select(MetricSnapshot.spend)
                    .where(MetricSnapshot.game_id == game_id)
                    .order_by(desc(MetricSnapshot.created_at))
                    .limit(n)
                )
                .scalars()
                .all()
            )
            return list(reversed(rows))

    # ── Delete ───────────────────────────────────────────────

    def delete_older_than(self, days: int) -> int:
        """删除 N 天前的快照."""
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with self._db.session() as session:
            result = session.execute(
                select(MetricSnapshot).where(MetricSnapshot.created_at < cutoff)
            ).scalars().all()
            count = len(result)
            for r in result:
                session.delete(r)
            return count

    def delete_by_game(self, game_id: str) -> int:
        with self._db.session() as session:
            result = session.execute(
                select(MetricSnapshot).where(MetricSnapshot.game_id == game_id)
            ).scalars().all()
            count = len(result)
            for r in result:
                session.delete(r)
            return count

    def count(self) -> int:
        with self._db.session() as session:
            return session.execute(
                select(func.count()).select_from(MetricSnapshot)
            ).scalar() or 0