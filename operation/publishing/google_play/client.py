"""
E15.1.4 — Mock Google Play Client

Sample-backed, stateful mock of Google Play Console API.
Replace with google-api-python-client in production.
"""
from __future__ import annotations

from typing import Dict, Optional

from operation.publishing.providers.models import (
    GP_APPROVED, GP_DRAFT, GP_IN_REVIEW, GP_PUBLISHED, GP_REJECTED,
)


class MockGooglePlayClient:
    """In-memory mock of Google Play Console. Zero real API calls."""

    def __init__(self):
        self._apps: Dict[str, dict] = {}
        self._builds: Dict[str, dict] = {}
        self._releases: Dict[str, dict] = {}
        # simulation: inject a rejection for testing
        self._simulated_rejection: Optional[dict] = None

    def set_simulated_rejection(self, code: str, reason: str) -> None:
        self._simulated_rejection = {"code": code, "reason": reason}

    # ------------------------------------------------------------------ #
    def create_app(self, game_id: str, package_name: str,
                   title: str) -> dict:
        app = {
            "app_id": f"gp_app_{game_id}",
            "game_id": game_id,
            "package_name": package_name,
            "title": title,
            "status": GP_DRAFT,
        }
        self._apps[game_id] = app
        return {
            "success": True, "app_id": app["app_id"],
            "package_name": package_name, "status": GP_DRAFT,
        }

    def get_app(self, game_id: str) -> Optional[dict]:
        return self._apps.get(game_id)

    # ------------------------------------------------------------------ #
    def upload_bundle(self, game_id: str, build_path: str,
                      version: str, build_number: int) -> dict:
        if game_id not in self._apps:
            return {"success": False, "error": f"app not found: {game_id}"}
        build = {
            "game_id": game_id, "path": build_path,
            "version": version, "build_number": build_number,
            "uploaded": True, "version_code": build_number,
        }
        self._builds[game_id] = build
        return {"success": True, "version_code": build_number}

    # ------------------------------------------------------------------ #
    def create_release(self, game_id: str, track: str = "internal") -> dict:
        if game_id not in self._builds:
            return {"success": False, "error": "no build uploaded"}
        rel = {
            "release_id": f"rel_{game_id}_{track}",
            "game_id": game_id, "track": track,
            "status": GP_DRAFT,
        }
        self._releases[game_id] = rel
        self._apps[game_id]["status"] = GP_DRAFT
        return {"success": True, "release_id": rel["release_id"], "track": track}

    # ------------------------------------------------------------------ #
    def submit_review(self, game_id: str) -> dict:
        if game_id not in self._releases:
            return {"success": False, "error": "no release created"}
        if self._simulated_rejection:
            status = GP_REJECTED
        else:
            status = GP_IN_REVIEW
        self._releases[game_id]["status"] = status
        self._apps[game_id]["status"] = status
        return {"success": True, "status": status}

    # ------------------------------------------------------------------ #
    def check_status(self, game_id: str) -> dict:
        app = self._apps.get(game_id, {})
        status = app.get("status", GP_DRAFT)
        # auto-advance: IN_REVIEW → APPROVED after one check (mock)
        if status == GP_IN_REVIEW and not self._simulated_rejection:
            status = GP_APPROVED
            self._apps[game_id]["status"] = status
            self._releases.get(game_id, {})["status"] = status
        return {
            "success": True,
            "game_id": game_id, "status": status,
            "rejection": self._simulated_rejection.copy() if status == GP_REJECTED and self._simulated_rejection else None,
        }

    # ------------------------------------------------------------------ #
    def release_to_production(self, game_id: str) -> dict:
        app = self._apps.get(game_id)
        if not app or app.get("status") != GP_APPROVED:
            return {"success": False,
                    "error": "app not approved for production release"}
        self._apps[game_id]["status"] = GP_PUBLISHED
        return {"success": True, "status": GP_PUBLISHED}

    def rollback(self, game_id: str) -> dict:
        self._apps[game_id]["status"] = GP_DRAFT
        self._releases.pop(game_id, None)
        return {"success": True, "status": GP_DRAFT}

    def update_metadata(self, game_id: str, metadata: dict) -> dict:
        return {"success": True, "detail": "metadata updated"}

    def upload_screenshots(self, game_id: str, screenshot_paths: list) -> dict:
        return {"success": True, "detail": f"{len(screenshot_paths)} screenshots uploaded"}


__all__ = ["MockGooglePlayClient"]
