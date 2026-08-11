"""E15.0.1 Audit Store — 审计记录存储与查询.

提供内存存储和持久化接口，支持:
  - 按 game_id 查询
  - 按 agent_id 查询
  - 按时间范围查询
  - 按执行状态查询
  - 统计汇总
  - JSON 导出
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .models import ExecutionStatus, GrowthDecisionAudit


class AuditStore:
    """审计存储 — 管理 GrowthDecisionAudit 记录.

    用法:
        store = AuditStore()
        store.record(audit)
        records = store.get_by_game("P04")
        stats = store.stats()
    """

    def __init__(self, max_records: int = 10000):
        self._records: list[GrowthDecisionAudit] = []
        self._max_records = max_records

    # ── Record ──────────────────────────────────────────────

    def record(self, audit: GrowthDecisionAudit) -> GrowthDecisionAudit:
        """记录一条审计."""
        self._records.append(audit)
        self._trim()
        return audit

    def record_decision(
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
    ) -> GrowthDecisionAudit:
        """便捷方法: 记录一条决策."""
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
        )
        return self.record(audit)

    def update_result(
        self,
        audit_id: str,
        status: ExecutionStatus,
        result: dict[str, Any] | None = None,
        rollback_record_id: str = "",
    ) -> GrowthDecisionAudit | None:
        """更新审计记录的执行结果."""
        for audit in self._records:
            if audit.audit_id == audit_id:
                audit.execution_status = status
                if result:
                    audit.result.update(result)
                if rollback_record_id:
                    audit.rollback_record_id = rollback_record_id
                return audit
        return None

    # ── Query ────────────────────────────────────────────────

    def get_by_id(self, audit_id: str) -> GrowthDecisionAudit | None:
        for a in self._records:
            if a.audit_id == audit_id:
                return a
        return None

    def get_by_game(self, game_id: str) -> list[GrowthDecisionAudit]:
        return [a for a in self._records if a.game_id == game_id]

    def get_by_agent(self, agent_id: str) -> list[GrowthDecisionAudit]:
        return [a for a in self._records if a.agent_id == agent_id]

    def get_by_status(self, status: ExecutionStatus) -> list[GrowthDecisionAudit]:
        return [a for a in self._records if a.execution_status == status]

    def get_by_time_range(
        self,
        start: str,
        end: str | None = None,
    ) -> list[GrowthDecisionAudit]:
        """按时间范围查询 (ISO 8601 格式)."""
        end = end or datetime.now(timezone.utc).isoformat()
        return [
            a for a in self._records
            if start <= a.timestamp <= end
        ]

    def get_by_plan(self, plan_id: str) -> list[GrowthDecisionAudit]:
        return [a for a in self._records if a.plan_id == plan_id]

    def get_by_cycle(self, cycle_id: str) -> list[GrowthDecisionAudit]:
        return [a for a in self._records if a.cycle_id == cycle_id]

    def get_recent(self, n: int = 10) -> list[GrowthDecisionAudit]:
        return self._records[-n:]

    def get_all(self) -> list[GrowthDecisionAudit]:
        return list(self._records)

    def get_needing_attention(self) -> list[GrowthDecisionAudit]:
        return [a for a in self._records if a.needs_attention]

    def get_failed(self) -> list[GrowthDecisionAudit]:
        return [a for a in self._records if a.is_failed]

    def get_rolled_back(self) -> list[GrowthDecisionAudit]:
        return [a for a in self._records if a.was_rolled_back]

    # ── Statistics ───────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """获取审计统计."""
        total = len(self._records)
        if total == 0:
            return {
                "total": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 0.0,
                "by_game": {},
                "by_status": {},
                "avg_confidence": 0.0,
            }

        success = len([a for a in self._records if a.is_success])
        failed = len([a for a in self._records if a.is_failed])
        confidences = [a.confidence for a in self._records if a.confidence > 0]

        by_game: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for a in self._records:
            by_game[a.game_id] = by_game.get(a.game_id, 0) + 1
            by_status[a.execution_status.value] = by_status.get(a.execution_status.value, 0) + 1

        return {
            "total": total,
            "success_count": success,
            "failure_count": failed,
            "success_rate": round(success / total, 4),
            "by_game": by_game,
            "by_status": by_status,
            "avg_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
        }

    def stats_by_game(self, game_id: str) -> dict[str, Any]:
        """按游戏统计."""
        records = self.get_by_game(game_id)
        total = len(records)
        if total == 0:
            return {"game_id": game_id, "total": 0}
        success = len([a for a in records if a.is_success])
        return {
            "game_id": game_id,
            "total": total,
            "success_count": success,
            "success_rate": round(success / total, 4),
        }

    # ── Export ───────────────────────────────────────────────

    def to_dicts(self) -> list[dict[str, Any]]:
        return [a.to_dict() for a in self._records]

    def to_summaries(self) -> list[dict[str, Any]]:
        return [a.to_summary() for a in self._records]

    def export_json(self, filepath: str) -> None:
        """导出为 JSON 文件."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dicts(), f, indent=2, ensure_ascii=False, default=str)

    # ── Maintenance ──────────────────────────────────────────

    def _trim(self) -> None:
        """超出容量时移除最旧记录."""
        while len(self._records) > self._max_records:
            self._records.pop(0)

    def clear(self) -> None:
        self._records.clear()

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self):
        return iter(self._records)