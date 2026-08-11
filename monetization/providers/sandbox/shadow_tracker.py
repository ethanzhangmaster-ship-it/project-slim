"""
E14.3.4 — Shadow Tracker (prediction vs reality)
=================================================

Shadow mode's whole purpose: BEFORE we let the agent touch production, we
measure how good its predictions actually are, against the real platform,
with zero write risk.

Flow:
    provider (SHADOW) reads current value, refuses to write
        -> tracker.record_proposal(change, provider_result, predicted_metric)
    days later, Reality Engine observes the real metric
        -> tracker.ingest_reality(record_id | change_id, actual_metric)
    promotion gate asks
        -> tracker.mean_error_pct(game, provider) / tracker.ready(...)

Pure in-memory + optional JSONL persistence (append-only, same pattern as the
E14.2 event logger). Stdlib only.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from monetization.providers.models import Change, ProviderResult
from monetization.providers.sandbox.sandbox_models import (
    SHADOW_CLOSED, SHADOW_OPEN, ShadowRecord,
)


class ShadowTracker:
    """Collects shadow proposals and closes them against reality."""

    def __init__(self, persist_path: Optional[str] = None):
        self._records: List[ShadowRecord] = []
        self._by_id: Dict[str, ShadowRecord] = {}
        self._persist_path = persist_path
        if persist_path:
            os.makedirs(os.path.dirname(persist_path) or ".", exist_ok=True)

    # ------------------------------------------------------------------ #
    # record
    # ------------------------------------------------------------------ #
    def record_proposal(self, change: Change, result: ProviderResult,
                        predicted_metric: float) -> ShadowRecord:
        """Store one shadow proposal. `result` must come from a SHADOW-mode
        apply (read-only). We trust but verify: a result that claims a real
        write in shadow is a contract violation and is refused."""
        if result.real_api_called and not result.shadow_read_only:
            raise ValueError(
                "shadow contract violation: write-style real call recorded "
                f"for change {change.change_id}")
        rec = ShadowRecord(
            game_id=change.game_id,
            provider=result.provider or change.provider,
            change_id=change.change_id,
            change_type=change.change_type,
            target=change.target,
            current=result.before,
            proposed=change.new,
            predicted_metric=predicted_metric,
        )
        self._records.append(rec)
        self._by_id[rec.record_id] = rec
        self._persist(rec)
        return rec

    # ------------------------------------------------------------------ #
    # close against reality
    # ------------------------------------------------------------------ #
    def ingest_reality(self, record_or_change_id: str,
                       actual_metric: float) -> Optional[ShadowRecord]:
        """Close a record by record_id or change_id. Returns the closed record
        or None if not found / already closed."""
        rec = self._by_id.get(record_or_change_id)
        if rec is None:
            for r in self._records:
                if r.change_id == record_or_change_id:
                    rec = r
                    break
        if rec is None or rec.status == SHADOW_CLOSED:
            return None
        rec.close(actual_metric)
        self._persist(rec)
        return rec

    # ------------------------------------------------------------------ #
    # queries (promotion gate inputs)
    # ------------------------------------------------------------------ #
    def records(self, game_id: str = "", provider: str = "",
                status: str = "") -> List[ShadowRecord]:
        out = self._records
        if game_id:
            out = [r for r in out if r.game_id == game_id]
        if provider:
            out = [r for r in out if r.provider == provider]
        if status:
            out = [r for r in out if r.status == status]
        return list(out)

    def open_count(self, game_id: str = "", provider: str = "") -> int:
        return len(self.records(game_id, provider, SHADOW_OPEN))

    def closed_count(self, game_id: str = "", provider: str = "") -> int:
        return len(self.records(game_id, provider, SHADOW_CLOSED))

    def mean_error_pct(self, game_id: str = "",
                       provider: str = "") -> Optional[float]:
        closed = self.records(game_id, provider, SHADOW_CLOSED)
        errs = [r.error_pct for r in closed if r.error_pct is not None]
        if not errs:
            return None
        return sum(errs) / len(errs)

    def ready(self, game_id: str, provider: str,
              min_closed: int, max_error_pct: float) -> bool:
        """Promotion-gate check: enough closed records AND accurate enough."""
        if self.closed_count(game_id, provider) < min_closed:
            return False
        err = self.mean_error_pct(game_id, provider)
        return err is not None and err <= max_error_pct

    # ------------------------------------------------------------------ #
    def _persist(self, rec: ShadowRecord) -> None:
        if not self._persist_path:
            return
        with open(self._persist_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")


__all__ = ["ShadowTracker"]
