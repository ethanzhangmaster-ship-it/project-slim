"""
E15.1.5 — AppStoreProvider (PublishingProvider implementation)
"""
from __future__ import annotations

from typing import Optional

from monetization.providers.models import CredentialRef, SandboxMode
from operation.publishing.app_store.client import MockAppStoreClient
from operation.publishing.app_store.mapper import AppStoreMapper
from operation.publishing.providers.base import PublishingProvider
from operation.publishing.providers.models import (
    AS_READY, OP_CHECK_STATUS, OP_CHECK_PHASED_RELEASE,
    OP_COMPLETE_PHASED_RELEASE, OP_CREATE_APP, OP_CREATE_RELEASE,
    OP_PAUSE_PHASED_RELEASE, OP_POLL_BUILD_STATUS, OP_RELEASE,
    OP_RESUME_PHASED_RELEASE, OP_ROLLBACK, OP_SELECT_BUILD,
    OP_START_PHASED_RELEASE, OP_SUBMIT_REVIEW, OP_UPLOAD_BUILD,
    OP_UPLOAD_BUILD_ALTOOL, OP_UPDATE_METADATA,
    PublishingChange, PublishingResult,
)


class AppStoreProvider(PublishingProvider):
    name = "app_store"

    def __init__(self, sandbox=SandboxMode.SIMULATION,
                 credential_ref=None,
                 client: Optional[MockAppStoreClient] = None,
                 mapper: Optional[AppStoreMapper] = None):
        super().__init__(sandbox=sandbox, credential_ref=credential_ref)
        self.client = client or MockAppStoreClient()
        self.mapper = mapper or AppStoreMapper()

    def apply_change(self, change: PublishingChange) -> PublishingResult:
        operation = change.operation
        game_id = change.game_id
        payload = change.new or {}
        real = self.sandbox == SandboxMode.PRODUCTION and not self._production_locked

        def _call():
            if operation == OP_CREATE_APP:
                return self.client.create_app(
                    game_id,
                    payload.get("bundle_id", f"com.fake.{game_id}"),
                    payload.get("title", game_id))
            elif operation == OP_UPLOAD_BUILD:
                return self.client.upload_build(
                    game_id, payload.get("file_path", ""),
                    payload.get("version", "1.0.0"),
                    payload.get("build_number", 1))
            elif operation == OP_CREATE_RELEASE:
                return self.client.create_version(
                    game_id, payload.get("version", "1.0.0"))
            elif operation == OP_SUBMIT_REVIEW:
                return self.client.submit_review(game_id)
            elif operation == OP_RELEASE:
                return self.client.release(game_id)
            elif operation == OP_UPDATE_METADATA:
                return {"success": True, "detail": "metadata updated"}
            elif operation == OP_CHECK_STATUS:
                return self.client.check_status(game_id)
            # iOS build upload & phased release (Spec ios_upload_spec.md §5.2)
            elif operation == OP_UPLOAD_BUILD_ALTOOL:
                return self.client.upload_build(
                    game_id, payload.get("ipa_path", ""),
                    payload.get("version", "1.0.0"),
                    payload.get("build_number", 1))
            elif operation == OP_POLL_BUILD_STATUS:
                return self.client.poll_build_status(
                    game_id, payload.get("version", "1.0.0"),
                    payload.get("build_number", 1),
                    timeout_seconds=payload.get("timeout_seconds", 1800))
            elif operation == OP_SELECT_BUILD:
                return self.client.select_build(
                    payload.get("version_id", ""),
                    payload.get("build_id", ""))
            elif operation == OP_START_PHASED_RELEASE:
                return self.client.start_phased_release(
                    payload.get("version_id", ""))
            elif operation == OP_PAUSE_PHASED_RELEASE:
                return self.client.pause_phased_release(
                    payload.get("phased_release_id", ""))
            elif operation == OP_RESUME_PHASED_RELEASE:
                return self.client.resume_phased_release(
                    payload.get("phased_release_id", ""))
            elif operation == OP_COMPLETE_PHASED_RELEASE:
                return self.client.complete_phased_release(
                    payload.get("phased_release_id", ""))
            elif operation == OP_CHECK_PHASED_RELEASE:
                return self.client.check_phased_release(
                    payload.get("version_id", ""))
            else:
                return {"success": False, "error": f"unknown op: {operation}"}

        result, elapsed = self._timed(_call)
        success = result.get("success", False)
        return self._result(
            operation, success, latency_ms=elapsed, real_api_called=real,
            change_id=change.change_id, detail=result.get("detail", ""),
            error=result.get("error", ""), before=change.old,
            after=result,
            **{k: v for k, v in result.items()
               if k not in ("success", "detail", "error")})

    def rollback_change(self, change: PublishingChange) -> PublishingResult:
        game_id = change.game_id
        real = self.sandbox == SandboxMode.PRODUCTION and not self._production_locked
        result, elapsed = self._timed(self.client.rollback, game_id)
        return self._result(
            OP_ROLLBACK, result.get("success", False),
            latency_ms=elapsed, real_api_called=real,
            change_id=change.change_id, detail="rolled back",
            after=result)

    def health_check(self) -> PublishingResult:
        return self._result(
            OP_CHECK_STATUS, True, latency_ms=0.5,
            detail="app_store mock healthy")


__all__ = ["AppStoreProvider"]
