"""
E15.1.2 — Real market-opportunity source (skeleton / seam)
==========================================================

Inert until you configure it. Reads ``credentials/market_sources.json``:

    {
      "providers": {
        "appstore_rank": {
          "enabled": false,
          "endpoint": "",
          "api_key_env": "MARKET_SRC_API_KEY"
        }
      }
    }

And only fires when BOTH hold:
  1. a provider is ``enabled`` with a non-empty ``endpoint``; AND
  2. a parser is registered in ``PROVIDER_ADAPTERS`` for that provider id.

Until then ``fetch()`` returns ``[]`` and never touches the network — so
the pipeline is safe to run in production today.

------------------------------------------------------------------------
HOW TO PLUG A REAL FEED (the only code you write):
------------------------------------------------------------------------
In your own bootstrap, register a parser that turns the provider's raw
JSON into a list of MarketOpportunity-shaped dicts:

    from operation.factory_brain.growth_sources.real_source import (
        register_provider,
    )
    def _parse_appstore(raw: dict) -> list:
        out = []
        for r in raw.get("results", []):
            out.append({
                "opportunity_id": f"as_{r['genre']}_{r['theme']}",
                "genre": r["genre"], "theme": r.get("theme", ""),
                "keyword_trend": r["trend"], "competition": r["competition"],
                "ecpm_signal": r["ecpm"], "ltv_forecast": r["ltv"],
                "notes": f"App Store rank feed: {r.get('note','')}",
            })
        return out
    register_provider("appstore_rank", _parse_appstore)

Then set ``enabled: true`` + ``endpoint`` in credentials/market_sources.json
(with the API key in the named env var, never inlined).
"""
from __future__ import annotations

import json
import os
from typing import Callable, Dict, List

from .base import MarketSource
from operation.factory_brain.models import MarketOpportunity

DEFAULT_CONFIG = "credentials/market_sources.json"

# provider_id -> parser(raw_json: dict) -> List[opportunity_dict]
# Populated by register_provider(); empty until you add a real feed.
PROVIDER_ADAPTERS: Dict[str, Callable[[dict], List[dict]]] = {}


def register_provider(provider_id: str,
                      parser: Callable[[dict], List[dict]]) -> None:
    """Register a raw-JSON parser for a real market provider."""
    PROVIDER_ADAPTERS[provider_id] = parser


class RealMarketSource(MarketSource):
    """Skeleton real feed. Safe + inert until configured + adapter present."""
    name = "real_market"
    kind = "real"

    def __init__(self, config_path: str = DEFAULT_CONFIG,
                 client=None) -> None:
        self.config_path = config_path
        self._client = client          # injectable for offline tests

    # ------------------------------------------------------------------ #
    def _load_config(self) -> dict:
        if not os.path.exists(self.config_path):
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def status(self) -> Dict[str, object]:
        cfg = self._load_config()
        providers = cfg.get("providers") or {}
        enabled = [pid for pid, p in providers.items()
                   if isinstance(p, dict) and p.get("enabled")
                   and p.get("endpoint")]
        configured = any(pid in PROVIDER_ADAPTERS for pid in enabled)
        return {"name": self.name, "kind": self.kind,
                "configured": configured,
                "enabled_providers": enabled,
                "registered_adapters": sorted(PROVIDER_ADAPTERS.keys()),
                "note": ("" if configured else
                         "no enabled provider has a registered adapter yet")}

    # ------------------------------------------------------------------ #
    def fetch_raw(self) -> List[dict]:
        cfg = self._load_config()
        providers = cfg.get("providers") or {}
        out: List[dict] = []
        for pid, pconf in providers.items():
            if not isinstance(pconf, dict):
                continue
            if not (pconf.get("enabled") and pconf.get("endpoint")):
                continue
            parser = PROVIDER_ADAPTERS.get(pid)
            if parser is None:                 # seam: adapter not implemented
                continue
            try:
                if self._client is not None:
                    raw_json = self._client(pid, pconf)
                else:
                    raw_json = self._http_get(pid, pconf)
                out.extend(parser(raw_json) or [])
            except Exception:                  # noqa: BLE001 — never crash
                continue
        return out

    @staticmethod
    def _http_get(provider_id: str, pconf: dict) -> dict:
        """Minimal urllib GET. Only reached when a provider is live."""
        import urllib.request
        url = pconf["endpoint"]
        env_key = pconf.get("api_key_env")
        headers = {}
        if env_key:
            token = os.environ.get(env_key, "")
            if token:
                headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    def normalize(self, raw: List[dict]) -> List[MarketOpportunity]:
        out: List[MarketOpportunity] = []
        for d in raw:
            if not isinstance(d, dict) or "opportunity_id" not in d:
                continue
            o = MarketOpportunity.from_dict(d)
            o.source = "growth_os"
            out.append(o)
        return out


__all__ = ["RealMarketSource", "register_provider", "PROVIDER_ADAPTERS"]
