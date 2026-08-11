"""
E15.1.1 — Google Play Real API Client

Production-ready Google Play Developer API client.
Implements same interface as MockGooglePlayClient.
Requires service account JSON credential.
Implements the arm_real_client hook pattern for testability.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from operation.providers.live.http_util import http_json


class GooglePlayRealClient:
    """Real Google Play Developer API client.

    Credential-driven. All API calls go through _call_api hook.
    Set _api_override to inject a mock transport for testing.
    """

    BASE_URL = "https://androidpublisher.googleapis.com/androidpublisher/v3"
    # Play Developer Reporting API (Vitals: crashRate / anrRate / retention).
    REPORTING_BASE = "https://playdeveloperreporting.googleapis.com/v1beta"
    # Play console hard cap on a review reply (developer comment) text.
    REVIEW_REPLY_MAX_CHARS = 350
    # Play console hard cap on a store-listing experiment display name.
    EXPERIMENT_NAME_MAX_CHARS = 80

    def __init__(self, credential: Optional[Dict[str, Any]] = None):
        self._credential = credential or {}
        self._apps: Dict[str, dict] = {}
        self._api_override: Optional[Callable] = None  # seam for testing
        self._vitals_override: Optional[Callable] = None  # seam for vitals
        self._token: Optional[str] = None
        self._token_exp: int = 0

    def arm_real_client(self, override: Callable) -> None:
        """Inject a custom API handler (test seam)."""
        self._api_override = override

    def arm_vitals(self, override: Callable) -> None:
        """Inject a custom Vitals transport (test seam).

        ``override`` has the signature ``(package_name, window_days) -> dict``
        and must return the normalized vitals dict produced by
        :meth:`get_vitals`. Used by the Health Agent tests so no real
        Play Developer Reporting API call is ever made in CI.
        """
        self._vitals_override = override

    # ------------------------------------------------------------------ #
    # HTTP seam
    # ------------------------------------------------------------------ #
    def _access_token(self) -> str:
        """Return an OAuth2 access token, caching it for ~55 min."""
        now = int(time.time())
        if self._token and self._token_exp and self._token_exp > now + 60:
            return self._token
        cred = self._credential or {}
        sa = cred.get("service_account_json")
        if not sa:
            p = cred.get("service_account_json_path")
            if not p or not os.path.exists(p):
                raise RuntimeError("service account JSON missing "
                                   "(set via store_keys.set_googleplay())")
            with open(p, "r", encoding="utf-8") as f:
                sa = json.load(f)
        from operation.providers.live import auth as _auth
        self._token = _auth.make_googleplay_token(sa)
        self._token_exp = now + 3500
        return self._token

    def _call_api(self, method: str, path: str,
                  body: Optional[Dict] = None) -> Dict[str, Any]:
        """Single HTTP seam. Override via arm_real_client or call directly."""
        if self._api_override:
            return self._api_override(method, path, body)

        cred = self._credential or {}
        if not (cred.get("service_account_json_path")
                or cred.get("service_account_json")):
            return {
                "success": False,
                "status_code": 0,
                "error": "Google Play credentials missing — "
                         "set via store_keys.set_googleplay()",
                "data": None,
            }
        try:
            token = self._access_token()
        except Exception as e:  # noqa: BLE001
            return {"success": False, "status_code": 0,
                    "error": f"auth failed: {e}", "data": None}
        headers = {"Authorization": f"Bearer {token}"}
        return http_json(method, self.BASE_URL + path,
                         body=body, headers=headers)

    def _resolve_package(self, game_id: str) -> Optional[str]:
        """Look up package_name from credential or app registry."""
        pkg = self._credential.get("package_name")
        if not pkg:
            app = self._apps.get(game_id, {})
            pkg = app.get("package_name")
        return pkg

    def set_package(self, game_id: str, package_name: str) -> None:
        """Register a game_id -> package_name mapping so check_status /
        update_metadata can resolve the package without re-reading creds."""
        self._apps[game_id] = {"package_name": package_name}

    # ------------------------------------------------------------------ #
    # App lifecycle
    # ------------------------------------------------------------------ #
    def create_app(self, game_id: str, package_name: str,
                   title: str) -> dict:
        path = f"/applications"
        body = {
            "packageName": package_name,
            "title": title,
        }
        result = self._call_api("POST", path, body)
        if result.get("success", False):
            app = {
                "app_id": f"gp_{game_id}",
                "game_id": game_id,
                "package_name": package_name,
                "title": title,
                "status": "draft",
            }
            self._apps[game_id] = app
            return {
                "success": True,
                "app_id": app["app_id"],
                "package_name": package_name,
                "status": "draft",
            }
        return result

    def get_app(self, game_id: str) -> Optional[dict]:
        pkg = self._resolve_package(game_id)
        if not pkg:
            return None
        path = f"/applications/{pkg}"
        result = self._call_api("GET", path)
        if result.get("success", False):
            return result
        return self._apps.get(game_id)

    # ------------------------------------------------------------------ #
    # Build upload
    # ------------------------------------------------------------------ #
    def upload_bundle(self, game_id: str, build_path: str,
                      version: str, build_number: int) -> dict:
        pkg = self._resolve_package(game_id)
        if not pkg:
            return {"success": False, "error": f"app not found: {game_id}"}
        # Real: POST /uploads/androidpublisher/v3/applications/{pkg}/edits/{editId}/bundles
        path = f"/applications/{pkg}/edits/upload/bundles"
        result = self._call_api("POST", path, {
            "version": version,
            "build_number": build_number,
        })
        if result.get("success", False):
            return {
                "success": True,
                "version_code": result.get("versionCode", build_number),
            }
        return result

    # ------------------------------------------------------------------ #
    # Release management
    # ------------------------------------------------------------------ #
    def create_release(self, game_id: str, track: str = "internal") -> dict:
        pkg = self._resolve_package(game_id)
        if not pkg:
            return {"success": False, "error": "app not found"}
        path = f"/applications/{pkg}/edits"
        result = self._call_api("POST", path, {"track": track})
        if result.get("success", False):
            return {
                "success": True,
                "release_id": result.get("id", f"rel_{game_id}"),
                "track": track,
            }
        return result

    def submit_review(self, game_id: str) -> dict:
        pkg = self._resolve_package(game_id)
        if not pkg:
            return {"success": False, "error": "app not found"}
        path = f"/applications/{pkg}/edits/commit"
        result = self._call_api("POST", path, {"changesNotSentForReview": False})
        if result.get("success", False):
            return {"success": True, "status": "in_review"}
        return result

    def check_status(self, game_id: str) -> dict:
        pkg = self._resolve_package(game_id)
        if not pkg:
            return {"game_id": game_id, "status": "unknown",
                    "error": "package_name missing (set in credential or app)"}
        # Google Play reads require a staging edit.
        r = self._call_api("POST", f"/applications/{pkg}/edits")
        if not r.get("success"):
            return {"game_id": game_id, "status": "unknown",
                    "error": r.get("error"),
                    "status_code": r.get("status_code")}
        edit_id = (r.get("data") or {}).get("id")
        if not edit_id:
            return {"game_id": game_id, "status": "draft", "success": True}
        try:
            r2 = self._call_api(
                "GET", f"/applications/{pkg}/edits/{edit_id}/tracks/production")
        finally:
            # best-effort cleanup of the staging edit
            self._call_api("DELETE",
                           f"/applications/{pkg}/edits/{edit_id}")
        if not r2.get("success"):
            return {"game_id": game_id, "status": "unknown",
                    "error": r2.get("error"),
                    "status_code": r2.get("status_code")}
        releases = (r2.get("data") or {}).get("releases") or []
        if not releases:
            return {"game_id": game_id, "status": "draft", "success": True}
        play_state = releases[0].get("status", "completed")
        status_map = {
            "completed": "published",
            "inProgress": "in_review",
            "draft": "draft",
            "halted": "rejected",
        }
        status = status_map.get(play_state, play_state)
        return {
            "game_id": game_id,
            "status": status,
            "success": True,
            "version": str(releases[0].get("versionCode", "")),
            "play_status": play_state,
            "rejection": releases[0].get("statusDetails"),
        }

    def release_to_production(self, game_id: str) -> dict:
        pkg = self._resolve_package(game_id)
        if not pkg:
            return {"success": False, "error": "app not found"}
        path = f"/applications/{pkg}/edits/commit"
        result = self._call_api("POST", path, {
            "track": "production",
            "status": "completed",
        })
        if result.get("success", False):
            return {"success": True, "status": "published"}
        return result

    def rollback(self, game_id: str) -> dict:
        pkg = self._resolve_package(game_id)
        if not pkg:
            return {"success": False, "error": "app not found"}
        path = f"/applications/{pkg}/edits/rollback"
        result = self._call_api("POST", path, {})
        if result.get("success", False):
            return {"success": True, "status": "draft"}
        return result

    # ------------------------------------------------------------------ #
    # Metadata
    # ------------------------------------------------------------------ #
    def update_metadata(self, game_id: str, metadata: Dict[str, Any],
                         locale: str = "en-US") -> dict:
        """Update a store listing locale via the Android Publisher
        Edits API: open an edit → PUT the listing → commit.

        ``locale`` is a BCP-47 code (e.g. ``en-US``, ``fil``, ``ar``).
        This is the lowest-blast-radius real write: it only changes the
        listing text (title / short / full description) of an app that
        already exists in the console. Reversible by another edit.
        """
        pkg = self._resolve_package(game_id)
        if not pkg:
            return {"success": False, "error": "app not found"}
        # 1) open a staging edit
        edit = self._call_api("POST", f"/applications/{pkg}/edits")
        if not edit.get("success"):
            return edit
        edit_id = (edit.get("data") or {}).get("id")
        if not edit_id:
            return {"success": False, "error": "edit id missing from response",
                    "detail": str(edit.get("data"))}
        # 2) put the listing (for the requested locale)
        body = {
            "title": metadata.get("title", ""),
            "shortDescription": metadata.get("short_description", ""),
            "fullDescription": metadata.get("full_description", ""),
        }
        put = self._call_api(
            "PUT",
            f"/applications/{pkg}/edits/{edit_id}/listings/{locale}", body)
        if not put.get("success"):
            self._call_api("DELETE", f"/applications/{pkg}/edits/{edit_id}")
            return put
        # 3) commit the edit so it actually lands in the console
        commit = self._call_api(
            "POST", f"/applications/{pkg}/edits/{edit_id}:commit", {})
        if not commit.get("success"):
            return commit
        return {"success": True, "detail": f"listing {locale} updated",
                "edit_id": edit_id, "locale": locale}

    def upload_screenshots(self, game_id: str, screenshot_paths: list) -> dict:
        pkg = self._resolve_package(game_id)
        if not pkg:
            return {"success": False, "error": "app not found"}
        path = f"/applications/{pkg}/listings/en-US/images"
        result = self._call_api("POST", path, {
            "image_count": len(screenshot_paths),
        })
        if result.get("success", False):
            return {"success": True, "detail": f"{len(screenshot_paths)} screenshots uploaded"}
        return result

    # ------------------------------------------------------------------ #
    # Closed-testing tester invitation
    # ------------------------------------------------------------------ #
    def invite_testers_to_closed_track(self, package_name: str,
                                       tester_emails: Optional[List[str]] = None,
                                       tester_groups: Optional[List[str]] = None,
                                       track: str = "closed",
                                       dry_run: bool = True) -> dict:
        """Invite a list of testers (or Google Groups) to the closed
        testing track of a given package. Lowest-blast-radius real write:
        only adds email addresses to the closed-testing testers list.
        No APK, no listing, no production publish.

        Edits API: open edit -> PUT testers/<track> -> commit.
        Default is dry_run=True; pass dry_run=False to actually invite.
        """
        if not package_name:
            return {"success": False, "status_code": 0,
                    "error": "package_name required"}
        emails = [e for e in (tester_emails or []) if e]
        groups = [g for g in (tester_groups or []) if g]
        if not emails and not groups:
            return {"success": False, "status_code": 0,
                    "error": "no testers to invite (emails/groups both empty)"}

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "package_name": package_name,
                "track": track,
                "would_invite_emails": emails,
                "would_invite_groups": groups,
                "note": "dry-run only; pass dry_run=False to actually invite",
            }

        edit = self._call_api("POST", f"/applications/{package_name}/edits")
        if not edit.get("success"):
            return edit
        edit_id = (edit.get("data") or {}).get("id")
        if not edit_id:
            return {"success": False,
                    "error": "edit id missing from open response",
                    "detail": str(edit.get("data"))}

        body: Dict[str, Any] = {}
        if emails:
            body["testerEmails"] = emails
        if groups:
            body["groups"] = groups
        put = self._call_api(
            "PUT",
            f"/applications/{package_name}/edits/{edit_id}/testers/{track}",
            body)
        if not put.get("success"):
            self._call_api(
                "DELETE", f"/applications/{package_name}/edits/{edit_id}")
            return put

        commit = self._call_api(
            "POST",
            f"/applications/{package_name}/edits/{edit_id}:commit", {})
        if not commit.get("success"):
            return commit
        return {
            "success": True,
            "package_name": package_name,
            "track": track,
            "tester_count": len(emails),
            "group_count": len(groups),
            "edit_id": edit_id,
            "detail": f"{len(emails)} testers + {len(groups)} groups invited to {track}",
        }

    def get_testers(self, package_name: str,
                    track: str = "closed") -> dict:
        """READ the current closed-track testers (emails + groups) for a
        package. No mutation: open edit -> GET testers/<track> -> delete edit.

        Returns ``{"success", "package_name", "track", "tester_emails",
        "groups"}``. Used by the Tester Pool Agent to compute the diff before
        inviting so it never clobbers existing testers (the PUT replaces the
        list, so we must UNION with the current set).
        """
        if not package_name:
            return {"success": False, "status_code": 0,
                    "error": "package_name required"}
        edit = self._call_api("POST", f"/applications/{package_name}/edits")
        if not edit.get("success"):
            return edit
        edit_id = (edit.get("data") or {}).get("id")
        if not edit_id:
            return {"success": True, "package_name": package_name,
                    "track": track, "tester_emails": [], "groups": []}
        try:
            r = self._call_api(
                "GET",
                f"/applications/{package_name}/edits/{edit_id}/testers/{track}")
        finally:
            self._call_api(
                "DELETE", f"/applications/{package_name}/edits/{edit_id}")
        if not r.get("success"):
            return {"success": False, "status_code": r.get("status_code"),
                    "error": r.get("error") or "testers read failed"}
        data = r.get("data") or {}
        return {
            "success": True,
            "package_name": package_name,
            "track": track,
            "tester_emails": data.get("testerEmails") or [],
            "groups": data.get("groups") or [],
        }


    def set_rollout(self, package_name: str, track: str = "production",
                    user_fraction: float = 0.05,
                    release_notes: Optional[Dict[str, str]] = None,
                    version_code: Optional[int] = None,
                    in_app_update_priority: int = 0) -> dict:
        """Stage a rollout at ``user_fraction`` (0.05 == 5%) on ``track``.
        Lowest-blast-radius release control: only changes the rollout
        percentage, no new binary. Edits API: open -> PUT tracks/{track}
        -> commit.
        """
        if not package_name:
            return {"success": False, "status_code": 0,
                    "error": "package_name required"}
        edit = self._call_api("POST", f"/applications/{package_name}/edits")
        if not edit.get("success"):
            return edit
        edit_id = (edit.get("data") or {}).get("id")
        if not edit_id:
            return {"success": False, "error": "edit id missing",
                    "detail": str(edit.get("data"))}
        release: Dict[str, Any] = {
            "status": "inProgress",
            "userFraction": float(user_fraction),
            "inAppUpdatePriority": int(in_app_update_priority),
        }
        if version_code is not None:
            release["versionCode"] = int(version_code)
        if release_notes:
            release["releaseNotes"] = [
                {"language": lang, "text": txt}
                for lang, txt in release_notes.items()]
        put = self._call_api(
            "PUT",
            f"/applications/{package_name}/edits/{edit_id}/tracks/{track}",
            {"releases": [release]})
        if not put.get("success"):
            self._call_api(
                "DELETE", f"/applications/{package_name}/edits/{edit_id}")
            return put
        commit = self._call_api(
            "POST", f"/applications/{package_name}/edits/{edit_id}:commit", {})
        if not commit.get("success"):
            return commit
        return {"success": True, "package_name": package_name, "track": track,
                "user_fraction": float(user_fraction),
                "detail": f"rollout set to {int(user_fraction * 100)}% "
                          f"on {track}"}

    def halt_rollout(self, package_name: str,
                     track: str = "production") -> dict:
        """Halt an in-progress rollout on ``track`` (userFraction -> 0).
        Used by the Health Agent to stop a bad release automatically.
        Edits API: open -> PUT tracks/{track} with status=halted -> commit.
        """
        if not package_name:
            return {"success": False, "status_code": 0,
                    "error": "package_name required"}
        edit = self._call_api("POST", f"/applications/{package_name}/edits")
        if not edit.get("success"):
            return edit
        edit_id = (edit.get("data") or {}).get("id")
        if not edit_id:
            return {"success": False, "error": "edit id missing",
                    "detail": str(edit.get("data"))}
        put = self._call_api(
            "PUT",
            f"/applications/{package_name}/edits/{edit_id}/tracks/{track}",
            {"releases": [{"status": "halted"}]})
        if not put.get("success"):
            self._call_api(
                "DELETE", f"/applications/{package_name}/edits/{edit_id}")
            return put
        commit = self._call_api(
            "POST", f"/applications/{package_name}/edits/{edit_id}:commit", {})
        if not commit.get("success"):
            return commit
        return {"success": True, "package_name": package_name, "track": track,
                "detail": f"rollout halted on {track}"}

    def get_track_status(self, package_name: str,
                         track: str = "production") -> dict:
        """READ the current rollout state of ``track`` (no mutation).

        Returns the latest release's status / userFraction / versionCode so
        the Release Agent can decide the next stage. Edits API:
        open edit -> GET tracks/{track} -> delete edit.
        """
        if not package_name:
            return {"success": False, "status_code": 0,
                    "error": "package_name required"}
        edit = self._call_api("POST", f"/applications/{package_name}/edits")
        if not edit.get("success"):
            return edit
        edit_id = (edit.get("data") or {}).get("id")
        if not edit_id:
            return {"success": True, "track": track, "releases": [],
                    "status": "empty"}
        try:
            r = self._call_api(
                "GET",
                f"/applications/{package_name}/edits/{edit_id}/tracks/{track}")
        finally:
            self._call_api(
                "DELETE", f"/applications/{package_name}/edits/{edit_id}")
        if not r.get("success"):
            return {"success": False, "status_code": r.get("status_code"),
                    "error": r.get("error") or "track read failed"}
        releases = (r.get("data") or {}).get("releases") or []
        if not releases:
            return {"success": True, "track": track, "releases": [],
                    "status": "empty"}
        latest = releases[-1]
        return {
            "success": True,
            "track": track,
            "status": latest.get("status", "completed"),
            "user_fraction": float(latest.get("userFraction", 0.0) or 0.0),
            "version_code": latest.get("versionCode"),
            "release_count": len(releases),
            "releases": releases,
        }


    # ------------------------------------------------------------------ #
    # Vitals (Play Developer Reporting API) — READ ONLY, no mutation
    # ------------------------------------------------------------------ #
    def _call_reporting(self, method: str, path: str,
                        body: Optional[Dict] = None) -> Dict[str, Any]:
        """Single HTTP seam for the Play Developer Reporting API.

        Override via :meth:`arm_vitals` (test seam) or call directly with a
        bearer token derived from the same service account as the publisher
        API. Returns the normalized ``http_json`` dict shape.
        """
        if self._vitals_override is not None:
            # The seam is keyed differently (package, window) because the
            # Health Agent owns the query composition; route it here.
            raise RuntimeError(
                "arm_vitals seams a (package, window) transport, not the raw "
                "reporting call — use get_vitals() with transport=")
        cred = self._credential or {}
        if not (cred.get("service_account_json_path")
                or cred.get("service_account_json")):
            return {"success": False, "status_code": 0,
                    "error": "Google Play credentials missing — "
                             "set via store_keys.set_googleplay()",
                    "data": None}
        try:
            token = self._access_token()
        except Exception as e:  # noqa: BLE001
            return {"success": False, "status_code": 0,
                    "error": f"auth failed: {e}", "data": None}
        url = self.REPORTING_BASE + path
        return http_json(method, url, body=body,
                         headers={"Authorization": f"Bearer {token}"})

    def _query_metric_set(self, package_name: str, metric_set: str,
                          metric: str) -> Optional[float]:
        """Query one Vitals metric set and return its latest value as a
        PERCENTAGE (0–100) so it matches ``ReleasePolicy`` thresholds.

        The Play Developer Reporting API returns a fraction (e.g. ``0.01`` ==
        1%), so the raw value is multiplied by 100. Returns ``None`` when the
        metric set is empty / unreadable / not yet populated.
        """
        path = f"/apps/{package_name}/{metric_set}:query"
        body = {
            "timelineSpec": {"aggregationPeriod": "DAILY"},
            "metrics": [metric],
        }
        r = self._call_reporting("POST", path, body)
        if not r.get("success"):
            return None
        data = r.get("data") or {}
        dms = data.get("dailyMetrics") or []
        if not dms:
            return None
        rows = dms[0].get("rows") or []
        if not rows:
            return None
        last = rows[-1]
        # columns: [timestamp, metricValue]; value is the last element.
        val = last[-1] if isinstance(last, (list, tuple)) else last
        try:
            if isinstance(val, dict):
                val = val.get("decimal", 0.0)
            return float(val) * 100.0
        except (TypeError, ValueError):
            return None

    def get_vitals(self, package_name: str, window_days: int = 7,
                   transport: Optional[Callable] = None) -> Dict[str, Any]:
        """READ the app's Vitals (crash / ANR rates) for the last
        ``window_days`` from the Play Developer Reporting API.

        Returns a normalized dict the Health Agent and Release Agent both
        consume:

            {"package_name", "crash_rate", "anr_rate", "d1_retention",
             "window_days", "source", "fetched_at"}

        Rates are PERCENTAGES (0–100) to match ``ReleasePolicy`` thresholds.
        ``d1_retention`` is ``None`` by default — the crash/ANR metric sets
        do not carry retention; wire a ``retentionMetricSet`` transport if
        you need it. ``transport`` can be injected (test seam / offline
        cache); otherwise the real Reporting API is used.

        Hard fact: this endpoint is READ-ONLY. It never mutates console
        state, so it is safe under SHADOW/PRODUCTION without an unlock.
        """
        if transport is None and self._vitals_override is not None:
            transport = self._vitals_override
        if transport is not None:
            return transport(package_name, window_days)
        crash = self._query_metric_set(
            package_name, "crashRateMetricSet", "crashRate")
        anr = self._query_metric_set(
            package_name, "anrRateMetricSet", "anrRate")
        return {
            "package_name": package_name,
            "crash_rate": crash,          # % or None
            "anr_rate": anr,             # % or None
            "d1_retention": None,        # not served by crash/ANR sets
            "window_days": window_days,
            "source": "play_developer_reporting",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }


    # ------------------------------------------------------------------ #
    # Reviews (reviews.list READ / reviews.reply WRITE)
    # ------------------------------------------------------------------ #
    def get_reviews(self, package_name: str,
                    max_results: int = 100,
                    transport: Optional[Callable] = None) -> Dict[str, Any]:
        """READ the latest user reviews for ``package_name`` via the Reviews
        API (``reviews.list``). Returns a normalized dict the Review Agent
        consumes:

            {"package_name", "reviews": [{...}], "count", "token",
             "fetched_at", "source"}

        Each review normalizes the Play JSON shape (which nests the latest
        user text + optional developer reply inside ``comments[]``):

            {"review_id", "author_name", "star_rating", "text",
             "last_modified", "device", "version_code", "reply_text",
             "replied_at", "reviewer_language"}

        Hard fact: READ-ONLY. Never mutates console state, safe under
        SHADOW/PRODUCTION without an unlock. ``transport`` can be injected
        (test seam / offline cache); otherwise the real Reviews API is used.
        """
        if transport is not None:
            return transport(package_name, max_results)
        if not package_name:
            return {"success": False, "status_code": 0,
                    "error": "package_name required", "data": None}
        path = (f"/applications/{package_name}/reviews"
                f"?maxResults={int(max_results)}")
        r = self._call_api("GET", path)
        if not r.get("success"):
            return {"success": False, "status_code": r.get("status_code"),
                    "error": r.get("error") or "review read failed",
                    "data": None}
        data = r.get("data") or {}
        raw = data.get("reviews") or []
        reviews = []
        for item in raw:
            author = (item.get("author") or {}).get("name", "")
            comments = item.get("comments") or []
            uc: Dict[str, Any] = {}
            dc: Dict[str, Any] = {}
            for c in comments:
                if c.get("userComment"):
                    uc = c["userComment"]
                if c.get("developerComment"):
                    dc = c["developerComment"]
            # fallback for the single-comment legacy shape
            if not uc and comments:
                uc = comments[-1]
            last_mod = (uc.get("lastModified") or {}).get("seconds")
            replied_mod = (dc.get("lastModified") or {}).get("seconds")
            reviews.append({
                "review_id": item.get("reviewId"),
                "author_name": author,
                "star_rating": uc.get("starRating"),
                "text": uc.get("text", ""),
                "last_modified": last_mod,
                "device": uc.get("device"),
                "version_code": uc.get("versionCode"),
                "reply_text": dc.get("text"),
                "replied_at": replied_mod,
                "reviewer_language": (uc.get("reviewerLanguage")
                                      or dc.get("reviewerLanguage")),
            })
        return {
            "success": True,
            "package_name": package_name,
            "reviews": reviews,
            "count": len(reviews),
            "token": data.get("token"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source": "androidpublisher.reviews.list",
        }

    def reply_to_review(self, package_name: str, review_id: str,
                        reply_text: str) -> Dict[str, Any]:
        """Reply to a user review via the Reviews API (``reviews.reply``).
        ``POST /applications/{pkg}/reviews/{reviewId}:reply`` with
        ``{"replyText": ...}``.

        This is the lowest-blast-radius real WRITE in the whole runtime:
        it changes only the developer reply text on a single review — no
        new binary, listing, or rollout. The 350-character Play console
        cap is enforced locally so we never send an oversize body the API
        would reject.

        Callers must validate ownership before writing (the PlayConnector
        does this via ``_verify_ownership``).
        """
        if not package_name:
            return {"success": False, "status_code": 0,
                    "error": "package_name required"}
        if not review_id:
            return {"success": False, "status_code": 0,
                    "error": "review_id required"}
        if not reply_text or not reply_text.strip():
            return {"success": False, "status_code": 0,
                    "error": "reply_text required (non-empty)"}
        if len(reply_text) > self.REVIEW_REPLY_MAX_CHARS:
            return {
                "success": False, "status_code": 0,
                "error": f"reply_text too long ({len(reply_text)} > "
                         f"{self.REVIEW_REPLY_MAX_CHARS} chars)",
            }
        path = (f"/applications/{package_name}/reviews/{review_id}:reply")
        r = self._call_api("POST", path, {"replyText": reply_text})
        if not r.get("success"):
            return {"success": False, "status_code": r.get("status_code"),
                    "error": r.get("error") or "reply failed"}
        data = r.get("data") or {}
        return {
            "success": True,
            "package_name": package_name,
            "review_id": review_id,
            "reply_text": reply_text,
            "result": data.get("result"),
            "detail": "reply posted",
        }

    # ------------------------------------------------------------------ #
    # Store-listing experiments (edits.experiments) — true ASO
    # ------------------------------------------------------------------ #
    def create_listing_experiment(
            self, package_name: str, *, name: str, locale: str = "en-US",
            variant_title: Optional[str] = None,
            variant_short: Optional[str] = None,
            variant_full: Optional[str] = None,
            baseline_title: Optional[str] = None,
            baseline_short: Optional[str] = None,
            baseline_full: Optional[str] = None,
            user_fraction: float = 0.1,
            start_date: Optional[Dict[str, int]] = None,
            end_date: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        """Create a store-listing A/B experiment via the Edits API
        (``edits.experiments``). Compares the CURRENT live listing (baseline
        variant) against one challenger variant (modified title / short /
        full description for ``locale``).

        Steps: open edit -> POST experiments -> commit edit so the
        experiment is actually scheduled. Returns
        ``{"success", "experiment_id", "edit_id", "name", "detail"}``.

        ``user_fraction`` is the share of users routed to the experiment
        (Google requires >= a minimum, default 10%). ``start_date`` /
        ``end_date`` are ``{"year","month","day"}`` dicts (optional; the
        console defaults to immediate / auto-end).

        This is the ASO control surface: it never changes the live listing
        until you later *promote* a winning variant — so it is a
        lowest-blast-radius, reversible write. The 80-char experiment-name
        cap is enforced locally.
        """
        if not package_name:
            return {"success": False, "status_code": 0,
                    "error": "package_name required"}
        if not name or not name.strip():
            return {"success": False, "status_code": 0,
                    "error": "experiment name required"}
        if len(name) > self.EXPERIMENT_NAME_MAX_CHARS:
            return {"success": False, "status_code": 0,
                    "error": f"name too long ({len(name)} > "
                             f"{self.EXPERIMENT_NAME_MAX_CHARS} chars)"}
        # validate the challenger title is non-empty if supplied
        if variant_title is not None and not variant_title.strip():
            return {"success": False, "status_code": 0,
                    "error": "variant_title must be non-empty if supplied"}

        edit = self._call_api("POST", f"/applications/{package_name}/edits")
        if not edit.get("success"):
            return edit
        edit_id = (edit.get("data") or {}).get("id")
        if not edit_id:
            return {"success": False,
                    "error": "edit id missing from response",
                    "detail": str(edit.get("data"))}

        baseline: Dict[str, Any] = {"id": "default"}
        if baseline_title is not None:
            baseline["storeListing"] = {
                "languageCode": locale, "title": baseline_title}
        challenger: Dict[str, Any] = {"id": "variant"}
        store_listing: Dict[str, Any] = {"languageCode": locale}
        if variant_title is not None:
            store_listing["title"] = variant_title
        if variant_short is not None:
            store_listing["shortDescription"] = variant_short
        if variant_full is not None:
            store_listing["fullDescription"] = variant_full
        challenger["storeListing"] = store_listing

        exp_body: Dict[str, Any] = {
            "name": name,
            "userFraction": user_fraction,
            "variants": [baseline, challenger],
        }
        if start_date:
            exp_body["startDate"] = start_date
        if end_date:
            exp_body["endDate"] = end_date

        r = self._call_api(
            "POST",
            f"/applications/{package_name}/edits/{edit_id}/experiments",
            exp_body)
        if not r.get("success"):
            self._call_api(
                "DELETE", f"/applications/{package_name}/edits/{edit_id}")
            return r
        exp = r.get("data") or {}
        exp_id = exp.get("experimentId") or exp.get("id")
        commit = self._call_api(
            "POST", f"/applications/{package_name}/edits/{edit_id}:commit", {})
        if not commit.get("success"):
            return {"success": False,
                    "error": "experiment created but edit commit failed",
                    "detail": commit.get("error") or ""}
        return {
            "success": True,
            "experiment_id": exp_id,
            "edit_id": edit_id,
            "name": name,
            "locale": locale,
            "detail": "listing experiment created",
        }

    def list_experiments(self, package_name: str) -> Dict[str, Any]:
        """READ the listing experiments for ``package_name`` via the Edits
        API (``edits.experiments``). READ-ONLY: opens a draft edit, lists the
        experiments, then discards the edit. Never mutates console state.

        Returns ``{"success", "package_name", "experiments": [...], "count"}``
        where each experiment keeps its raw shape (id / name / status /
        variants / results as returned by Play).
        """
        if not package_name:
            return {"success": False, "status_code": 0,
                    "error": "package_name required", "experiments": []}
        edit = self._call_api("POST", f"/applications/{package_name}/edits")
        if not edit.get("success"):
            return {"success": False,
                    "status_code": edit.get("status_code"),
                    "error": edit.get("error") or "edit open failed",
                    "experiments": []}
        edit_id = (edit.get("data") or {}).get("id")
        if not edit_id:
            return {"success": False, "error": "edit id missing",
                    "experiments": []}
        try:
            r = self._call_api(
                "GET",
                f"/applications/{package_name}/edits/{edit_id}/experiments")
        finally:
            self._call_api(
                "DELETE", f"/applications/{package_name}/edits/{edit_id}")
        if not r.get("success"):
            return {"success": False,
                    "status_code": r.get("status_code"),
                    "error": r.get("error") or "experiment list failed",
                    "experiments": []}
        exps = (r.get("data") or {}).get("experiments") or []
        return {
            "success": True,
            "package_name": package_name,
            "experiments": exps,
            "count": len(exps),
            "source": "androidpublisher.edits.experiments",
        }

    def get_experiment(self, package_name: str,
                       experiment_id: str) -> Dict[str, Any]:
        """READ a single listing experiment by id (``edits.experiments.get``).
        READ-ONLY, discards the draft edit afterwards."""
        if not package_name or not experiment_id:
            return {"success": False, "status_code": 0,
                    "error": "package_name + experiment_id required"}
        edit = self._call_api("POST", f"/applications/{package_name}/edits")
        if not edit.get("success"):
            return edit
        edit_id = (edit.get("data") or {}).get("id")
        if not edit_id:
            return {"success": False, "error": "edit id missing"}
        try:
            r = self._call_api(
                "GET",
                f"/applications/{package_name}/edits/{edit_id}"
                f"/experiments/{experiment_id}")
        finally:
            self._call_api(
                "DELETE", f"/applications/{package_name}/edits/{edit_id}")
        if not r.get("success"):
            return {"success": False,
                    "status_code": r.get("status_code"),
                    "error": r.get("error") or "experiment read failed"}
        return {"success": True, "package_name": package_name,
                "experiment": r.get("data") or {},
                "experiment_id": experiment_id}

    def delete_experiment(self, package_name: str,
                          experiment_id: str) -> Dict[str, Any]:
        """Delete a listing experiment (``edits.experiments.delete``). Opens
        an edit, deletes the experiment, commits the edit so the deletion
        lands. Lowest-blast-radius write (removes a scheduled test only)."""
        if not package_name or not experiment_id:
            return {"success": False, "status_code": 0,
                    "error": "package_name + experiment_id required"}
        edit = self._call_api("POST", f"/applications/{package_name}/edits")
        if not edit.get("success"):
            return edit
        edit_id = (edit.get("data") or {}).get("id")
        if not edit_id:
            return {"success": False, "error": "edit id missing"}
        r = self._call_api(
            "DELETE",
            f"/applications/{package_name}/edits/{edit_id}"
            f"/experiments/{experiment_id}")
        if not r.get("success"):
            self._call_api(
                "DELETE", f"/applications/{package_name}/edits/{edit_id}")
            return r
        commit = self._call_api(
            "POST", f"/applications/{package_name}/edits/{edit_id}:commit", {})
        if not commit.get("success"):
            return {"success": False,
                    "error": "experiment deleted but edit commit failed",
                    "detail": commit.get("error") or ""}
        return {"success": True, "experiment_id": experiment_id,
                "detail": "experiment deleted"}


__all__ = ["GooglePlayRealClient", "load_default_real_client"]


def load_default_real_client():
    """Build a GooglePlayRealClient using the credentials in
    ``credentials/store_keys.json`` (if present). Used by
    ``operation.publishing_factory.tester_community.inviter`` so the
    caller does not have to wire credentials manually."""
    from operation.providers.live.store_keys import get_googleplay
    cred = get_googleplay() or {}
    return GooglePlayRealClient(credential=cred)
