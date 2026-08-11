"""
E15.1.5 — Mock App Store Client

Sample-backed, stateful mock of App Store Connect API.
"""
from __future__ import annotations

from typing import Dict, Optional

from operation.publishing.providers.models import (
    AS_IN_REVIEW, AS_PREPARE, AS_READY, AS_REJECTED, AS_WAITING,
    BS_VALID,
)


class MockAppStoreClient:
    """In-memory mock of App Store Connect. Zero real API calls."""

    def __init__(self):
        self._apps: Dict[str, dict] = {}
        self._builds: Dict[str, dict] = {}
        self._simulated_rejection: Optional[dict] = None

    def set_simulated_rejection(self, code: str, reason: str) -> None:
        self._simulated_rejection = {"code": code, "reason": reason}

    # ------------------------------------------------------------------ #
    def create_app(self, game_id: str, bundle_id: str, title: str) -> dict:
        app = {
            "app_id": f"as_app_{game_id}",
            "game_id": game_id,
            "bundle_id": bundle_id,
            "title": title,
            "status": AS_PREPARE,
        }
        self._apps[game_id] = app
        return {"success": True, "app_id": app["app_id"]}

    def get_app(self, game_id: str) -> Optional[dict]:
        return self._apps.get(game_id)

    # ------------------------------------------------------------------ #
    def upload_build(self, game_id: str, build_path: str,
                     version: str, build_number: int) -> dict:
        if game_id not in self._apps:
            return {"success": False, "error": f"app not found: {game_id}"}
        build = {
            "game_id": game_id, "path": build_path,
            "version": version, "build_number": build_number,
            "uploaded": True,
        }
        self._builds[game_id] = build
        self._apps[game_id]["status"] = AS_PREPARE
        return {"success": True, "build_id": f"mock_bld_{build_number}"}

    # ------------------------------------------------------------------ #
    def create_version(self, game_id: str, version: str) -> dict:
        if game_id not in self._apps:
            return {"success": False, "error": "app not found"}
        self._apps[game_id]["version"] = version
        return {"success": True}

    def submit_review(self, game_id: str, version_id: Optional[str] = None) -> dict:
        if self._simulated_rejection:
            status = AS_REJECTED
        else:
            status = AS_WAITING
        self._apps[game_id]["status"] = status
        return {"success": True, "status": status}

    def check_status(self, game_id: str) -> dict:
        app = self._apps.get(game_id, {})
        status = app.get("status", AS_PREPARE)
        if status == AS_WAITING:
            status = AS_IN_REVIEW
        elif status == AS_IN_REVIEW and not self._simulated_rejection:
            status = AS_READY
        self._apps[game_id]["status"] = status
        return {
            "game_id": game_id, "status": status,
            "rejection": self._simulated_rejection.copy() if status == AS_REJECTED and self._simulated_rejection else None,
        }

    def release(self, game_id: str) -> dict:
        app = self._apps.get(game_id)
        if not app:
            return {"success": False, "error": "app not found"}
        status = app.get("status", "")
        if status == AS_REJECTED:
            return {"success": False, "error": "cannot release rejected app"}
        self._apps[game_id]["status"] = AS_READY
        return {"success": True, "status": AS_READY}

    def rollback(self, game_id: str) -> dict:
        self._apps[game_id]["status"] = AS_PREPARE
        return {"success": True, "status": AS_PREPARE}

    def update_metadata(self, game_id: str, metadata: dict) -> dict:
        return {"success": True, "detail": "metadata updated"}

    def upload_screenshots(self, game_id: str, screenshot_paths: list) -> dict:
        return {"success": True, "detail": f"{len(screenshot_paths)} screenshots uploaded"}

    # ------------------------------------------------------------------ #
    # iOS build upload & phased release stubs (Spec ios_upload_spec.md)
    # SIMULATION 模式下的简单成功返回，不改变现有方法行为。
    # ------------------------------------------------------------------ #
    def poll_build_status(self, game_id, version, build_number,
                          timeout_seconds=1800, poll_interval_seconds=30):
        return {
            "success": True,
            "build_status": {
                "build_id": f"mock_bld_{build_number}",
                "version": version,
                "build_number": build_number,
                "processing_state": BS_VALID,
            },
        }

    def select_build(self, version_id, build_id):
        return {"success": True, "detail": f"build {build_id} selected for {version_id}"}

    def start_phased_release(self, version_id):
        return {"success": True, "detail": f"phased release started for {version_id}"}

    def pause_phased_release(self, phased_release_id):
        return {"success": True, "detail": f"phased release {phased_release_id} paused"}

    def resume_phased_release(self, phased_release_id):
        return {"success": True, "detail": f"phased release {phased_release_id} resumed"}

    def complete_phased_release(self, phased_release_id):
        return {"success": True, "detail": f"phased release {phased_release_id} completed"}

    def check_phased_release(self, version_id):
        return {
            "success": True,
            "data": {"id": f"pr_{version_id}", "attributes": {"state": "ACTIVE"}},
        }


__all__ = ["MockAppStoreClient"]
