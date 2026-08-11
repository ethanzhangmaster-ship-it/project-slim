"""
E15.2.6.5 — Adjust discovery helper.

Lists the apps this user token can see so we can map them to our MAX
accounts (ACCT_1/2/3). Run:

    PYTHONPATH=. python operation/optimizer/adjust_tools.py discover

The output is a clean table of name / token / platform / bundle that you
can use to fill `adjust.account_apps` in credentials/live_accounts.json.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from operation.providers.live.adjust.kpi_client import (  # noqa: E402
    load_adjust_config, list_apps, AdjustAuthError, AdjustError)


def _bundle(a: dict) -> str:
    return (a.get("bundle_id") or a.get("package_name")
            or a.get("store_id") or a.get("bundle") or "")


def discover() -> List[dict]:
    cfg = load_adjust_config()
    tok = cfg.get("user_token")
    if not tok:
        return []
    apps = list_apps(tok)
    return [{
        "name": a.get("name"),
        "token": a.get("token"),
        "platform": a.get("platform"),
        "bundle": _bundle(a),
    } for a in apps]


def fetch_account_dau(account: str, start: str, end: str) -> Optional[float]:
    """Sum/avg DAU for one mapped MAX account over [start, end]."""
    from operation.providers.live.adjust.kpi_client import (
        load_adjust_config, fetch_avg_dau)
    cfg = load_adjust_config()
    tok = cfg.get("user_token")
    apps = cfg.get("account_apps", {}).get(account)
    if not tok:
        print("NO_TOKEN (adjust.user_token not set)")
        return None
    if not apps:
        print(f"NO_MAPPING (adjust.account_apps['{account}'] empty)")
        return None
    return fetch_avg_dau(tok, apps, start, end)


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "dau":
        acct = args[1] if len(args) > 1 else "ACCT_2"
        # default window: 10 days ending yesterday
        from datetime import date, timedelta
        end = (date.today() - timedelta(days=1)).isoformat()
        start = (date.today() - timedelta(days=10)).isoformat()
        try:
            dau = fetch_account_dau(acct, start, end)
        except AdjustAuthError as e:
            print("AUTH_ERROR:", e); return 2
        except AdjustError as e:
            print("API_ERROR:", e); return 3
        if dau is None:
            return 0
        print(f"{acct} mean daily DAU = {dau:,.1f}  (window {start}..{end})")
        return 0

    try:
        apps = discover()
    except AdjustAuthError as e:
        print("AUTH_ERROR:", e)
        return 2
    except AdjustError as e:
        print("API_ERROR:", e)
        return 3
    if not apps:
        print("NO_APPS (no token configured or empty account)")
        return 0
    print(f"# discovered {len(apps)} Adjust app(s):")
    for a in apps:
        tok = a["token"] or "?"
        mask = (tok[:4] + "…" + tok[-4:]) if len(tok) > 10 else tok
        print(f"  - {a['name']}  | token={mask}  | {a['platform']}  | {a['bundle']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
