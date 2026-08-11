"""
E15.1.4 — GooglePlayProvider (PublishingProvider implementation)

Full Google Play publishing lifecycle via MockGooglePlayClient.
Respects SandboxMode: SIMULATION (no API), SHADOW (read-only), PRODUCTION (real).
"""
from __future__ import annotations

from typing import Optional

from monetization.providers.models import CredentialRef, SandboxMode
from operation.publishing.google_play.client import MockGooglePlayClient
from operation.publishing.google_play.mapper import GooglePlayMapper
from operation.publishing.providers.base import PublishingProvider
from operation.publishing.providers.models import (
    GP_APPROVED, GP_DRAFT, GP_REJECTED, OP_CHECK_STATUS,
    OP_CREATE_APP, OP_CREATE_RELEASE, OP_RELEASE,
    OP_ROLLBACK, OP_SUBMIT_REVIEW, OP_UPLOAD_BUILD,
    OP_UPDATE_METADATA, PublishingChange, PublishingResult,
)


class GooglePlayProvider(PublishingProvider):
    name = "google_play"

    def __init__(self, sandbox=SandboxMode.SIMULATION,
                 credential_ref=None,
                 client: Optional[MockGooglePlayClient] = None,
                 mapper: Optional[GooglePlayMapper] = None):
        super().__init__(sandbox=sandbox, credential_ref=credential_ref)
        self.client = client or MockGooglePlayClient()
        self.mapper = mapper or GooglePlayMapper()

    # ------------------------------------------------------------------ #
    def apply_change(self, change: PublishingChange) -> PublishingResult:
        operation = change.operation
        game_id = change.game_id
        payload = change.new or {}
        real = self.sandbox == SandboxMode.PRODUCTION and not self._production_locked

        def _call():
            if operation == OP_CREATE_APP:
                return self.client.create_app(
                    game_id,
                    payload.get("package_name", f"com.fake.{game_id}"),
                    payload.get("title", game_id))
            elif operation == OP_UPLOAD_BUILD:
                return self.client.upload_bundle(
                    game_id, payload.get("file_path", ""),
                    payload.get("version", "1.0.0"),
                    payload.get("build_number", 1))
            elif operation == OP_CREATE_RELEASE:
                return self.client.create_release(
                    game_id, payload.get("track", "internal"))
            elif operation == OP_SUBMIT_REVIEW:
                return self.client.submit_review(game_id)
            elif operation == OP_RELEASE:
                return self.client.release_to_production(game_id)
            elif operation == OP_UPDATE_METADATA:
                locale = payload.pop("locale", "en-US")
                return self.client.update_metadata(
                    game_id, payload, locale=locale)
            elif operation == OP_CHECK_STATUS:
                return self.client.check_status(game_id)
            else:
                return {"success": False, "error": f"unknown op: {operation}"}

        result, elapsed = self._timed(_call)
        success = result.get("success", False)
        return self._result(
            operation, success, latency_ms=elapsed, real_api_called=real,
            change_id=change.change_id, detail=result.get("detail", ""),
            error=result.get("error", ""), before=change.old,
            after=result, **{k: v for k, v in result.items()
                             if k not in ("success", "detail", "error")})

    def rollback_change(self, change: PublishingChange) -> PublishingResult:
        game_id = change.game_id
        real = self.sandbox == SandboxMode.PRODUCTION and not self._production_locked
        result, elapsed = self._timed(self.client.rollback, game_id)
        success = result.get("success", False)
        return self._result(
            OP_ROLLBACK, success, latency_ms=elapsed, real_api_called=real,
            change_id=change.change_id, detail="rolled back to DRAFT",
            after=result)

    def health_check(self) -> PublishingResult:
        real = self.sandbox == SandboxMode.PRODUCTION and not self._production_locked
        # check connectivity by listing apps (mock: always healthy)
        return self._result(
            OP_CHECK_STATUS, True, latency_ms=0.5, real_api_called=real,
            detail="google_play mock healthy")


__all__ = ["GooglePlayProvider"]
