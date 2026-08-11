"""E15.0.1 Audit Service — 审计服务层.

封装 AuditStore，提供面向 Agent 的审计接口:
  - log_decision(): 记录决策
  - log_execution_result(): 记录执行结果
  - get_audit_trail(): 获取完整审计追踪
  - generate_audit_report(): 生成审计报告

E15.0.8 升级: 支持 StorageService 持久化到 PostgreSQL.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from .audit_store import AuditStore
from .models import ExecutionStatus, GrowthDecisionAudit

if TYPE_CHECKING:
    from ..storage.service import StorageService

logger = logging.getLogger(__name__)


class AuditService:
    """审计服务 — Agent 决策的完整审计追踪.

    用法:
        service = AuditService()
        audit = service.log_decision(
            agent_id="growth_agent_01",
            game_id="P04",
            input_context={"roas": 1.0, "spend": 500},
            detected_problem="ROAS decay detected",
            decision="reduce budget 20%",
            action="update_budget",
            confidence=0.87,
        )
        # 执行后
        service.log_execution_result(
            audit.audit_id,
            status=ExecutionStatus.SUCCESS,
            result={"roas_after_7d": 1.2},
        )

    E15.0.8 持久化:
        storage = StorageService(db=db, redis=redis)
        service = AuditService(storage=storage)
        # 决策自动双写 (内存 + PostgreSQL)
    """

    def __init__(
        self,
        store: AuditStore | None = None,
        storage: "StorageService | None" = None,
    ):
        self._store = store or AuditStore()
        self._storage = storage

    @property
    def store(self) -> AuditStore:
        return self._store

    @property
    def has_persistent_storage(self) -> bool:
        return self._storage is not None

    # ── Logging ──────────────────────────────────────────────

    def log_decision(
        self,
        agent_id: str,
        game_id: str,
        input_context: dict[str, Any],
        detected_problem: str,
        decision: str,
        action: str,
        confidence: float,
        plan_id: str = "",
        cycle_id: str = "",
        safety_decision: str = "",
    ) -> GrowthDecisionAudit:
        """记录一次 Agent 决策.

        Returns:
            GrowthDecisionAudit: 审计记录 (包含 audit_id)
        """
        audit = GrowthDecisionAudit(
            agent_id=agent_id,
            game_id=game_id,
            input_context=input_context,
            detected_problem=detected_problem,
            decision=decision,
            action=action,
            confidence=confidence,
            plan_id=plan_id,
            cycle_id=cycle_id,
            safety_decision=safety_decision,
        )
        result = self._store.record(audit)

        # E15.0.8: 持久化到 PostgreSQL
        if self._storage is not None:
            try:
                self._storage.audit.save(audit.to_dict())
            except Exception as e:
                logger.warning(f"Failed to persist audit to PostgreSQL: {e}")

        return result

    def log_execution_result(
        self,
        audit_id: str,
        status: ExecutionStatus,
        result: dict[str, Any] | None = None,
        rollback_record_id: str = "",
    ) -> GrowthDecisionAudit | None:
        """记录执行结果."""
        audit_result = self._store.update_result(
            audit_id=audit_id,
            status=status,
            result=result,
            rollback_record_id=rollback_record_id,
        )

        # E15.0.8: 持久化到 PostgreSQL
        if self._storage is not None:
            try:
                self._storage.audit.update_status(
                    audit_id=audit_id,
                    status=status.value,
                    result=result,
                )
            except Exception as e:
                logger.warning(f"Failed to persist execution result to PostgreSQL: {e}")

        return audit_result

    # ── Audit Trail ──────────────────────────────────────────

    def get_audit_trail(
        self,
        game_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """获取指定游戏的完整审计追踪."""
        records = self._store.get_by_game(game_id)
        records.sort(key=lambda r: r.timestamp, reverse=True)
        return [r.to_summary() for r in records[:limit]]

    def get_decision_history(
        self,
        game_id: str,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> list[GrowthDecisionAudit]:
        """获取决策历史."""
        if start_time and end_time:
            return self._store.get_by_time_range(start_time, end_time)
        return self._store.get_by_game(game_id)

    # ── Reports ──────────────────────────────────────────────

    def generate_audit_report(
        self,
        game_id: str,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, Any]:
        """生成审计报告.

        Returns:
            {
                "game_id": "P04",
                "period": {"start": ..., "end": ...},
                "total_decisions": N,
                "success_rate": X%,
                "avg_confidence": X,
                "decisions": [...],
                "stats": {...}
            }
        """
        records = self.get_decision_history(game_id, start_time, end_time)
        total = len(records)
        if total == 0:
            return {
                "game_id": game_id,
                "period": {"start": start_time or "N/A", "end": end_time or "N/A"},
                "total_decisions": 0,
                "success_rate": 0.0,
                "avg_confidence": 0.0,
                "decisions": [],
                "stats": {},
            }

        success = len([r for r in records if r.is_success])
        failed = len([r for r in records if r.is_failed])
        confidences = [r.confidence for r in records if r.confidence > 0]

        # 按决策类型统计
        by_action: dict[str, int] = {}
        for r in records:
            by_action[r.action] = by_action.get(r.action, 0) + 1

        return {
            "game_id": game_id,
            "period": {
                "start": start_time or records[-1].timestamp,
                "end": end_time or records[0].timestamp,
            },
            "total_decisions": total,
            "success_rate": round(success / total, 4),
            "avg_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
            "by_action": by_action,
            "success_count": success,
            "failure_count": failed,
            "decisions": [r.to_summary() for r in records[-20:]],
            "stats": self._store.stats_by_game(game_id),
        }

    def generate_full_report(self) -> dict[str, Any]:
        """生成全量审计报告."""
        stats = self._store.stats()
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_records": len(self._store),
            "stats": stats,
            "needing_attention": len(self._store.get_needing_attention()),
            "failed_count": len(self._store.get_failed()),
            "rolled_back_count": len(self._store.get_rolled_back()),
        }

    # ── Rollback Audit ───────────────────────────────────────

    def log_rollback(
        self,
        audit_id: str,
        result: dict[str, Any] | None = None,
    ) -> GrowthDecisionAudit | None:
        """记录回滚."""
        audit_result = self._store.update_result(
            audit_id=audit_id,
            status=ExecutionStatus.ROLLED_BACK,
            result=result,
        )

        # E15.0.8: 持久化到 PostgreSQL
        if self._storage is not None:
            try:
                self._storage.audit.update_status(
                    audit_id=audit_id,
                    status=ExecutionStatus.ROLLED_BACK.value,
                    result=result,
                )
            except Exception as e:
                logger.warning(f"Failed to persist rollback to PostgreSQL: {e}")

        return audit_result