"""
E14.5.3 — Alert Engine
========================

Rule-based alerting on top of the FleetHealthReport (E14.5.1) plus optional
external signals (e.g. a revenue-drop measurement from the Reality Engine).

Rules (per spec):
    rollback_rate > 20%      -> CRITICAL  (bad-decision loop)
    provider_health < 40     -> WARNING   (downgrade sandbox to simulation)
    revenue_drop   > 15%     -> CRITICAL  (freeze execution)
    game isolated (crash)    -> CRITICAL  (keep out of fleet)

The engine only *emits* structured Alerts (runtime.alerting.Alert). It never
acts on its own — automatic recovery lives in E14.2's RecoveryManager. This
keeps the observability layer a pure "tell the human" surface.

Output: append-only JSONL at <alerts_dir>/<day_tag>.jsonl.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from monetization.observability.models import FleetHealthReport
from monetization.runtime.alerting import (
    ALERT_CRITICAL, ALERT_WARNING, Alert,
)

# thresholds (tunable)
ROLLBACK_RATE_LIMIT = 0.20
PROVIDER_HEALTH_FLOOR = 40.0
REVENUE_DROP_LIMIT = 15.0


class AlertEngine:
    """Evaluates fleet health + external signals into structured Alerts."""

    def __init__(self, alerts_dir: str = "observability/alerts"):
        self.dir = Path(alerts_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._signals: Dict[str, Dict[str, float]] = {}   # game_id -> {kind: val}
        self._buffer: List[Alert] = []

    # ------------------------------------------------------------------ #
    def record_signal(self, game_id: str, kind: str, value: float) -> None:
        """Feed an external signal (e.g. revenue_drop_pct=18.0)."""
        self._signals.setdefault(game_id, {})[kind] = value

    # ------------------------------------------------------------------ #
    def evaluate(self, fleet: FleetHealthReport) -> List[Alert]:
        out: List[Alert] = []
        for g in fleet.games:
            # 1. rollback_rate > 20%  -> bad-decision loop
            if g.rollback_rate > ROLLBACK_RATE_LIMIT:
                out.append(Alert(
                    ALERT_CRITICAL,
                    f"{g.game_id} rollback_rate {g.rollback_rate:.0%} > "
                    f"{ROLLBACK_RATE_LIMIT:.0%}: bad-decision loop suspected",
                    game=g.game_id, source="alert_engine",
                    meta={"rule": "rollback_rate", "value": g.rollback_rate,
                          "action": "disable_execution_review"}))

            # 2. provider_health < 40 -> downgrade sandbox
            if g.provider_health < PROVIDER_HEALTH_FLOOR:
                out.append(Alert(
                    ALERT_WARNING,
                    f"{g.game_id} provider_health {g.provider_health:.0f} < "
                    f"{PROVIDER_HEALTH_FLOOR:.0f}: downgrade sandbox to simulation",
                    game=g.game_id, source="alert_engine",
                    meta={"rule": "provider_health", "value": g.provider_health,
                          "action": "downgrade_sandbox"}))

            # 3. revenue_drop > 15% -> freeze execution
            sig = self._signals.get(g.game_id, {})
            rev_drop = sig.get("revenue_drop_pct", 0.0)
            if rev_drop > REVENUE_DROP_LIMIT:
                out.append(Alert(
                    ALERT_CRITICAL,
                    f"{g.game_id} revenue dropped {rev_drop:.0f}% > "
                    f"{REVENUE_DROP_LIMIT:.0f}%: freeze execution",
                    game=g.game_id, source="alert_engine",
                    meta={"rule": "revenue_drop", "value": rev_drop,
                          "action": "freeze_execution"}))

            # 4. crash loop / isolated -> keep out of fleet
            if g.status == "isolated":
                out.append(Alert(
                    ALERT_CRITICAL,
                    f"{g.game_id} is isolated (crash loop / degraded): "
                    f"keep out of fleet",
                    game=g.game_id, source="alert_engine",
                    meta={"rule": "crash_loop", "action": "isolate"}))

            # 5. high risk (non-isolated) -> warning for human attention
            if g.risk == "high" and g.status != "isolated":
                out.append(Alert(
                    ALERT_WARNING,
                    f"{g.game_id} risk=high (score {g.score:.0f})",
                    game=g.game_id, source="alert_engine",
                    meta={"rule": "high_risk", "value": g.score}))

        self._buffer.extend(out)
        return out

    # ------------------------------------------------------------------ #
    def flush(self, day_tag: str = "") -> int:
        path = self.dir / f"{day_tag or 'alerts'}.jsonl"
        n = 0
        with path.open("a", encoding="utf-8") as fh:
            for a in self._buffer:
                fh.write(json.dumps(a.to_dict(), ensure_ascii=False) + "\n")
                n += 1
        self._buffer.clear()
        return n


__all__ = ["AlertEngine", "ROLLBACK_RATE_LIMIT",
           "PROVIDER_HEALTH_FLOOR", "REVENUE_DROP_LIMIT"]
