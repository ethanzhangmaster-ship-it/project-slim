"""V4.0: Adjust Adapter — wraps existing Adjust data.

Bridges Adjust app event data into the Creative Repository.
Reuses existing unified_state_builder.py and creative_id_mapping.
"""

from __future__ import annotations

from typing import Any


class AdjustAdapter:
    """Adapter for Adjust data → Creative Repository.

    Reuses existing UnifiedStateBuilder and creative_id_mapping.
    Does NOT reimplement Adjust API calls.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path

    def extract_adjust_data(self, adjust_record: dict[str, Any]) -> dict[str, Any]:
        """Extract standardized Adjust data from record.

        Compatible with existing unified_state format.
        """
        return {
            "creative_id": adjust_record.get("adjust_creative_id", ""),
            "facebook_creative_id": adjust_record.get("facebook_creative_id", ""),
            "installs": int(adjust_record.get("installs", 0)),
            "purchases": int(adjust_record.get("purchases", 0)),
            "purchase_value": float(adjust_record.get("purchase_value", 0)),
            "p04_events": int(adjust_record.get("p04_events", 0)),
            "tutorial_complete": int(adjust_record.get("tutorial_complete", 0)),
            "level_10_complete": int(adjust_record.get("level_10_complete", 0)),
            "session_time": float(adjust_record.get("session_time", 0)),
            "roas_d1": float(adjust_record.get("roas_d1", 0)),
            "roas_d7": float(adjust_record.get("roas_d7", 0)),
            "roas_d30": float(adjust_record.get("roas_d30", 0)),
            "ltv_d30": float(adjust_record.get("ltv_d30", 0)),
            "ltv_d90": float(adjust_record.get("ltv_d90", 0)),
            "retention_d1": float(adjust_record.get("retention_d1", 0)),
            "retention_d7": float(adjust_record.get("retention_d7", 0)),
            "arpu": float(adjust_record.get("arpu", 0)),
            "ad_revenue": float(adjust_record.get("ad_revenue", 0)),
        }

    @property
    def available(self) -> bool:
        return bool(self._db_path)