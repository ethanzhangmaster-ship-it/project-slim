"""
P3 — Store API credential vault.

Holds App Store Connect + Google Play credentials in
<workspace-root>/credentials/store_keys.json — the SAME directory that
already holds live_accounts.json (the running automation reads keys from
here). Local-only, git-ignored. NEVER inline secrets in scripts/Bash.

App Store Connect requires:
    key_id, issuer_id, private_key_p8   (the .p8 file text verbatim)
Google Play requires:
    service_account_json_path           (path to the service-account .json;
                                          that file is also git-ignored)

To go live you only paste credentials here — the crypto dependency
(`cryptography`) is already installed into the managed runtime, so no
extra install step is needed.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional


def _store_path() -> str:
    """Resolve <workspace-root>/credentials/store_keys.json.

    launchforge/operation/providers/live/store_keys.py
      -> 2026-07-23-11-01-07/credentials/store_keys.json
    (4 levels up from .../operation/providers/live, i.e. the workspace
    root that also contains live_accounts.json).
    """
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(here))))
    return os.path.join(root, "credentials", "store_keys.json")


def load() -> Dict[str, Any]:
    path = _store_path()
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_appstore() -> Optional[dict]:
    data = load()
    as_ = data.get("app_store_connect")
    if not as_ or not as_.get("key_id") or not as_.get("issuer_id") \
            or not as_.get("private_key_p8"):
        return None
    return as_


def get_googleplay() -> Optional[dict]:
    data = load()
    gp = data.get("google_play")
    if not gp or not gp.get("service_account_json_path"):
        return None
    return gp


def has_any() -> bool:
    return get_appstore() is not None or get_googleplay() is not None


def set_appstore(key_id: str, issuer_id: str, private_key_p8: str) -> None:
    path = _store_path()
    data = {"_note": "Local-only store API keys. Never commit.",
            "app_store_connect": {}, "google_play": {}}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    data["app_store_connect"] = {
        "key_id": key_id,
        "issuer_id": issuer_id,
        "private_key_p8": private_key_p8,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def set_googleplay(service_account_json_path: str) -> None:
    path = _store_path()
    data = {"_note": "Local-only store API keys. Never commit.",
            "app_store_connect": {}, "google_play": {}}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    data["google_play"] = {
        "service_account_json_path": service_account_json_path,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


__all__ = [
    "load", "get_appstore", "get_googleplay", "has_any",
    "set_appstore", "set_googleplay",
]
