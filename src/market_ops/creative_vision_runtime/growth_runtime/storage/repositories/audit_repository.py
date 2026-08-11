"""E15.0.8 Audit Repository — 审计记录持久化.

替代: AuditStore (内存) → Postgres
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, func, select

from ..database import DatabaseManager
from ..models import AuditRecord


class AuditRepository:
    """审计仓库 — GrowthDecisionAudit 的持久化 CRUD.

    用法:
        repo = AuditRepository(db)
        repo.save(audit_dict)
        records = repo.find_by_game("P04", limit=50)
    """

    def __init__(self, db: DatabaseManager):
        self._db = db

    # ── Create ───────────────────────────────────────────────

    def save(self, audit: dict[str, Any]) -> AuditRecord:
        """保存一条审计记录.

        Args:
            audit: GrowthDecisionAudit.to_dict() 输出

        Returns:
            AuditRecord
        """
        record = AuditRecord(
            id=audit.get("audit_id", ""),
            game_id=audit.get("game_id", ""),
            agent_id=audit.get("agent_id", ""),
            detected_problem=audit.get("detected_problem", ""),
            decision=audit.get("decision", ""),
            action=audit.get("action", ""),
            confidence=audit.get("confidence", 0.0),
            input_context=audit.get("input_context", {}),
            execution_status=audit.get("execution_status", "pending"),
            result=audit.get("result", {}),
            plan_id=audit.get("plan_id", ""),
            cycle_id=audit.get("cycle_id", ""),
            safety_decision=audit.get("safety_decision", ""),
            rollback_record_id=audit.get("rollback_record_id", ""),
            metadata_=audit.get("metadata", {}),
        )
        with self._db.session() as session:
            session.add(record)
        return record

    def save_batch(self, audits: list[dict[str, Any]]) -> list[AuditRecord]:
        """批量保存审计记录."""
        records = []
        with self._db.session() as session:
            for audit in audits:
                record = AuditRecord(
                    id=audit.get("audit_id", ""),
                    game_id=audit.get("game_id", ""),
                    agent_id=audit.get("agent_id", ""),
                    detected_problem=audit.get("detected_problem", ""),
                    decision=audit.get("decision", ""),
                    action=audit.get("action", ""),
                    confidence=audit.get("confidence", 0.0),
                    input_context=audit.get("input_context", {}),
                    execution_status=audit.get("execution_status", "pending"),
                    result=audit.get("result", {}),
                    plan_id=audit.get("plan_id", ""),
                    cycle_id=audit.get("cycle_id", ""),
                    safety_decision=audit.get("safety_decision", ""),
                    rollback_record_id=audit.get("rollback_record_id", ""),
                    metadata_=audit.get("metadata", {}),
                )
                session.add(record)
                records.append(record)
        return records

    # ── Read ─────────────────────────────────────────────────

    def get_by_id(self, audit_id: str) -> AuditRecord | None:
        with self._db.session() as session:
            return session.get(AuditRecord, audit_id)

    def find_by_game(
        self, game_id: str, limit: int = 50, offset: int = 0,
    ) -> list[AuditRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(AuditRecord)
                    .where(AuditRecord.game_id == game_id)
                    .order_by(desc(AuditRecord.created_at))
                    .limit(limit)
                    .offset(offset)
                )
                .scalars()
                .all()
            )

    def find_by_agent(
        self, agent_id: str, limit: int = 50,
    ) -> list[AuditRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(AuditRecord)
                    .where(AuditRecord.agent_id == agent_id)
                    .order_by(desc(AuditRecord.created_at))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    def find_by_status(
        self, status: str, limit: int = 50,
    ) -> list[AuditRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(AuditRecord)
                    .where(AuditRecord.execution_status == status)
                    .order_by(desc(AuditRecord.created_at))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    def find_by_time_range(
        self, start: str, end: str | None = None, limit: int = 100,
    ) -> list[AuditRecord]:
        end = end or datetime.now(timezone.utc).isoformat()
        with self._db.session() as session:
            return (
                session.execute(
                    select(AuditRecord)
                    .where(
                        AuditRecord.created_at >= start,
                        AuditRecord.created_at <= end,
                    )
                    .order_by(desc(AuditRecord.created_at))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    def find_by_plan(self, plan_id: str) -> list[AuditRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(AuditRecord)
                    .where(AuditRecord.plan_id == plan_id)
                    .order_by(desc(AuditRecord.created_at))
                )
                .scalars()
                .all()
            )

    def find_needing_attention(self, limit: int = 50) -> list[AuditRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(AuditRecord)
                    .where(
                        AuditRecord.execution_status.in_(
                            ["pending", "rejected", "failed"]
                        )
                    )
                    .order_by(desc(AuditRecord.created_at))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    def get_all(self, limit: int = 100) -> list[AuditRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(AuditRecord)
                    .order_by(desc(AuditRecord.created_at))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    # ── Update ───────────────────────────────────────────────

    def update_status(
        self, audit_id: str, status: str, result: dict[str, Any] | None = None,
    ) -> AuditRecord | None:
        with self._db.session() as session:
            record = session.get(AuditRecord, audit_id)
            if record:
                record.execution_status = status
                if result:
                    record.result = {**record.result, **result}
            return record

    def update_rollback(
        self, audit_id: str, rollback_record_id: str,
    ) -> AuditRecord | None:
        with self._db.session() as session:
            record = session.get(AuditRecord, audit_id)
            if record:
                record.execution_status = "rolled_back"
                record.rollback_record_id = rollback_record_id
            return record

    # ── Delete ───────────────────────────────────────────────

    def delete(self, audit_id: str) -> bool:
        with self._db.session() as session:
            record = session.get(AuditRecord, audit_id)
            if record:
                session.delete(record)
                return True
            return False

    def delete_by_game(self, game_id: str) -> int:
        with self._db.session() as session:
            result = session.execute(
                select(AuditRecord).where(AuditRecord.game_id == game_id)
            ).scalars().all()
            count = len(result)
            for r in result:
                session.delete(r)
            return count

    # ── Statistics ───────────────────────────────────────────

    def count(self) -> int:
        with self._db.session() as session:
            return session.execute(
                select(func.count()).select_from(AuditRecord)
            ).scalar() or 0

    def count_by_game(self, game_id: str) -> int:
        with self._db.session() as session:
            return session.execute(
                select(func.count())
                .select_from(AuditRecord)
                .where(AuditRecord.game_id == game_id)
            ).scalar() or 0

    def stats(self) -> dict[str, Any]:
        with self._db.session() as session:
            total = session.execute(
                select(func.count()).select_from(AuditRecord)
            ).scalar() or 0

            if total == 0:
                return {"total": 0, "success_count": 0, "failure_count": 0, "success_rate": 0.0}

            success = session.execute(
                select(func.count())
                .select_from(AuditRecord)
                .where(AuditRecord.execution_status == "success")
            ).scalar() or 0

            failed = session.execute(
                select(func.count())
                .select_from(AuditRecord)
                .where(AuditRecord.execution_status == "failed")
            ).scalar() or 0

            return {
                "total": total,
                "success_count": success,
                "failure_count": failed,
                "success_rate": round(success / total, 4),
            }