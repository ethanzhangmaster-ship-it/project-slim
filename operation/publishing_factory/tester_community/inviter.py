"""High-level inviter: load community config -> drive RealClient ->
record eligibility state.

This module does the actual API call. CLI wraps it.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from operation.publishing.providers.google_play.real_client import (
    GooglePlayRealClient, load_default_real_client,
)
from operation.publishing_factory.tester_community import community, eligibility


def invite(package_name: str, *,
           apply: bool = False,
           dry_run: Optional[bool] = None,
           tester_emails: Optional[List[str]] = None,
           tester_groups: Optional[List[str]] = None,
           client: Optional[GooglePlayRealClient] = None) -> Dict:
    """Invite the community (or override list) to ``package_name``'s
    closed track. Returns a status dict with at least:
      - ok(bool)
      - stage(str): "dry-run" | "invite-sent" | "no-community" |
                    "no-tester-list" | "config-missing" |
                    "api-error"
      - detail(str): human-readable summary
      - tester_count(int): how many testers were targeted
      - http_status(int|None): the API's status code (None for dry-run)
      - body of the API result (when apply=True)
    """
    if dry_run is None:
        dry_run = not apply

    community_emails: List[str] = []
    community_groups: List[str] = []
    if tester_emails is None and tester_groups is None:
        cfg = community.load()
        if not cfg.get("configured"):
            return {
                "ok": False,
                "stage": "config-missing",
                "detail": ("tester_community.json is not configured. "
                           "Run: python -m operation.publishing_factory."
                           "tester_community init"),
                "tester_count": 0,
                "http_status": None,
            }
        community_emails = cfg.get("emails", [])
        community_groups = cfg.get("groups", [])
    else:
        community_emails = tester_emails or []
        community_groups = tester_groups or []

    if not community_emails and not community_groups:
        return {
            "ok": False,
            "stage": "no-tester-list",
            "detail": ("tester community has neither emails nor groups; "
                       "add at least one"),
            "tester_count": 0,
            "http_status": None,
        }

    target_emails = community_emails
    target_groups = community_groups
    client = client or load_default_real_client()

    result = client.invite_testers_to_closed_track(
        package_name=package_name,
        tester_emails=target_emails,
        tester_groups=target_groups,
        track="closed",
        dry_run=dry_run,
    )

    if not result.get("success"):
        return {
            "ok": False,
            "stage": "api-error",
            "detail": (result.get("error")
                       or "API returned success=False"),
            "tester_count": len(target_emails),
            "http_status": result.get("status_code"),
            "api_result": result,
        }

    if dry_run:
        return {
            "ok": True,
            "stage": "dry-run",
            "detail": (f"would invite {len(target_emails)} emails + "
                       f"{len(target_groups)} groups to {package_name} "
                       f"closed track (pass apply=True to actually "
                       f"send)"),
            "tester_count": len(target_emails),
            "http_status": None,
            "would_invite_emails": target_emails,
            "would_invite_groups": target_groups,
            "api_result": result,
        }

    # Real send: bump eligibility state
    new_state = eligibility.record_invitation(
        package_name, tester_count=len(target_emails))
    return {
        "ok": True,
        "stage": "invite-sent",
        "detail": (f"invited {len(target_emails)} emails + "
                   f"{len(target_groups)} groups to {package_name} "
                   f"closed track; 14-day clock "
                   f"{'started' if new_state['invited_at'] else 'not started yet'} "
                   f"(need {eligibility.REQUIRED_TESTERS} testers)"),
        "tester_count": len(target_emails),
        "http_status": result.get("status_code") or 200,
        "eligibility": new_state,
        "api_result": result,
    }


__all__ = ["invite"]
