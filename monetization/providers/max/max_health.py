"""
E14.3.2 — Module 6: MAX Health
==============================

Produces the health signal consumed by the E14.2 Runtime Supervisor
(`health_check() -> degrade / alert`). The shape:

    {
      "provider": "max",
      "status": "healthy",          # healthy | degraded | down
      "latency_ms": 120,
      "credential_valid": true,
      "api_available": true
    }

`status` is degraded when credential is invalid OR the API is unreachable.
The credential_valid / api_available flags ride in ProviderResult.extra so the
frozen 5-key contract stays intact.
"""
from __future__ import annotations

from monetization.providers.max.max_models import MaxHealth


def build_health(client) -> MaxHealth:
    cred_valid = client.check_credential()
    api_available = client.ping()
    status = "healthy" if (cred_valid and api_available) else "degraded"
    return MaxHealth(status=status, credential_valid=cred_valid,
                     api_available=api_available)
