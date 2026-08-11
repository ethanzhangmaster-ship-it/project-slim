"""E13.5 — Release Agent (staged rollout controller).

Drives a new version from 5% -> 20% -> 50% -> 100% on the production track
using Google Play's ``userFraction`` rollout, gated by health metrics and an
observation window. Every real write goes through ``PlayConnector`` so the
three-tier gate + RELEASE unlock are inherited automatically — this agent
NEVER talks to the API directly.

Lean rule: pure Python, deterministic, JSONL state, no LLM.

Safety model:
  * It will NOT advance unless the observation window has elapsed AND the
    health gates pass. If metrics are unavailable and ``require_metrics`` is
    True, it HOLDS (never advances blind).
  * It HALTS (userFraction -> 0) the moment a gate is violated.
  * It never creates a release or uploads a binary; it only moves the
    rollout fraction of an already-published version.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from operation.publishing_factory.play_runtime.connector import PlayConnector
from operation.publishing_factory.play_runtime.models import (
    BlastRadius, GateStage, PlayResult,
)

try:  # EP0.11.4 central audit (optional; no-op when not injected)
    from audit.integration import FlowAuditor
except ImportError:  # pragma: no cover - audit package not on path
    FlowAuditor = None  # type: ignore


# Default staged-rollout ladder (Google Play supported fractions).
DEFAULT_STAGES: tuple = (0.05, 0.20, 0.50, 1.00)


@dataclass
class ReleasePolicy:
    """Tunable rollout policy. Defaults are conservative."""
    stages: tuple = DEFAULT_STAGES
    observe_hours: int = 48          # wait this long between stage advances
    require_metrics: bool = True     # HOLD (never advance) if metrics missing
    # health gates (percent unless noted)
    max_crash_rate: float = 1.0      # %
    max_anr_rate: float = 0.5        # %
    min_d1_retention: float = 0.0    # 0 == do not gate on retention


class ReleaseAgent:
    """Policy-driven staged rollout controller over a PlayConnector."""

    def __init__(self,
                 connector: PlayConnector,
                 policy: Optional[ReleasePolicy] = None,
                 state_path: Optional[str] = None,
                 metrics_provider: Optional[Callable[[str], Optional[Dict]]] = None,
                 auditor: Optional["FlowAuditor"] = None):
        self.connector = connector
        self.policy = policy or ReleasePolicy()
        self.state_path = Path(state_path or "data/play_runtime/release_state.json")
        self.metrics_provider = metrics_provider  # pkg -> metrics dict | None
        # EP0.11.4: central audit trail (release flow:
        # decision -> approval -> release_action -> result). No-op when None.
        self.auditor = auditor

    def _audit_decision(self, package: str, decision: Dict[str, Any]) -> Optional[str]:
        if self.auditor is None:
            return None
        return self.auditor.release_decision(
            package=package,
            recommendation=str(decision.get("recommendation")),
            reason=str(decision.get("reason", "")),
            inputs={k: decision.get(k) for k in
                    ("track_fraction", "stage_index", "next_fraction",
                     "healthy", "window_elapsed")},
        )

    def _audit_result(self, decision_id: Optional[str], package: str,
                      res: PlayResult) -> None:
        if self.auditor is None or decision_id is None:
            return
        self.auditor.release_result(
            decision_id=decision_id, package=package, op=res.op,
            ok=res.ok, real_api_called=res.real_api_called,
            detail=res.detail or "")

    # ------------------------------------------------------------------ #
    # state persistence
    def _load_state(self) -> Dict[str, Any]:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_state(self, state: Dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    def _state_for(self, package: str) -> Dict[str, Any]:
        s = self._load_state().get(package) or {}
        return {
            "stage_index": int(s.get("stage_index", -1)),
            "last_advance_at": s.get("last_advance_at"),
            "status": s.get("status", "unknown"),
            "track": s.get("track", "production"),
        }

    def _record(self, package: str, **fields) -> None:
        state = self._load_state()
        cur = state.get(package, {})
        cur.update(fields)
        state[package] = cur
        self._save_state(state)

    # ------------------------------------------------------------------ #
    # track reading
    def get_track(self, package: str) -> Optional[Dict]:
        res = self.connector.get_track_status(package)
        if not res.ok:
            return None
        return res.data or {}

    # ------------------------------------------------------------------ #
    # decision logic
    def _stage_index_of(self, fraction: float) -> int:
        """Return the index in policy.stages closest to ``fraction``."""
        for i, f in enumerate(self.policy.stages):
            if abs(f - fraction) < 1e-6:
                return i
        # not on a ladder rung (e.g. arbitrary fraction) -> nearest lower
        best, best_i = -1.0, -1
        for i, f in enumerate(self.policy.stages):
            if f <= fraction + 1e-6 and f > best:
                best, best_i = f, i
        return best_i

    @staticmethod
    def _now_iso(now: Optional[datetime] = None) -> str:
        return (now or datetime.now(timezone.utc)).isoformat()

    def _window_elapsed(self, package: str, now: datetime) -> bool:
        st = self._state_for(package)
        last = st.get("last_advance_at") if isinstance(st, dict) else None
        if not last:
            return True  # first advance: no observation window yet
        try:
            last_dt = datetime.fromisoformat(last)
        except (ValueError, TypeError):
            return True
        elapsed_h = (now - last_dt).total_seconds() / 3600.0
        return elapsed_h >= self.policy.observe_hours

    def _healthy(self, metrics: Optional[Dict]) -> tuple:
        """(healthy: bool, reason: str)."""
        if metrics is None:
            if self.policy.require_metrics:
                return False, "no metrics available (require_metrics=True -> HOLD)"
            return True, "no metrics but require_metrics disabled"
        crash = float(metrics.get("crash_rate", 0.0) or 0.0)
        anr = float(metrics.get("anr_rate", 0.0) or 0.0)
        d1 = float(metrics.get("d1_retention", 0.0) or 0.0)
        if crash > self.policy.max_crash_rate:
            return False, f"crash_rate {crash:.2f}% > {self.policy.max_crash_rate:.2f}%"
        if anr > self.policy.max_anr_rate:
            return False, f"anr_rate {anr:.2f}% > {self.policy.max_anr_rate:.2f}%"
        if self.policy.min_d1_retention > 0 and d1 < self.policy.min_d1_retention:
            return False, (f"d1_retention {d1:.3f} < "
                           f"{self.policy.min_d1_retention:.3f}")
        return True, "all gates passed"

    def evaluate(self, package: str,
                 metrics: Optional[Dict] = None,
                 now: Optional[datetime] = None) -> Dict[str, Any]:
        """Decide the next action for ``package`` without writing anything.

        Returns a recommendation dict:
          recommendation in {not_in_rollout, released, advance, hold, halt}
        """
        now = now or datetime.now(timezone.utc)
        track = self.get_track(package)
        if not track:
            return {"package": package, "recommendation": "not_in_rollout",
                    "reason": "track unreadable / app not found",
                    "track_fraction": None, "stage_index": -1,
                    "next_fraction": None, "healthy": None,
                    "window_elapsed": None}
        status = (track.get("status") or "").lower()
        fraction = float(track.get("user_fraction") or 0.0)
        if status == "empty" or fraction <= 0.0:
            return {"package": package, "recommendation": "not_in_rollout",
                    "reason": "no active rollout on production",
                    "track_fraction": fraction, "stage_index": -1,
                    "next_fraction": None, "healthy": None,
                    "window_elapsed": None}
        if abs(fraction - 1.0) < 1e-6 or status == "completed":
            return {"package": package, "recommendation": "released",
                    "reason": "already at 100% (fully rolled out)",
                    "track_fraction": fraction, "stage_index": len(self.policy.stages) - 1,
                    "next_fraction": None, "healthy": None,
                    "window_elapsed": None}
        if status == "halted":
            return {"package": package, "recommendation": "halt",
                    "reason": "rollout already halted; awaiting manual review",
                    "track_fraction": fraction,
                    "stage_index": self._stage_index_of(fraction),
                    "next_fraction": None, "healthy": None,
                    "window_elapsed": None}

        idx = self._stage_index_of(fraction)

        # Missing metrics: cannot safely decide -> HOLD (never advance blind).
        if metrics is None:
            if self.policy.require_metrics:
                return {"package": package, "recommendation": "hold",
                        "reason": "metrics unavailable (require_metrics=True -> HOLD)",
                        "track_fraction": fraction, "stage_index": idx,
                        "next_fraction": None, "healthy": None,
                        "window_elapsed": None}
            healthy, h_reason = True, "no metrics; require_metrics disabled"
        else:
            healthy, h_reason = self._healthy(metrics)
            if not healthy:
                return {"package": package, "recommendation": "halt",
                        "reason": f"health gate violated: {h_reason}",
                        "track_fraction": fraction, "stage_index": idx,
                        "next_fraction": None, "healthy": False,
                        "window_elapsed": None}

        window = self._window_elapsed(package, now)
        if not window:
            return {"package": package, "recommendation": "hold",
                    "reason": f"observing; window {self.policy.observe_hours}h not elapsed",
                    "track_fraction": fraction, "stage_index": idx,
                    "next_fraction": None, "healthy": True,
                    "window_elapsed": False}
        if idx < len(self.policy.stages) - 1:
            next_f = self.policy.stages[idx + 1]
            return {"package": package, "recommendation": "advance",
                    "reason": f"healthy + window elapsed -> advance to {int(next_f*100)}%",
                    "track_fraction": fraction, "stage_index": idx,
                    "next_fraction": next_f, "healthy": True,
                    "window_elapsed": True}
        return {"package": package, "recommendation": "released",
                "reason": "at final stage",
                "track_fraction": fraction, "stage_index": idx,
                "next_fraction": None, "healthy": True,
                "window_elapsed": True}

    # ------------------------------------------------------------------ #
    # actions (all gated by the connector)
    def advance(self, package: str, *, apply: bool = False,
                metrics: Optional[Dict] = None,
                now: Optional[datetime] = None) -> PlayResult:
        now = now or datetime.now(timezone.utc)
        decision = self.evaluate(package, metrics=metrics, now=now)
        decision_id = self._audit_decision(package, decision)
        if decision["recommendation"] != "advance":
            res = PlayResult(
                op="set_rollout", package_name=package,
                radius=BlastRadius.RELEASE, stage=GateStage.BLOCKED,
                real_api_called=False, ok=False,
                detail=f"refused advance: {decision['reason']}")
            if self.auditor is not None and decision_id is not None:
                self.auditor.approval(decision_id, approver="release_gate",
                                      approved=False,
                                      reason=str(decision["reason"]))
                self._audit_result(decision_id, package, res)
            return res
        next_f = decision["next_fraction"]
        if self.auditor is not None and decision_id is not None:
            self.auditor.approval(decision_id, approver="release_gate",
                                  approved=True,
                                  reason=f"advance to {next_f}")
        res = self.connector.set_rollout(
            package, "production", next_f, apply=apply)
        if res.ok and res.stage == GateStage.EXECUTE:
            self._record(package, stage_index=decision["stage_index"] + 1,
                         last_advance_at=self._now_iso(now),
                         status="rolling", track="production")
        self._audit_result(decision_id, package, res)
        return res

    def halt(self, package: str, *, apply: bool = False) -> PlayResult:
        decision_id = None
        if self.auditor is not None:
            decision_id = self.auditor.release_decision(
                package=package, recommendation="halt",
                reason="halt requested (health gate or manual)")
            self.auditor.approval(decision_id, approver="release_gate",
                                  approved=True, reason="halt is always allowed")
        res = self.connector.halt_rollout(package, "production", apply=apply)
        if res.ok and res.stage == GateStage.EXECUTE:
            self._record(package, status="halted", track="production")
        self._audit_result(decision_id, package, res)
        return res

    # ------------------------------------------------------------------ #
    # E15.2 decision execution (Reality -> Decision -> Execution)
    def execute_decision(self, decision: Any, *, apply: bool = False,
                         metrics: Optional[Dict] = None,
                         snapshot: Optional[Any] = None) -> PlayResult:
        """Execute a ``PlayDecision`` produced by the Play Decision Engine.

        Mapping (everything still flows through the connector gate, so the
        three-tier gate + RELEASE unlock are inherited automatically):
          * INCREASE_ROLLOUT -> :meth:`advance`
          * HALT_RELEASE     -> :meth:`halt`
          * HOLD_ROLLOUT / anything else -> explicit no-op (recorded)

        ``snapshot`` (a PlayRealitySnapshot) can stand in for ``metrics``:
        its crash/anr/d1 fields are converted to the metrics dict the
        advance health-gate consumes.
        """
        action = getattr(decision, "action", None)
        action_value = getattr(action, "value", str(action))
        package = getattr(decision, "package_name", "")

        if metrics is None and snapshot is not None:
            metrics = {
                "crash_rate": getattr(snapshot, "crash_rate", None),
                "anr_rate": getattr(snapshot, "anr_rate", None),
                "d1_retention": getattr(snapshot, "d1_retention", None),
            }

        if action_value == "increase_rollout":
            return self.advance(package, apply=apply, metrics=metrics)
        if action_value == "halt_release":
            return self.halt(package, apply=apply)

        # HOLD_ROLLOUT and non-release actions are a deliberate no-op here.
        return PlayResult(
            op="execute_decision", package_name=package,
            radius=BlastRadius.READ, stage=GateStage.RECOMMEND,
            real_api_called=False, ok=True,
            detail=(f"no-op for action={action_value}: "
                    f"{getattr(decision, 'reason', '')}"))

    # ------------------------------------------------------------------ #
    # daily sweep
    def run_daily(self, packages: List[str], *,
                  apply: bool = False,
                  now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Evaluate every package; act (advance/halt) only when ``apply``.

        Returns one recommendation dict per package (with the executed
        PlayResult attached when ``apply`` is True). The connector's own
        gate still enforces RELEASE unlock, so even ``apply=True`` is safe
        against an unlocked connector.
        """
        now = now or datetime.now(timezone.utc)
        out: List[Dict[str, Any]] = []
        for pkg in packages:
            metrics = self.metrics_provider(pkg) if self.metrics_provider else None
            decision = self.evaluate(pkg, metrics=metrics, now=now)
            rec = decision["recommendation"]
            executed: Optional[PlayResult] = None
            if apply and rec == "advance":
                executed = self.advance(pkg, apply=True, metrics=metrics, now=now)
                rec = ("advanced" if executed.ok else "advance_failed")
            elif apply and rec == "halt":
                executed = self.halt(pkg, apply=True)
            else:
                # advance()/halt() audit themselves; audit the passive
                # recommendations (hold/released/not_in_rollout) here.
                self._audit_decision(pkg, decision)
            out.append({**decision, "action_taken": rec,
                        "executed": (executed.to_dict() if executed else None)})
        return out


__all__ = ["ReleaseAgent", "ReleasePolicy", "DEFAULT_STAGES"]
