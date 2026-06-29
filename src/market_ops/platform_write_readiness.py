from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings


SUPPORTED_OPERATIONS = {
    "meta_ads": {"increase_budget_cap", "decrease_budget_or_bid", "pause_candidate_review"},
    "google_ads": {"increase_budget_cap", "decrease_budget_or_bid", "pause_candidate_review"},
    "apple_search_ads": set(),
}


@dataclass(slots=True)
class PlatformWriteReadinessResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class PlatformWriteReadinessBuilder:
    """Builds a safety gate for future ad-platform write connectors."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> PlatformWriteReadinessResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"platform_write_readiness_{suffix}.md"
        json_path = output_dir / f"platform_write_readiness_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return PlatformWriteReadinessResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        global_write_enabled = _env_bool("MEDIA_BUYER_PLATFORM_WRITE_ENABLED")
        approval_required = not _env_bool("MEDIA_BUYER_ALLOW_UNAPPROVED_WRITE")
        platform_gates = {
            "meta_ads": _platform_gate(
                platform="meta_ads",
                credential_ready=bool(self._settings.meta_access_token and self._settings.meta_ad_account_id),
                global_write_enabled=global_write_enabled,
                approval_required=approval_required,
                missing_credentials=[
                    name
                    for name, value in (
                        ("META_ACCESS_TOKEN", self._settings.meta_access_token),
                        ("META_AD_ACCOUNT_ID", self._settings.meta_ad_account_id),
                    )
                    if not value
                ],
            ),
            "google_ads": _platform_gate(
                platform="google_ads",
                credential_ready=bool(
                    self._settings.google_ads_developer_token
                    and self._settings.google_ads_client_id
                    and self._settings.google_ads_client_secret
                    and self._settings.google_ads_refresh_token
                    and self._settings.google_ads_customer_id
                ),
                global_write_enabled=global_write_enabled,
                approval_required=approval_required,
                missing_credentials=[
                    name
                    for name, value in (
                        ("GOOGLE_ADS_DEVELOPER_TOKEN", self._settings.google_ads_developer_token),
                        ("GOOGLE_ADS_CLIENT_ID", self._settings.google_ads_client_id),
                        ("GOOGLE_ADS_CLIENT_SECRET", self._settings.google_ads_client_secret),
                        ("GOOGLE_ADS_REFRESH_TOKEN", self._settings.google_ads_refresh_token),
                        ("GOOGLE_ADS_CUSTOMER_ID", self._settings.google_ads_customer_id),
                    )
                    if not value
                ],
            ),
            "apple_search_ads": _platform_gate(
                platform="apple_search_ads",
                credential_ready=False,
                global_write_enabled=global_write_enabled,
                approval_required=approval_required,
                missing_credentials=["APPLE_SEARCH_ADS_CONNECTOR"],
            ),
            "unknown": {
                "platform": "unknown",
                "write_ready": False,
                "supported_operations": [],
                "missing_credentials": [],
                "blockers": ["platform_not_inferred"],
            },
        }
        ready_platforms = [name for name, item in platform_gates.items() if item.get("write_ready")]
        return {
            "report_date": report_date.isoformat(),
            "mode": "platform_write_readiness_gate",
            "passed": True,
            "global_write_enabled": global_write_enabled,
            "approval_required": approval_required,
            "rules": {
                "enable_env": "MEDIA_BUYER_PLATFORM_WRITE_ENABLED=true",
                "approval_override_env": "MEDIA_BUYER_ALLOW_UNAPPROVED_WRITE=true",
                "default": "Writes remain disabled unless explicitly enabled and platform credentials are complete.",
            },
            "summary": {
                "ready_platform_count": len(ready_platforms),
                "ready_platforms": ready_platforms,
                "blocked_platform_count": sum(1 for item in platform_gates.values() if not item.get("write_ready")),
            },
            "platforms": platform_gates,
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# Platform Write Readiness | {payload['report_date']}",
            "",
            "- Mode: platform_write_readiness_gate",
            f"- Global write enabled: {payload['global_write_enabled']}",
            f"- Approval required: {payload['approval_required']}",
            f"- Ready platforms: {summary['ready_platform_count']}",
            "",
            "## Platforms",
            "",
        ]
        for platform, item in payload["platforms"].items():
            blockers = ", ".join(item.get("blockers") or []) or "none"
            operations = ", ".join(item.get("supported_operations") or []) or "none"
            missing = ", ".join(item.get("missing_credentials") or []) or "none"
            lines.append(
                f"- {platform} | write_ready={item.get('write_ready')} | operations={operations} | "
                f"missing={missing} | blockers={blockers}"
            )
        lines.append("")
        return "\n".join(lines)


def readiness_for_intent(readiness_payload: dict[str, Any], platform: str, operation: str) -> dict[str, Any]:
    platforms = readiness_payload.get("platforms") or {}
    gate = platforms.get(platform) or platforms.get("unknown") or {}
    blockers = list(gate.get("blockers") or [])
    supported = set(gate.get("supported_operations") or [])
    if operation and supported and operation not in supported:
        blockers.append("operation_not_supported")
    if operation and not supported and platform != "unknown":
        blockers.append("operation_not_supported")
    return {
        "platform_write_enabled": bool(readiness_payload.get("global_write_enabled")),
        "platform_write_ready": bool(gate.get("write_ready")) and not blockers,
        "blockers": _unique(blockers),
        "supported_operations": sorted(supported),
    }


def _platform_gate(
    *,
    platform: str,
    credential_ready: bool,
    global_write_enabled: bool,
    approval_required: bool,
    missing_credentials: list[str],
) -> dict[str, Any]:
    blockers: list[str] = []
    if not global_write_enabled:
        blockers.append("platform_write_disabled")
    if not credential_ready:
        blockers.append("platform_credentials_missing")
    if approval_required:
        blockers.append("approval_required")
    return {
        "platform": platform,
        "write_ready": global_write_enabled and credential_ready and not approval_required,
        "supported_operations": sorted(SUPPORTED_OPERATIONS.get(platform, set())),
        "missing_credentials": missing_credentials,
        "blockers": blockers,
    }


def _env_bool(name: str) -> bool:
    return str(os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result
