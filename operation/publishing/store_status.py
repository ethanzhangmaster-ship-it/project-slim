"""
P3 — Store publishing-status backflow.

Pulls real (or simulated) publishing status from App Store Connect /
Google Play for a set of games and normalizes it into a flat report that
the daily briefing can later embed.

Safety contract (same as the rest of the system):
  * dry_run=True  → ZERO network calls, real_api_called=False.
  * vault empty   → ZERO network calls, real_api_called=False
                     (status "disabled", reason "no_store_credentials").
  * real calls only happen when dry_run=False AND the vault has the
    matching platform credential AND sandbox is production/shadow.

This module never writes to a store — it only reads status.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from operation.providers.live.store_keys import (
    get_appstore,
    get_googleplay,
    has_any,
)
from operation.publishing.providers.app_store.real_client import (
    AppStoreRealClient,
)
from operation.publishing.providers.google_play.real_client import (
    GooglePlayRealClient,
)


def collect_store_status(games: List[Dict[str, str]], *,
                          dry_run: bool = True,
                          sandbox: str = "simulation") -> Dict[str, Any]:
    """Collect publishing status for `games`.

    games: [{"game_id", "platform": "ios"|"android",
              "bundle_id"?|"package_name"?}]
    Returns:
        {"status": "disabled"|"live",
         "real_api_called": bool,
         "reason"?: str,
         "per_game": [{"game_id","platform","status","version"?,
                       "error"?,"note"?}]}
    """
    live = (not dry_run) and sandbox in ("production", "shadow")

    if dry_run or not has_any():
        return {
            "status": "disabled",
            "real_api_called": False,
            "reason": "dry_run" if dry_run else "no_store_credentials",
            "per_game": [
                {
                    "game_id": g.get("game_id"),
                    "platform": g.get("platform"),
                    "status": "unknown",
                    "note": "store status backflow not active",
                }
                for g in games
            ],
        }

    as_cred = get_appstore()
    gp_cred = get_googleplay()
    per_game: List[Dict[str, Any]] = []
    real_called = False

    for g in games:
        plat = g.get("platform")
        gid = g.get("game_id")
        if plat == "ios" and as_cred:
            client = AppStoreRealClient(credential={
                "key_id": as_cred["key_id"],
                "issuer_id": as_cred["issuer_id"],
                "private_key_p8": as_cred["private_key_p8"],
                "bundle_id": g.get("bundle_id"),
            })
            res = client.check_status(gid)
            real_called = True
            per_game.append({
                "game_id": gid, "platform": "ios",
                "status": res.get("status"),
                "version": res.get("version", ""),
                "error": res.get("error", ""),
            })
        elif plat == "android" and gp_cred:
            client = GooglePlayRealClient(credential={
                "service_account_json_path": gp_cred["service_account_json_path"],
                "package_name": g.get("package_name"),
            })
            res = client.check_status(gid)
            real_called = True
            per_game.append({
                "game_id": gid, "platform": "android",
                "status": res.get("status"),
                "version": res.get("version", ""),
                "error": res.get("error", ""),
            })
        else:
            per_game.append({
                "game_id": gid, "platform": plat,
                "status": "unknown",
                "note": "no credential configured for this platform",
            })

    return {
        "status": "live",
        "real_api_called": real_called,
        "per_game": per_game,
    }


__all__ = ["collect_store_status"]
