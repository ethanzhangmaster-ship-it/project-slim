"""E15.0.8 Execution Repository — 执行记录持久化.

替代: ProductionWorker._results (内存) → Postgres
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, func, select

from ..database import DatabaseManager
from ..models import ExecutionRecord


class ExecutionRepository:
    """执行仓库 — ExecutionResult 的持久化 CRUD.

    用法:
        repo = ExecutionRepository(db)
        repo.save(result_dict)
        records = repo.find_by_status("failed")
    """

    def __init__(self, db: DatabaseManager):
        self._db = db

    # ── Create ───────────────────────────────────────────────

    def save(self, execution: dict[str, Any]) -> ExecutionRecord:
        """保存执行记录."""
        record = ExecutionRecord(
            execution_id=execution.get("result_id", execution.get("execution_id", "")),
            action_id=execution.get("action_id", ""),
            action_type=execution.get("action_type", ""),
            params=execution.get("params", {}),
            status=execution.get("status", "pending"),
            output=execution.get("output", {}),
            error=execution.get("error", ""),
            duration_ms=execution.get("duration_ms", 0.0),
            rollback_record_id=execution.get("rollback_record_id", ""),
        )
        with self._db.session() as session:
            session.add(record)
        return record

    # ── Read ─────────────────────────────────────────────────

    def get_by_id(self, execution_id: str) -> ExecutionRecord | None:
        with self._db.session() as session:
            return session.get(ExecutionRecord, execution_id)

    def find_by_action(self, action_id: str) -> list[ExecutionRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(ExecutionRecord)
                    .where(ExecutionRecord.action_id == action_id)
                    .order_by(desc(ExecutionRecord.started_at))
                )
                .scalars()
                .all()
            )

    def find_by_type(
        self, action_type: str, limit: int = 50,
    ) -> list[ExecutionRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(ExecutionRecord)
                    .where(ExecutionRecord.action_type == action_type)
                    .order_by(desc(ExecutionRecord.started_at))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    def find_by_status(
        self, status: str, limit: int = 50,
    ) -> list[ExecutionRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(ExecutionRecord)
                    .where(ExecutionRecord.status == status)
                    .order_by(desc(ExecutionRecord.started_at))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    def find_failed(self, limit: int = 50) -> list[ExecutionRecord]:
        return self.find_by_status("failed", limit)

    def get_recent(self, limit: int = 50) -> list[ExecutionRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(ExecutionRecord)
                    .order_by(desc(ExecutionRecord.started_at))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    # ── Update ───────────────────────────────────────────────

    def update_status(
        self, execution_id: str, status: str, error: str = "",
    ) -> ExecutionRecord | None:
        with self._db.session() as session:
            record = session.get(ExecutionRecord, execution_id)
            if record:
                record.status = status
                if error:
                    record.error = error
            return record

    # ── Delete ───────────────────────────────────────────────

    def delete(self, execution_id: str) -> bool:
        with self._db.session() as session:
            record = session.get(ExecutionRecord, execution_id)
            if record:
                session.delete(record)
                return True
            return False

    def delete_older_than(self, days: int) -> int:
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with self._db.session() as session:
            result = session.execute(
                select(ExecutionRecord).where(ExecutionRecord.started_at < cutoff)
            ).scalars().all()
            count = len(result)
            for r in result:
                session.delete(r)
            return count

    def count(self) -> int:
        with self._db.session() as session:
            return session.execute(
                select(func.count()).select_from(ExecutionRecord)
            ).scalar() or 0

    def stats(self) -> dict[str, Any]:
        with self._db.session() as session:
            total = session.execute(
                select(func.count()).select_from(ExecutionRecord)
            ).scalar() or 0
            if total == 0:
                return {"total": 0, "success_count": 0, "failure_count": 0}
            success = session.execute(
                select(func.count())
                .select_from(ExecutionRecord)
                .where(ExecutionRecord.status == "success")
            ).scalar() or 0
            failed = session.execute(
                select(func.count())
                .select_from(ExecutionRecord)
                .where(ExecutionRecord.status == "failed")
            ).scalar() or 0
            return {
                "total": total,
                "success_count": success,
                "failure_count": failed,
                "success_rate": round(success / total, 4),
            }