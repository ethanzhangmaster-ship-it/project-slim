"""
E14.3.3 — Module 6: Remote Config Health
=========================================

Produces the health signal consumed by the E14.2 Runtime Supervisor
(`health_check() -> degrade / alert`). The shape:

    {
      "provider": "RemoteConfig",
      "status": "healthy",            # healthy | degraded | down
      "backend": "local" | "firebase" | "mock",
      "latency_ms": 80,
      "credential_valid": true,
      "api_available": true,
      "config_version": "v123"
    }

`status` is degraded when the credential is invalid OR the backend is
unreachable. The credential_valid / api_available / backend / config_version
flags ride in ProviderResult.extra so the frozen 5-key contract stays intact.
"""
from __future__ import annotations

from monetization.providers.remote_config.config_models import ConfigHealth


def build_health(client) -> ConfigHealth:
    cred_valid = client.check_credential()
    api_available = client.ping()
    status = "healthy" if (cred_valid and api_available) else "degraded"
    return ConfigHealth(
        status=status,
        backend=getattr(client, "backend", "mock"),
        credential_valid=cred_valid,
        api_available=api_available,
        config_version=client.config_version(),
    )
