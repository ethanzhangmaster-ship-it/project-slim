"""
E15.1.1 — GooglePlayProductionProvider

PublishingProvider backed by GooglePlayRealClient.
Routes sandbox mode: PRODUCTION → real API, SIMULATION → mock.
"""
from __future__ import annotations

from typing import Optional

from monetization.providers.models import CredentialRef, SandboxMode
from operation.publishing.google_play.client import MockGooglePlayClient
from operation.publishing.google_play.mapper import GooglePlayMapper
from operation.publishing.google_play.provider import GooglePlayProvider
from operation.publishing.providers.base import PublishingProvider
from operation.publishing.providers.google_play.real_client import GooglePlayRealClient
from operation.publishing.providers.models import (
    GP_APPROVED, OP_CHECK_STATUS, OP_CREATE_APP, OP_CREATE_RELEASE,
    OP_RELEASE, OP_ROLLBACK, OP_SUBMIT_REVIEW, OP_UPLOAD_BUILD,
    OP_UPDATE_METADATA, PublishingChange, PublishingResult,
)


class GooglePlayProductionProvider(PublishingProvider):
    """Production Google Play provider: real API when PRODUCTION sandbox.

    Extends GooglePlayProvider's logic but replaces MockGooglePlayClient
    with GooglePlayRealClient. Falls back to mock in SIMULATION/SHADOW.
    """

    name = "google_play_production"

    def __init__(self, sandbox=SandboxMode.SIMULATION,
                 credential_ref=None,
                 credential: Optional[dict] = None,
                 mock_client: Optional[MockGooglePlayClient] = None):
        super().__init__(sandbox=sandbox, credential_ref=credential_ref)
        self._real_client = GooglePlayRealClient(credential=credential)
        self._mock_client = mock_client or MockGooglePlayClient()
        self.mapper = GooglePlayMapper()

    @property
    def _client(self):
        """Return real or mock client based on sandbox mode."""
        if self.sandbox == SandboxMode.PRODUCTION:
            return self._real_client
        return self._mock_client

    def arm_real_client(self, override):
        """Inject test seam into the real client."""
        self._real_client.arm_real_client(override)

    # ------------------------------------------------------------------ #
    def apply_change(self, change: PublishingChange) -> PublishingResult:
        operation = change.operation
        game_id = change.game_id
        payload = change.new or {}
        client = self._client
        real = self.sandbox == SandboxMode.PRODUCTION and not self._production_locked

        def _call():
            if operation == OP_CREATE_APP:
                return client.create_app(
                    game_id,
                    payload.get("package_name", f"com.fake.{game_id}"),
                    payload.get("title", game_id))
            elif operation == OP_UPLOAD_BUILD:
                return client.upload_bundle(
                    game_id, payload.get("file_path", ""),
                    payload.get("version", "1.0.0"),
                    payload.get("build_number", 1))
            elif operation == OP_CREATE_RELEASE:
                return client.create_release(
                    game_id, payload.get("track", "internal"))
            elif operation == OP_SUBMIT_REVIEW:
                return client.submit_review(game_id)
            elif operation == OP_RELEASE:
                return client.release_to_production(game_id)
            elif operation == OP_UPDATE_METADATA:
                return client.update_metadata(game_id, payload)
            elif operation == OP_CHECK_STATUS:
                return client.check_status(game_id)
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
        client = self._client
        real = self.sandbox == SandboxMode.PRODUCTION and not self._production_locked
        result, elapsed = self._timed(client.rollback, change.game_id)
        success = result.get("success", False)
        return self._result(
            OP_ROLLBACK, success, latency_ms=elapsed, real_api_called=real,
            change_id=change.change_id, detail="rolled back to DRAFT",
            after=result)

    def health_check(self) -> PublishingResult:
        client = self._client
        real = self.sandbox == SandboxMode.PRODUCTION and not self._production_locked
        result, elapsed = self._timed(client.get_app, "_health")
        return self._result(
            OP_CHECK_STATUS, True, latency_ms=elapsed, real_api_called=real,
            detail="google_play client ready")


__all__ = ["GooglePlayProductionProvider"]
