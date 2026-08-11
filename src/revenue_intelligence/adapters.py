"""
E16.1 — Adapters (real-infrastructure bridges)

Thin, *lazy* adapters that connect the Revenue Intelligence Agent to the
existing LaunchForge reality layer without hard dependencies:

* ``reality_snapshot_to_revenue_snapshot`` — collapse a
  ``monetization.reality`` ``RealitySnapshot`` (per-platform segments) into one
  ``RevenueSnapshot`` the agent understands.
* ``RealityFactRevenueSource`` — implements ``RevenueDataSource`` over a
  prebuilt ``RevenueSnapshot`` (or a ``RealitySnapshot``).
* ``OperationRecordPatternMemory`` — implements ``PatternMemory`` over the
  *real* operation history (``operation/memory`` ``OperationRecord``), giving
  E16.1 a genuine E13.4 Growth-Memory back instead of a stub.

All heavy imports are deferred so the agent's core stays import-safe and
testable in isolation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    PatternMatch,
    RevenueAction,
    RevenueDataSource,
    RevenueSnapshot,
)


# --------------------------------------------------------------------------- #
# Reality bridge
# --------------------------------------------------------------------------- #
def reality_snapshot_to_revenue_snapshot(
    rs: Any, date: Optional[str] = None
) -> RevenueSnapshot:
    """Aggregate a ``monetization.reality`` ``RealitySnapshot`` into one fact.

    Segments are per-(platform, country) slices; we sum revenue/spend and
    DAU-weight the rate metrics (retention, payer conversion).
    """
    segs = getattr(rs, "segments", []) or []
    game_id = getattr(rs, "game_id", "unknown")
    if not segs:
        return RevenueSnapshot(game_id=game_id, date=date or "aggregated")

    total_iap = sum(s.iap_revenue for s in segs)
    total_ad = sum(s.ad_revenue for s in segs)
    total_spend = sum(s.spend for s in segs)
    total_dau = sum(s.dau for s in segs)

    rev = total_iap + total_ad

    def _wavg(attr: str) -> float:
        num = sum(getattr(s, attr, 0.0) * s.dau for s in segs if s.dau)
        return (num / total_dau) if total_dau else 0.0

    payer_conv = _wavg("payer_conversion")
    payer_count = int(round(total_dau * payer_conv)) if total_dau else 0
    arppu = (total_iap / payer_count) if payer_count else 0.0
    roas = (rev / total_spend) if total_spend else 0.0

    return RevenueSnapshot(
        game_id=game_id,
        date=date or getattr(rs, "generated_at", "aggregated") or "aggregated",
        revenue_total=round(rev, 4),
        iap_revenue=round(total_iap, 4),
        ad_revenue=round(total_ad, 4),
        spend=round(total_spend, 4),
        roas=round(roas, 4),
        payer_count=payer_count,
        payer_conversion=round(payer_conv, 4),
        arppu=round(arppu, 4),
        dau=int(total_dau),
        retention_d1=round(_wavg("d1"), 4),
        retention_d7=round(_wavg("d7"), 4),
        retention_d30=round(_wavg("d30"), 4),
    )


class RealityFactRevenueSource:
    """``RevenueDataSource`` backed by an already-built ``RevenueSnapshot``.

    Use ``reality_snapshot_to_revenue_snapshot`` to feed a real
    ``RealitySnapshot`` if you have one, or pass a ``RevenueSnapshot``
    directly (e.g. from a data warehouse query).
    """

    def __init__(
        self,
        snapshot: Optional[RevenueSnapshot] = None,
        reality_snapshot: Optional[Any] = None,
        date: Optional[str] = None,
    ):
        if reality_snapshot is not None:
            self._snap = reality_snapshot_to_revenue_snapshot(
                reality_snapshot, date=date
            )
        elif snapshot is not None:
            self._snap = snapshot
        else:
            raise ValueError("provide snapshot or reality_snapshot")

    def load_snapshot(self, game_id: str, period: str) -> RevenueSnapshot:
        return self._snap


# --------------------------------------------------------------------------- #
# E13.4 Growth Memory bridge (real operation history)
# --------------------------------------------------------------------------- #
# Map known operation verbs / tags to a recommended RevenueAction.
_OP_TO_ACTION = {
    "raise_bid_floor": RevenueAction.INCREASE_UA_BUDGET,
    "increase_bid": RevenueAction.INCREASE_UA_BUDGET,
    "scale_ua": RevenueAction.INCREASE_UA_BUDGET,
    "lower_bid": RevenueAction.DECREASE_UA_BUDGET,
    "decrease_bid": RevenueAction.DECREASE_UA_BUDGET,
    "cut_ua": RevenueAction.DECREASE_UA_BUDGET,
    "create_offer": RevenueAction.CREATE_OFFER,
    "new_offer": RevenueAction.CREATE_OFFER,
    "modify_price": RevenueAction.MODIFY_PRICE,
    "price_test": RevenueAction.MODIFY_PRICE,
    "investigate_retention": RevenueAction.INVESTIGATE_RETENTION,
    "retention_push": RevenueAction.INVESTIGATE_RETENTION,
    "rollback_version": RevenueAction.ROLLBACK_VERSION,
    "revert_build": RevenueAction.ROLLBACK_VERSION,
    "scale_feature": RevenueAction.SCALE_FEATURE,
}

_TAG_TO_ACTION = {
    "profitable": RevenueAction.INCREASE_UA_BUDGET,
    "scale": RevenueAction.SCALE_FEATURE,
    "retention_risk": RevenueAction.INVESTIGATE_RETENTION,
    "price_drop": RevenueAction.MODIFY_PRICE,
}


class OperationRecordPatternMemory:
    """``PatternMemory`` over the real ``operation/memory`` ``OperationRecord`` log.

    Each historical monetization operation becomes a candidate precedent. The
    agent queries it the same way it would query the full E13.4 Growth Memory.
    """

    def __init__(self, path: str):
        self.path = Path(path)
        self._OperationRecord = self._lazy_record_cls()

    # ------------------------------------------------------------------ #
    @staticmethod
    def _lazy_record_cls():
        try:
            # local import keeps the core import-safe
            from operation.memory.models import OperationRecord  # type: ignore

            return OperationRecord
        except Exception:  # pragma: no cover - fallback only
            return None

    def _load(self) -> List[Any]:
        if not self.path.exists() or self._OperationRecord is None:
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = self._OperationRecord.from_dict(__import__("json").loads(line))
                out.append(rec)
            except Exception:
                continue
        return out

    def add(self, record: Any) -> None:
        """Persist an OperationRecord (already a dataclass instance)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(__import__("json").dumps(record.to_dict()) + "\n")

    # ------------------------------------------------------------------ #
    def search_similar(
        self, game_id: str, signal: Dict[str, Any], limit: int = 3
    ) -> List[PatternMatch]:
        recs = self._load()
        if game_id:
            recs = [r for r in recs if getattr(r, "game_id", None) == game_id]
        ranked = sorted(
            recs,
            key=lambda r: self._score(r, signal),
            reverse=True,
        )
        return [self._to_pattern(r) for r in ranked[:limit]]

    # ------------------------------------------------------------------ #
    @staticmethod
    def _score(record: Any, signal: Dict[str, Any]) -> float:
        score = float(getattr(record, "confidence", 0.0) or 0.0)
        op = (getattr(record, "operation", "") or "").lower()
        if any(k.lower() in op for k in signal.keys() if isinstance(k, str)):
            score += 0.1
        tags = set(getattr(record, "tags", []) or [])
        sig_tags = {str(v).lower() for v in signal.values() if isinstance(v, str)}
        score += 0.05 * len(tags & sig_tags)
        return score

    @classmethod
    def _to_pattern(cls, record: Any) -> PatternMatch:
        op = (getattr(record, "operation", "") or "").lower()
        tags = [str(t).lower() for t in (getattr(record, "tags", []) or [])]
        action = cls._resolve_action(op, tags)
        metrics = getattr(record, "result_metrics", {}) or {}
        strat = ", ".join(f"{k}={v}" for k, v in metrics.items()) or "no metrics"
        return PatternMatch(
            pattern_id=getattr(record, "record_id", ""),
            description=f"Operation '{getattr(record, 'operation', '')}' "
            f"({getattr(record, 'provider', '')})",
            confidence=float(getattr(record, "confidence", 0.0) or 0.0),
            similar_case=getattr(record, "fingerprint", ""),
            recommended_action=action,
            recommended_strategy=strat,
            source="operation_memory",
        )

    @staticmethod
    def _resolve_action(op: str, tags: List[str]) -> Optional[RevenueAction]:
        for key, action in _OP_TO_ACTION.items():
            if key in op:
                return action
        for key, action in _TAG_TO_ACTION.items():
            if key in tags:
                return action
        return None


__all__ = [
    "reality_snapshot_to_revenue_snapshot",
    "RealityFactRevenueSource",
    "OperationRecordPatternMemory",
]
