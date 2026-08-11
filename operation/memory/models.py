"""
E15.2.1 — Operation Memory Models

OperationRecord captures the full lifecycle of a monetization operation:
before → change → after → result, enabling learning over time.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _uid(p: str = "mem") -> str:
    return f"{p}_{uuid.uuid4().hex[:8]}"


@dataclass
class OperationRecord:
    """Immutable record of one monetization operation with before/after snapshots."""

    record_id: str
    game_id: str
    operation: str          # e.g. "raise_bid_floor", "add_waterfall_network"
    provider: str           # e.g. "max", "iap", "admob"
    sandbox: str            # SIMULATION | SHADOW | PRODUCTION

    # Context that influenced the decision
    context: Dict[str, Any] = field(default_factory=dict)
    # {"country": "US", "platform": "android", "format": "reward"}

    # State snapshots
    before_state: Dict[str, Any] = field(default_factory=dict)
    # {"ecpm": 12.5, "revenue_daily": 340.0, "fill_rate": 0.92}
    after_state: Dict[str, Any] = field(default_factory=dict)
    # {"ecpm": 13.8, "revenue_daily": 375.0, "fill_rate": 0.93}

    # Outcome
    result_success: bool = True
    result_metrics: Dict[str, Any] = field(default_factory=dict)
    # {"revenue_change_pct": 10.3, "ecpm_change_pct": 10.4}
    error: Optional[str] = None

    # Learning signal
    confidence: float = 0.0   # 0.0–1.0, how confident we are this was causal
    tags: List[str] = field(default_factory=list)
    # ["profitable", "low_risk", "us_reward"]

    timestamp: float = field(default_factory=time.time)

    @property
    def fingerprint(self) -> str:
        """Deterministic key for dedup: game_id + operation + context."""
        raw = f"{self.game_id}|{self.operation}|{sorted(self.context.items())}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    @property
    def revenue_impact(self) -> Optional[float]:
        """Percentage revenue change from before to after."""
        if "revenue_change_pct" in self.result_metrics:
            return self.result_metrics["revenue_change_pct"]
        b = self.before_state.get("revenue_daily", 0)
        a = self.after_state.get("revenue_daily", 0)
        if b and b > 0:
            return round((a - b) / b * 100, 2)
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "game_id": self.game_id,
            "operation": self.operation,
            "provider": self.provider,
            "sandbox": self.sandbox,
            "context": self.context,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "result_success": self.result_success,
            "result_metrics": self.result_metrics,
            "error": self.error,
            "confidence": self.confidence,
            "tags": self.tags,
            "timestamp": self.timestamp,
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OperationRecord":
        d = dict(d)
        d.pop("fingerprint", None)
        return cls(**d)


def record_factory(
    game_id: str,
    operation: str,
    provider: str,
    sandbox: str = "SIMULATION",
    context: Optional[Dict[str, Any]] = None,
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
    result_success: bool = True,
    result_metrics: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    confidence: float = 0.0,
    tags: Optional[List[str]] = None,
) -> OperationRecord:
    return OperationRecord(
        record_id=_uid("mem"),
        game_id=game_id,
        operation=operation,
        provider=provider,
        sandbox=sandbox,
        context=context or {},
        before_state=before_state or {},
        after_state=after_state or {},
        result_success=result_success,
        result_metrics=result_metrics or {},
        error=error,
        confidence=confidence,
        tags=tags or [],
    )
