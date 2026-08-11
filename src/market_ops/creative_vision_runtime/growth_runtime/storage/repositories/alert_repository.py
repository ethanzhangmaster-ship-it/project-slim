"""E15.0.8 Alert Repository — 报警记录持久化.

替代: AlertManager._alerts (内存) → Postgres
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, func, select, update

from ..database import DatabaseManager
from ..models import AlertRecord


class AlertRepository:
    """报警仓库 — Alert 的持久化 CRUD.

    用法:
        repo = AlertRepository(db)
        repo.save(alert_dict)
        alerts = repo.find_unacknowledged()
    """

    def __init__(self, db: DatabaseManager):
        self._db = db

    # ── Create ───────────────────────────────────────────────

    def save(self, alert: dict[str, Any]) -> AlertRecord:
        """保存报警记录."""
        record = AlertRecord(
            alert_id=alert.get("alert_id", ""),
            severity=alert.get("severity", "info"),
            rule_name=alert.get("rule_name", ""),
            message=alert.get("message", ""),
            game_id=alert.get("game_id", ""),
            metrics_data=alert.get("metrics", {}),
            acknowledged=alert.get("acknowledged", False),
        )
        with self._db.session() as session:
            session.add(record)
        return record

    # ── Read ─────────────────────────────────────────────────

    def get_by_id(self, alert_id: str) -> AlertRecord | None:
        with self._db.session() as session:
            return session.get(AlertRecord, alert_id)

    def find_by_severity(
        self, severity: str, limit: int = 50,
    ) -> list[AlertRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(AlertRecord)
                    .where(AlertRecord.severity == severity)
                    .order_by(desc(AlertRecord.created_at))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    def find_by_game(
        self, game_id: str, limit: int = 50,
    ) -> list[AlertRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(AlertRecord)
                    .where(AlertRecord.game_id == game_id)
                    .order_by(desc(AlertRecord.created_at))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    def find_unacknowledged(self, limit: int = 50) -> list[AlertRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(AlertRecord)
                    .where(AlertRecord.acknowledged == False)
                    .order_by(desc(AlertRecord.created_at))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    def find_by_rule(
        self, rule_name: str, limit: int = 50,
    ) -> list[AlertRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(AlertRecord)
                    .where(AlertRecord.rule_name == rule_name)
                    .order_by(desc(AlertRecord.created_at))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    def get_recent(self, limit: int = 50) -> list[AlertRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(AlertRecord)
                    .order_by(desc(AlertRecord.created_at))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    # ── Update ───────────────────────────────────────────────

    def acknowledge(self, alert_id: str) -> bool:
        with self._db.session() as session:
            record = session.get(AlertRecord, alert_id)
            if record:
                record.acknowledged = True
                return True
            return False

    def acknowledge_all(self) -> int:
        with self._db.session() as session:
            result = session.execute(
                update(AlertRecord)
                .where(AlertRecord.acknowledged == False)
                .values(acknowledged=True)
            )
            return result.rowcount

    # ── Delete ───────────────────────────────────────────────

    def delete(self, alert_id: str) -> bool:
        with self._db.session() as session:
            record = session.get(AlertRecord, alert_id)
            if record:
                session.delete(record)
                return True
            return False

    def delete_older_than(self, days: int) -> int:
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with self._db.session() as session:
            result = session.execute(
                select(AlertRecord).where(AlertRecord.created_at < cutoff)
            ).scalars().all()
            count = len(result)
            for r in result:
                session.delete(r)
            return count

    def count(self) -> int:
        with self._db.session() as session:
            return session.execute(
                select(func.count()).select_from(AlertRecord)
            ).scalar() or 0

    def count_unacknowledged(self) -> int:
        with self._db.session() as session:
            return session.execute(
                select(func.count())
                .select_from(AlertRecord)
                .where(AlertRecord.acknowledged == False)
            ).scalar() or 0

    def get_summary(self) -> dict[str, Any]:
        return {
            "total": self.count(),
            "unacknowledged": self.count_unacknowledged(),
        }