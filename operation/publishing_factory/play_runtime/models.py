"""E13.5 — Play Runtime models.

Pure data classes + enums that describe a Google Play operation and its
blast radius. No I/O here; the connector and audit log consume these.

Lean rule: deterministic, no LLM, JSONL-friendly (everything is str/dict).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class BlastRadius(str, Enum):
    """How destructive / visible a Play operation is.

    Ordered by blast radius. Anything above ``READ`` requires the
    auto-pilot gate; anything at ``RELEASE`` additionally requires an
    explicit ``unlock_release()`` call (the Approval door).
    """
    READ = "read"            # ownership / status / vitals — no mutation
    METADATA = "metadata"    # listing title/desc — reversible text
    TESTERS = "testers"      # closed-track testers — reversible list
    BINARY = "binary"        # AAB upload — reversible-ish, needs build
    RELEASE = "release"      # track promotion / rollout — gated hard


class GateStage(str, Enum):
    """The three-tier execution gate, made explicit per call.

    RECOMMEND  -> SIM: propose only, never call the API
    SIMULATE   -> SHADOW: real READ for verification, writes are previewed
    APPROVE    -> PRODUCTION + auto-pilot unlocked, awaiting release unlock
    EXECUTE    -> PRODUCTION: real write happened
    BLOCKED    -> refused by a safety lock (no API call made)
    """
    RECOMMEND = "recommend"
    SIMULATE = "simulate"
    APPROVE = "approve"
    EXECUTE = "execute"
    BLOCKED = "blocked"


@dataclass
class PlayOperation:
    """One logical Play action, irrespective of execution stage."""
    op: str                       # e.g. "update_listing", "set_rollout"
    package_name: str
    radius: BlastRadius
    payload: Dict[str, Any] = field(default_factory=dict)
    locale: Optional[str] = None
    track: Optional[str] = None   # internal/closed/open/production
    note: str = ""


@dataclass
class PlayResult:
    """Outcome of a PlayOperation after routing through the gate."""
    op: str
    package_name: str
    radius: BlastRadius
    stage: GateStage
    real_api_called: bool = False     # hard lock: False in SIM/SHADOW
    ok: bool = False
    http_status: Optional[int] = None
    error: str = ""
    detail: str = ""
    diagnosis: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op": self.op,
            "package_name": self.package_name,
            "radius": self.radius.value,
            "stage": self.stage.value,
            "real_api_called": self.real_api_called,
            "ok": self.ok,
            "http_status": self.http_status,
            "error": self.error,
            "detail": self.detail,
            "diagnosis": self.diagnosis,
            "data": self.data,
            "at": self.at,
        }


__all__ = ["BlastRadius", "GateStage", "PlayOperation", "PlayResult"]
