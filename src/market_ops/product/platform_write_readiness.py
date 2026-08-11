"""Hard readiness gate for real advertising-platform writes."""

from __future__ import annotations

import os
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PlatformWriteReadiness:
    ready: bool
    sandbox: bool
    reasons: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def facebook_write_readiness(binding_path: Path) -> PlatformWriteReadiness:
    """Report whether a real Meta write is allowed.

    Existing deployments use ``META_*`` names while the legacy execution
    adapter accepts ``FACEBOOK_*``. Both names are supported, but the gate
    never treats an available credential as authority to write.
    """
    reasons: list[str] = []
    sandbox = os.getenv("FACEBOOK_SANDBOX", "true").lower() not in {"false", "0", "no"}
    token = os.getenv("FACEBOOK_ACCESS_TOKEN") or os.getenv("META_ACCESS_TOKEN")
    account = os.getenv("FACEBOOK_AD_ACCOUNT_ID") or os.getenv("META_AD_ACCOUNT_ID")
    if sandbox:
        reasons.append("FACEBOOK_SANDBOX is enabled")
    if not token:
        reasons.append("Meta access token is missing")
    if not account:
        reasons.append("Meta ad account ID is missing")
    if not binding_path.exists():
        reasons.append("verified campaign binding file is missing")
    else:
        try:
            from .campaign_binding import CampaignBindingIndex

            payload = json.loads(binding_path.read_text(encoding="utf-8"))
            if not isinstance(payload, list) or not payload:
                raise ValueError("binding file is empty")
            CampaignBindingIndex.from_payload(payload)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            reasons.append(f"verified campaign binding file is invalid: {exc}")
    if os.getenv("MARKET_OPS_ALLOW_PLATFORM_WRITES") != "1":
        reasons.append("MARKET_OPS_ALLOW_PLATFORM_WRITES is not explicitly enabled")
    return PlatformWriteReadiness(ready=not reasons, sandbox=sandbox, reasons=reasons)
