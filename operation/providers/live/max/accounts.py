"""
E15 — Live MAX multi-account credential store.

Loads real AppLovin MAX account keys from credentials/live_accounts.json.
This is the SINGLE source of truth for live keys — never inline keys in
ad-hoc Bash commands or scripts. The file is local-only and git-ignored.
"""
from __future__ import annotations

import json
import os
from typing import Dict, Optional

_STORE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))),
    "credentials", "live_accounts.json")


def _store_path() -> str:
    # launchforge/operation/providers/live/max/accounts.py
    # -> launchforge/credentials/live_accounts.json
    here = os.path.dirname(os.path.abspath(__file__))
    lf_root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(here)))))
    return os.path.join(lf_root, "credentials", "live_accounts.json")


def load_accounts() -> Dict[str, dict]:
    """Return the full {account_id: {label, report_key, management_key}} map."""
    path = _store_path()
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("accounts", {})


def get_account(account_id: str) -> Optional[dict]:
    """Return one account's config, or None if missing/empty."""
    acct = load_accounts().get(account_id)
    if not acct:
        return None
    if not acct.get("report_key"):
        return None
    return acct


def set_account(account_id: str, label: str,
                report_key: str, management_key: str = "") -> None:
    """Persist (or update) an account's keys into the store."""
    path = _store_path()
    data = {"_note": "Local-only MAX account keys. Never commit.", "accounts": {}}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    data.setdefault("accounts", {})[account_id] = {
        "label": label,
        "report_key": report_key,
        "management_key": management_key,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


__all__ = ["load_accounts", "get_account", "set_account"]
