from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import copy


class RollbackStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Snapshot:
    snapshot_id: str
    name: str
    state: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = "system"
    description: str = ""


@dataclass
class RollbackRecord:
    rollback_id: str
    from_snapshot: str
    to_snapshot: str = ""
    status: RollbackStatus = RollbackStatus.PENDING
    reason: str = ""
    affected_systems: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    changes: Dict[str, Any] = field(default_factory=dict)


class RollbackSystem:
    def __init__(self):
        self._snapshots: Dict[str, Snapshot] = {}
        self._rollback_history: List[RollbackRecord] = []
        self._current_state: Dict[str, Any] = {}

    def create_snapshot(
        self,
        name: str,
        state: Dict[str, Any],
        description: str = "",
        created_by: str = "system",
    ) -> Snapshot:
        snapshot_id = f"snap_{hash(name + str(datetime.now())) % 100000:05d}"

        snapshot = Snapshot(
            snapshot_id=snapshot_id,
            name=name,
            state=copy.deepcopy(state),
            created_by=created_by,
            description=description,
        )

        self._snapshots[snapshot_id] = snapshot
        self._current_state = copy.deepcopy(state)
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        return self._snapshots.get(snapshot_id)

    def list_snapshots(self, limit: int = 20) -> List[Snapshot]:
        snapshots = sorted(self._snapshots.values(), key=lambda s: s.created_at, reverse=True)
        return snapshots[:limit]

    def rollback_to(
        self,
        snapshot_id: str,
        reason: str = "",
        affected_systems: List[str] = None,
    ) -> RollbackRecord:
        snapshot = self._snapshots.get(snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        rollback_id = f"rollback_{hash(snapshot_id + str(datetime.now())) % 10000:04d}"

        record = RollbackRecord(
            rollback_id=rollback_id,
            from_snapshot=snapshot_id,
            status=RollbackStatus.IN_PROGRESS,
            reason=reason,
            affected_systems=affected_systems or [],
            started_at=datetime.now(),
        )

        try:
            old_state = copy.deepcopy(self._current_state)
            new_state = copy.deepcopy(snapshot.state)

            changes = self._compare_states(old_state, new_state)
            record.changes = changes

            self._current_state = new_state
            record.status = RollbackStatus.COMPLETED
            record.completed_at = datetime.now()

        except Exception as e:
            record.status = RollbackStatus.FAILED
            record.completed_at = datetime.now()
            record.changes = {"error": str(e)}

        self._rollback_history.append(record)
        return record

    def _compare_states(self, old: Dict, new: Dict) -> Dict[str, Any]:
        changes = {}
        all_keys = set(old.keys()) | set(new.keys())

        for key in all_keys:
            old_val = old.get(key)
            new_val = new.get(key)
            if old_val != new_val:
                changes[key] = {"old": old_val, "new": new_val}

        return {
            "changed_keys": list(changes.keys()),
            "total_changes": len(changes),
            "details": changes,
        }

    def get_current_state(self) -> Dict[str, Any]:
        return copy.deepcopy(self._current_state)

    def update_state(self, updates: Dict[str, Any]):
        self._current_state.update(updates)

    def get_rollback_history(self, limit: int = 20) -> List[RollbackRecord]:
        return self._rollback_history[-limit:]

    def compare_snapshots(self, snap1_id: str, snap2_id: str) -> Optional[Dict[str, Any]]:
        snap1 = self._snapshots.get(snap1_id)
        snap2 = self._snapshots.get(snap2_id)
        if not snap1 or not snap2:
            return None
        return self._compare_states(snap1.state, snap2.state)

    def delete_snapshot(self, snapshot_id: str) -> bool:
        if snapshot_id in self._snapshots:
            del self._snapshots[snapshot_id]
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        completed = sum(1 for r in self._rollback_history if r.status == RollbackStatus.COMPLETED)
        failed = sum(1 for r in self._rollback_history if r.status == RollbackStatus.FAILED)
        return {
            "total_snapshots": len(self._snapshots),
            "total_rollbacks": len(self._rollback_history),
            "successful_rollbacks": completed,
            "failed_rollbacks": failed,
            "success_rate": round(completed / len(self._rollback_history) * 100, 1) if self._rollback_history else 0,
        }
