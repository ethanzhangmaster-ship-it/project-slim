"""P3.6.4 Memory Governance — deterministic, pure computation."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


OBSOLETE_THRESHOLD = 0.1
GRACE_PERIOD_DAYS = 30
ARCHIVE_AFTER_DAYS = 365
REACTIVATE_THRESHOLD = 0.3
AUTO_RESOLVE_RATIO = 3.0


class GovernanceAction(str, Enum):
    MARK_OBSOLETE = "mark_obsolete"
    MARK_ARCHIVED = "mark_archived"
    RESOLVE_CONFLICT = "resolve_conflict"
    MERGE_DUPLICATES = "merge_duplicates"


class RecordState(str, Enum):
    ACTIVE = "active"
    CONFLICTED = "conflicted"
    OBSOLETE = "obsolete"
    ARCHIVED = "archived"


@dataclass
class GovernanceRecord:
    governance_id: str
    target_node_id: str
    action: GovernanceAction
    reason: str
    evidence: List[str]
    previous_state: RecordState
    new_state: RecordState
    merged_from: List[str] = field(default_factory=list)
    created_at: str = ""
    requires_ceo_review: bool = False
    real_api_called: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "governance_id": self.governance_id,
            "target_node_id": self.target_node_id,
            "action": self.action.value,
            "reason": self.reason,
            "evidence": list(self.evidence),
            "previous_state": self.previous_state.value,
            "new_state": self.new_state.value,
            "merged_from": list(self.merged_from),
            "created_at": self.created_at,
            "requires_ceo_review": self.requires_ceo_review,
            "real_api_called": False,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GovernanceRecord":
        return cls(
            governance_id=str(data.get("governance_id", "")),
            target_node_id=str(data.get("target_node_id", "")),
            action=GovernanceAction(data.get("action", GovernanceAction.MARK_OBSOLETE.value)),
            reason=str(data.get("reason", "")),
            evidence=list(data.get("evidence") or []),
            previous_state=RecordState(data.get("previous_state", RecordState.ACTIVE.value)),
            new_state=RecordState(data.get("new_state", RecordState.ACTIVE.value)),
            merged_from=list(data.get("merged_from") or []),
            created_at=str(data.get("created_at", "")),
            requires_ceo_review=bool(data.get("requires_ceo_review", False)),
            real_api_called=False,
        )


def _parse(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _days(old: str, now: str) -> float:
    a, b = _parse(old), _parse(now)
    if a is None or b is None:
        return 0.0
    if a.tzinfo is None:
        a = a.replace(tzinfo=timezone.utc)
    if b.tzinfo is None:
        b = b.replace(tzinfo=timezone.utc)
    return max(0.0, (b - a).total_seconds() / 86400.0)


def _rid(*parts: str) -> str:
    raw = "|".join(parts).encode("utf-8")
    return "gov_" + hashlib.sha256(raw).hexdigest()[:16]


def _node_id(record: Dict[str, Any]) -> str:
    if record.get("node_id"):
        return str(record["node_id"])
    if record.get("record_id"):
        return f"ceo_decision:{record['record_id']}"
    if record.get("insight_id"):
        return f"strategic_insight:{record['insight_id']}"
    return ""


def _direction(record: Dict[str, Any]) -> Optional[bool]:
    outcome = record.get("outcome") or {}
    if "success" in outcome:
        return bool(outcome["success"])
    if "success_rate" in outcome:
        return float(outcome["success_rate"] or 0.0) >= 0.5
    return None


class GovernanceEngine:
    """Produce append-only governance declarations; never mutates inputs."""

    def __init__(
        self,
        obsolete_threshold: float = OBSOLETE_THRESHOLD,
        grace_period_days: int = GRACE_PERIOD_DAYS,
        archive_after_days: int = ARCHIVE_AFTER_DAYS,
        reactivate_threshold: float = REACTIVATE_THRESHOLD,
        auto_resolve_ratio: float = AUTO_RESOLVE_RATIO,
    ) -> None:
        self.obsolete_threshold = float(obsolete_threshold)
        self.grace_period_days = int(grace_period_days)
        self.archive_after_days = int(archive_after_days)
        self.reactivate_threshold = float(reactivate_threshold)
        self.auto_resolve_ratio = float(auto_resolve_ratio)

    @property
    def real_api_called(self) -> bool:
        return False

    def run(
        self,
        ceo_records: Optional[List[Dict[str, Any]]] = None,
        strategic_insights: Optional[List[Dict[str, Any]]] = None,
        conflicts: Optional[List[Any]] = None,
        as_of: str = "",
        states: Optional[Dict[str, str]] = None,
        qualities: Optional[Dict[str, float]] = None,
        state_changed_at: Optional[Dict[str, str]] = None,
    ) -> List[GovernanceRecord]:
        try:
            return self._run(
                list(ceo_records or []), list(strategic_insights or []),
                list(conflicts or []), as_of, dict(states or {}),
                dict(qualities or {}), dict(state_changed_at or {}),
            )
        except Exception:
            return []

    def _run(self, records, insights, conflicts, as_of, states, qualities, changed):
        now = as_of or datetime.now(timezone.utc).isoformat()
        out: List[GovernanceRecord] = []

        # Same game + same decision/action + same outcome direction.
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for record in records:
            direction = _direction(record)
            if direction is None:
                continue
            payload = record.get("decision_payload") or {}
            key = f"{record.get('game_id','')}|{record.get('decision_type','')}|{payload.get('action','')}|{int(direction)}"
            groups.setdefault(key, []).append(record)
        for key, members in sorted(groups.items()):
            visible = [m for m in members if states.get(_node_id(m), RecordState.ACTIVE.value) == RecordState.ACTIVE.value]
            if len(visible) < 2:
                continue
            ids = sorted(x for x in (_node_id(m) for m in visible) if x)
            target = ids[0]
            out.append(GovernanceRecord(
                governance_id=_rid("merge", key, now[:10]), target_node_id=target,
                action=GovernanceAction.MERGE_DUPLICATES,
                reason="同一游戏内存在相同决策、动作与结果方向的重复经验，归并为一个审计组。",
                evidence=ids, previous_state=RecordState.ACTIVE,
                new_state=RecordState.ACTIVE, merged_from=ids[1:], created_at=now,
            ))
            for source in ids[1:]:
                out.append(GovernanceRecord(
                    governance_id=_rid(source, GovernanceAction.MARK_OBSOLETE.value),
                    target_node_id=source, action=GovernanceAction.MARK_OBSOLETE,
                    reason="该记录已被同游戏语义重复经验归并。", evidence=[target],
                    previous_state=RecordState.ACTIVE, new_state=RecordState.OBSOLETE,
                    created_at=now,
                ))

        # Quality lifecycle for decisions and strategic insights.
        for record in records + insights:
            target = _node_id(record)
            if not target:
                continue
            state = RecordState(states.get(target, RecordState.ACTIVE.value))
            quality = float(qualities.get(target, record.get("quality", 1.0)) or 0.0)
            since = changed.get(target) or str(record.get("created_at", ""))
            age = _days(since, now)
            if state == RecordState.ARCHIVED:
                continue
            if state == RecordState.OBSOLETE and age >= self.archive_after_days:
                out.append(GovernanceRecord(
                    _rid(target, GovernanceAction.MARK_ARCHIVED.value), target,
                    GovernanceAction.MARK_ARCHIVED, "废弃状态已超过自动归档期限。", [since],
                    state, RecordState.ARCHIVED, created_at=now,
                ))
            elif state == RecordState.OBSOLETE and quality >= self.reactivate_threshold:
                out.append(GovernanceRecord(
                    _rid(target, "reactivate", now[:10]), target,
                    GovernanceAction.RESOLVE_CONFLICT, "新证据使质量恢复到重新激活阈值。",
                    [f"quality={quality:.6f}"], state, RecordState.ACTIVE, created_at=now,
                ))
            elif state in (RecordState.ACTIVE, RecordState.CONFLICTED) and quality < self.obsolete_threshold and age >= self.grace_period_days:
                out.append(GovernanceRecord(
                    _rid(target, GovernanceAction.MARK_OBSOLETE.value), target,
                    GovernanceAction.MARK_OBSOLETE, "质量持续低于废弃阈值并超过宽限期。",
                    [f"quality={quality:.6f}", f"age_days={age:.1f}"], state,
                    RecordState.OBSOLETE, created_at=now,
                ))

        # Hybrid conflict resolution.
        for conflict in conflicts:
            data = conflict.to_dict() if hasattr(conflict, "to_dict") else dict(conflict)
            successes, failures = list(data.get("successes") or []), list(data.get("failures") or [])
            if not successes or not failures:
                continue
            high, low = max(len(successes), len(failures)), min(len(successes), len(failures))
            automatic = high >= self.auto_resolve_ratio * low
            key = str(data.get("key", ""))
            targets = sorted({_node_id(x) for x in successes + failures if _node_id(x)})
            target = targets[0] if targets else f"conflict:{key}"
            out.append(GovernanceRecord(
                _rid("conflict", key, now[:10]), target,
                GovernanceAction.RESOLVE_CONFLICT,
                ("证据量达到自动裁决比例，采用优势结果方向。" if automatic
                 else "证据量不足以自动裁决，需要 CEO 关注。"),
                targets, RecordState.CONFLICTED,
                RecordState.ACTIVE if automatic else RecordState.CONFLICTED,
                created_at=now, requires_ceo_review=not automatic,
            ))
        # One target/action declaration per run.  Merge-driven obsolescence is
        # emitted first and therefore wins over a simultaneous decay candidate.
        unique: Dict[tuple, GovernanceRecord] = {}
        for item in out:
            unique.setdefault((item.target_node_id, item.action.value), item)
        return sorted(unique.values(), key=lambda item: (
            item.action.value, item.target_node_id, item.governance_id
        ))


__all__ = [
    "GovernanceAction", "RecordState", "GovernanceRecord", "GovernanceEngine",
    "OBSOLETE_THRESHOLD", "GRACE_PERIOD_DAYS", "ARCHIVE_AFTER_DAYS",
    "REACTIVATE_THRESHOLD", "AUTO_RESOLVE_RATIO",
]
