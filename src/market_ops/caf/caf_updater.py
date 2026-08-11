"""Update character_schema.json with constrained feature adjustments.

Constraints:
  - clamp features to [0, 1]
  - prevent identity drift (max step per update ≤ 0.05)
  - write version + update_history
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_ops.caf.feature_attribution_engine import compute_feature_deltas

MAX_DELTA_PER_STEP = 0.05
CLAMP_MIN = 0.0
CLAMP_MAX = 1.0


def update_character(
    *,
    schema_path: str | Path | None = None,
    signals: dict[str, float],
    learning_rate: float = 0.05,
) -> dict[str, Any]:
    """Apply one CAF update step.

    Returns the updated character schema dict.
    """
    if schema_path is None:
        schema_path = Path(__file__).parent / "character_schema.json"
    else:
        schema_path = Path(schema_path)

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    features: dict[str, float] = schema.get("features", {})

    attribution = compute_feature_deltas(
        signals=signals, learning_rate=learning_rate
    )
    deltas = attribution.get("feature_deltas", {})

    update_entries: list[dict[str, Any]] = []
    for feat, delta in deltas.items():
        if feat not in features:
            continue
        clamped = max(CLAMP_MIN, min(CLAMP_MAX, delta))
        old = features[feat]
        new = round(max(CLAMP_MIN, min(CLAMP_MAX, old + clamped)), 4)
        features[feat] = new
        update_entries.append({
            "feature": feat,
            "old": old,
            "new": new,
            "delta": clamped,
        })

    schema["features"] = features
    schema["version"] = schema.get("version", 1) + 1
    schema["updated_at"] = datetime.now(timezone.utc).isoformat()
    history = schema.get("update_history", [])
    if not isinstance(history, list):
        history = []
    history.append({
        "version": schema["version"],
        "timestamp": schema["updated_at"],
        "signals": signals,
        "deltas": deltas,
        "changes": update_entries,
    })
    schema["update_history"] = history

    # Write back
    schema_path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return schema
