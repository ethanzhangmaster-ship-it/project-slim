"""E9.7: Prediction Tracker — Records and retrieves E9.6 prediction snapshots.

Saves frozen prediction records so the system can later compare
predicted vs actual performance.

Usage:
    tracker = PredictionTracker()
    tracker.load_predictions("output/creative_matching/creative_prediction.json")
    tracker.save_history("output/creative_learning/prediction_history.json")
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_ops.creative_learning.schemas import PredictionRecord


class PredictionTracker:
    """Records and manages prediction history."""

    def __init__(self) -> None:
        self._records: list[PredictionRecord] = []
        self._records_by_id: dict[str, PredictionRecord] = {}

    # ── Loading ────────────────────────────────────────────

    def load_predictions(self, path: str | Path) -> int:
        """Load E9.6 creative_prediction.json and create records.

        Returns: number of records created.
        """
        p = Path(path)
        if not p.exists():
            return 0

        with open(p, 'r', encoding='utf-8') as f:
            predictions = json.load(f)

        timestamp = datetime.now(timezone.utc).isoformat()

        self._records = []
        for pred in predictions:
            record = PredictionRecord(
                creative_id=pred.get("creative_id", ""),
                creative_genome_name=pred.get("creative_genome_name", ""),
                prediction_time=timestamp,
                archetype_prediction={
                    arch: detail.get("adjusted_probability", 0)
                    for arch, detail in pred.get("prediction", {}).items()
                },
                predicted_metrics={
                    "ltv": pred.get("expected", {}).get("ltv", 0),
                    "d30_retention": pred.get("expected", {}).get("d30_retention", 0),
                    "payer_rate": pred.get("expected", {}).get("payer_rate", 0),
                    "iap_potential": pred.get("expected", {}).get("iap_potential", 0),
                },
                dna_features={
                    "features": pred.get("dna_features", {}).get("features", {}),
                    "source_dna": pred.get("dna_features", {}).get("source_dna", {}),
                },
            )
            self._records.append(record)
            self._records_by_id[record.creative_id] = record

        return len(self._records)

    def add_record(self, record: PredictionRecord) -> None:
        """Add a single prediction record."""
        self._records.append(record)
        self._records_by_id[record.creative_id] = record

    # ── Saving ─────────────────────────────────────────────

    def save_history(self, path: str | Path) -> str:
        """Save prediction history to JSON.

        → output/creative_learning/prediction_history.json
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        data = [r.to_dict() for r in self._records]
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return str(p)

    # ── Queries ────────────────────────────────────────────

    def get_record(self, creative_id: str) -> PredictionRecord | None:
        return self._records_by_id.get(creative_id)

    def get_predicted_archetype(self, creative_id: str, archetype: str) -> float:
        record = self._records_by_id.get(creative_id)
        if record:
            return record.archetype_prediction.get(archetype, 0.0)
        return 0.0

    def get_predicted_metric(self, creative_id: str, metric: str) -> float:
        record = self._records_by_id.get(creative_id)
        if record:
            return record.predicted_metrics.get(metric, 0.0)
        return 0.0

    @property
    def records(self) -> list[PredictionRecord]:
        return self._records

    @property
    def creative_ids(self) -> list[str]:
        return list(self._records_by_id.keys())

    def get_summary(self) -> dict[str, Any]:
        if not self._records:
            return {"status": "empty", "total_records": 0}

        avg_ltv = sum(r.predicted_metrics.get("ltv", 0) for r in self._records) / len(self._records)
        avg_payer = sum(r.predicted_metrics.get("payer_rate", 0) for r in self._records) / len(self._records)

        return {
            "total_records": len(self._records),
            "avg_predicted_ltv": round(avg_ltv, 2),
            "avg_predicted_payer_rate": round(avg_payer, 3),
            "prediction_time": self._records[0].prediction_time if self._records else "",
        }