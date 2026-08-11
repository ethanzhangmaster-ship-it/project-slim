"""Extract CAF signals from V1 outputs (image metadata + optional metrics).

Input: per-image metadata JSON + optional metrics JSON
Output: signal dict suitable for feature attribution
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def extract_signals(
    *,
    metadata_path: str | Path,
    metrics: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Extract CAF signals from a single creative's results.

    Args:
        metadata_path: path to the creative metadata JSON
        metrics: optional dict with keys like ctr, cvr, roas, ipm
    """
    import json

    meta = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    creative_id = meta.get("creative_id", "unknown")
    template = meta.get("template", "unknown")
    identity = meta.get("identity") or (
        meta.get("creative_spec", {}).get("identity", "")
    )

    signals: dict[str, float] = {}

    if metrics:
        # Normalise each metric to a 0-1 signal
        if "ctr" in metrics:
            signals["ctr_signal"] = _normalise_signal(metrics["ctr"], ref=0.03, cap=0.15)
        if "cvr" in metrics:
            signals["cvr_signal"] = _normalise_signal(metrics["cvr"], ref=0.05, cap=0.30)
        if "roas" in metrics:
            signals["roas_signal"] = _normalise_signal(metrics["roas"], ref=1.0, cap=3.0)
        if "ipm" in metrics:
            signals["ipm_signal"] = _normalise_signal(metrics["ipm"], ref=1.0, cap=10.0)
    else:
        # No metrics available — return identity-only signal placeholder
        signals["ctr_signal"] = 0.0
        signals["cvr_signal"] = 0.0
        signals["roas_signal"] = 0.0
        signals["ipm_signal"] = 0.0

    return {
        "character_id": identity or "witch_v1",
        "creative_id": creative_id,
        "template": template,
        "signals": signals,
    }


def _normalise_signal(value: float, *, ref: float, cap: float) -> float:
    """Map a raw metric to [0, 1] based on a reference baseline."""
    if value <= 0:
        return 0.0
    ratio = value / max(ref, 1e-6)
    return min(ratio / (cap / ref), 1.0)
