"""Controlled one-action production canary with monitoring and rollback evidence."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List


@dataclass
class CanaryResult:
    canary_id: str
    success: bool
    executed: bool = False
    monitored: bool = False
    rolled_back: bool = False
    reason: str = ""
    evidence: List[str] = field(default_factory=list)
    real_api_called: bool = False


class CanaryCoordinator:
    """Never executes more than one approved action for one game."""
    def __init__(self, execute: Callable[..., Dict[str, Any]],
                 monitor: Callable[..., Dict[str, Any]],
                 rollback: Callable[..., Dict[str, Any]], audit_path: str):
        self.execute_fn, self.monitor_fn, self.rollback_fn = execute, monitor, rollback
        self.audit_path = Path(audit_path); self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def run(self, canary_id: str, game_id: str, action: Dict[str, Any], *,
            approval_id: str = "") -> CanaryResult:
        if not canary_id or not game_id or not action or not approval_id:
            result = CanaryResult(canary_id, False, reason="canary requires id, game, action and approval")
            self._audit(result); return result
        if self._already_completed(canary_id):
            result = CanaryResult(canary_id, False, reason="canary id already used")
            self._audit(result); return result
        result = CanaryResult(canary_id, False)
        try:
            executed = dict(self.execute_fn(game_id=game_id, action=dict(action), approval_id=approval_id) or {})
            result.executed = bool(executed.get("success", False))
            result.real_api_called = bool(executed.get("real_api_called", False))
            result.evidence.append(str(executed.get("evidence_ref", "execution")))
            if not result.executed:
                result.reason = "execution failed"; self._audit(result); return result
            observed = dict(self.monitor_fn(game_id=game_id, action=dict(action), execution=executed) or {})
            result.monitored = True; result.evidence.append(str(observed.get("evidence_ref", "monitor")))
            if bool(observed.get("healthy", False)):
                result.success = True; result.reason = "canary healthy"
                self._audit(result); return result
            rolled = dict(self.rollback_fn(game_id=game_id, action=dict(action),
                                           approval_id=approval_id, execution=executed) or {})
            result.rolled_back = bool(rolled.get("success", False))
            result.evidence.append(str(rolled.get("evidence_ref", "rollback")))
            result.reason = "monitor unhealthy; rollback " + ("succeeded" if result.rolled_back else "failed")
            self._audit(result); return result
        except Exception as exc:
            result.reason = f"canary error: {type(exc).__name__}"
            self._audit(result); return result

    def _audit(self, result):
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result.__dict__, ensure_ascii=False) + "\n")

    def _already_completed(self, canary_id):
        if not self.audit_path.exists(): return False
        for line in self.audit_path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                if row.get("canary_id") == canary_id and row.get("executed"):
                    return True
            except json.JSONDecodeError:
                continue
        return False


__all__ = ["CanaryResult", "CanaryCoordinator"]
