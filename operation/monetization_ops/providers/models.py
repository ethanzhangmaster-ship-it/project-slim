"""
E15.2.1 — Monetization Operation Provider Contract

Mirrors E15.1 PublishingProvider pattern.
MonetizationOpChange / OpResult / MonetizationOperationProvider ABC.
Reuses SandboxMode + CredentialRef from monetization/providers/.
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from monetization.providers.models import CredentialRef, SandboxMode


def _uid(p: str = "mo") -> str:
    return f"{p}_{uuid.uuid4().hex[:8]}"


# --------------------------------------------------------------------------- #
# Operations
# --------------------------------------------------------------------------- #
OP_CREATE = "create"
OP_UPDATE = "update"
OP_FETCH = "fetch"
OP_DELETE = "delete"
OP_HEALTH_CHECK = "health_check"

# Ad types
AD_REWARDED = "rewarded_video"
AD_INTERSTITIAL = "interstitial"
AD_BANNER = "banner"

# IAP types
IAP_CONSUMABLE = "consumable"
IAP_NON_CONSUMABLE = "non_consumable"
IAP_SUBSCRIPTION = "subscription"


@dataclass
class AdUnit:
    game_id: str
    platform: str                         # "android" | "ios"
    network: str                          # "max" | "admob" | "levelplay"
    placement: str
    format: str                           # AD_*
    ad_unit_id: str = ""
    status: str = "inactive"              # inactive | active | error

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id, "platform": self.platform,
            "network": self.network, "placement": self.placement,
            "format": self.format, "ad_unit_id": self.ad_unit_id,
            "status": self.status,
        }


@dataclass
class IAPProduct:
    game_id: str
    platform: str
    product_id: str
    product_type: str                      # consumable | non_consumable | subscription
    title: str = ""
    price: float = 0.0
    currency: str = "USD"
    status: str = "inactive"

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id, "platform": self.platform,
            "product_id": self.product_id, "product_type": self.product_type,
            "title": self.title, "price": self.price,
            "currency": self.currency, "status": self.status,
        }


@dataclass
class MonetizationOpChange:
    target: str
    operation: str
    provider: str = ""
    game_id: str = ""
    old: Any = None
    new: Any = None
    sandbox: SandboxMode = SandboxMode.SIMULATION
    credential_ref: Optional[CredentialRef] = None
    change_id: str = field(default_factory=_uid)

    def to_dict(self) -> dict:
        return {
            "target": self.target, "operation": self.operation,
            "provider": self.provider, "game_id": self.game_id,
            "sandbox": self.sandbox.value, "change_id": self.change_id,
        }


@dataclass
class OpResult:
    provider: str
    operation: str
    success: bool
    latency_ms: float = 0.0
    real_api_called: bool = False
    change_id: str = ""
    detail: str = ""
    error: str = ""
    data: Any = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "provider": self.provider, "operation": self.operation,
            "success": self.success, "latency_ms": self.latency_ms,
            "real_api_called": self.real_api_called,
            "change_id": self.change_id, "detail": self.detail,
            "error": self.error, "extra": self.extra,
        }


# --------------------------------------------------------------------------- #
# ABC
# --------------------------------------------------------------------------- #
class MonetizationOperationProvider(ABC):
    name: str = "abstract_mo"

    def __init__(self, sandbox=SandboxMode.SIMULATION,
                 credential_ref=None):
        self.sandbox = sandbox
        self.credential_ref = credential_ref
        self._production_locked = True

    @abstractmethod
    def apply_change(self, change: MonetizationOpChange) -> OpResult: ...

    @abstractmethod
    def rollback_change(self, change: MonetizationOpChange) -> OpResult: ...

    @abstractmethod
    def health_check(self) -> OpResult: ...

    def unlock(self): self._production_locked = False
    def lock(self): self._production_locked = True

    def _result(self, operation, success, *, latency_ms=0.0,
                real_api_called=False, change_id="", detail="", error="",
                data=None, **extra) -> OpResult:
        if real_api_called and (self._production_locked or self.sandbox != SandboxMode.PRODUCTION):
            raise RuntimeError(
                f"{self.name}: real_api_called=True requires unlock()+PRODUCTION")
        return OpResult(
            provider=self.name, operation=operation, success=success,
            latency_ms=latency_ms, real_api_called=real_api_called,
            change_id=change_id, detail=detail, error=error,
            data=data, extra=extra)

    @staticmethod
    def _timed(fn, *a, **kw):
        t0 = time.perf_counter()
        r = fn(*a, **kw)
        return r, (time.perf_counter() - t0) * 1000.0


__all__ = [
    "MonetizationOperationProvider", "MonetizationOpChange", "OpResult",
    "AdUnit", "IAPProduct", "SandboxMode", "CredentialRef",
    "OP_CREATE", "OP_UPDATE", "OP_FETCH", "OP_DELETE", "OP_HEALTH_CHECK",
    "AD_REWARDED", "AD_INTERSTITIAL", "AD_BANNER",
    "IAP_CONSUMABLE", "IAP_NON_CONSUMABLE", "IAP_SUBSCRIPTION",
]
