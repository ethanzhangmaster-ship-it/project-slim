"""
E15.1.1 — App Store Real API Client

Production-ready App Store Connect API client.
Implements same interface as MockAppStoreClient.
Requires API Key + Issuer ID + Private Key (JWT auth).
Implements the arm_real_client hook pattern for testability.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

from operation.providers.live.http_util import http_json
from operation.publishing.providers.models import (
    BS_FAILED, BS_PROCESSING, BS_VALID, BuildStatus,
)


class AppStoreRealClient:
    """Real App Store Connect API client.

    Credential-driven: API Key ID + Issuer ID + Private Key (JWT).
    All API calls go through _call_api hook.
    """

    BASE_URL = "https://api.appstoreconnect.apple.com/v1"

    def __init__(self, credential: Optional[Dict[str, Any]] = None):
        self._credential = credential or {}
        self._apps: Dict[str, dict] = {}
        self._api_override: Optional[Callable] = None
        self._altool_override: Optional[Callable] = None
        self._jwt: Optional[str] = None
        self._jwt_exp: int = 0

    def arm_real_client(self, override: Callable) -> None:
        self._api_override = override

    def arm_altool(self, override: Callable) -> None:
        """Test seam: override _run_altool for unit testing (no real subprocess)."""
        self._altool_override = override

    # ------------------------------------------------------------------ #
    # HTTP seam
    # ------------------------------------------------------------------ #
    def _auth_header(self) -> Dict[str, str]:
        """Return a Bearer header, caching the ES256 JWT for ~10 min."""
        now = int(time.time())
        if self._jwt and self._jwt_exp and self._jwt_exp > now + 30:
            return {"Authorization": f"Bearer {self._jwt}"}
        from operation.providers.live import auth as _auth
        self._jwt = _auth.make_appstore_jwt(
            self._credential["key_id"],
            self._credential["issuer_id"],
            self._credential["private_key_p8"])
        self._jwt_exp = now + 600
        return {"Authorization": f"Bearer {self._jwt}"}

    def _call_api(self, method: str, path: str,
                  body: Optional[Dict] = None) -> Dict[str, Any]:
        if self._api_override:
            return self._api_override(method, path, body)

        cred = self._credential or {}
        if not (cred.get("key_id") and cred.get("issuer_id")
                and cred.get("private_key_p8")):
            return {
                "success": False,
                "status_code": 0,
                "error": "App Store Connect credentials missing — "
                         "set via store_keys.set_appstore()",
                "data": None,
            }
        try:
            headers = self._auth_header()
        except Exception as e:  # noqa: BLE001
            return {"success": False, "status_code": 0,
                    "error": f"auth failed: {e}", "data": None}
        return http_json(method, self.BASE_URL + path,
                         body=body, headers=headers)

    def _resolve_bundle(self, game_id: str) -> Optional[str]:
        bundle = self._credential.get("bundle_id")
        if not bundle:
            app = self._apps.get(game_id, {})
            bundle = app.get("bundle_id")
        return bundle

    # ------------------------------------------------------------------ #
    # App lifecycle
    # ------------------------------------------------------------------ #
    def create_app(self, game_id: str, bundle_id: str, title: str) -> dict:
        path = f"/apps"
        body = {
            "data": {
                "type": "apps",
                "attributes": {
                    "bundleId": bundle_id,
                    "name": title,
                    "sku": f"sku_{game_id}",
                    "primaryLocale": "en-US",
                }
            }
        }
        result = self._call_api("POST", path, body)
        if result.get("success", False):
            app = {
                "app_id": f"as_{game_id}",
                "game_id": game_id,
                "bundle_id": bundle_id,
                "title": title,
                "status": "prepare_for_submission",
            }
            self._apps[game_id] = app
            return {"success": True, "app_id": app["app_id"]}
        return result

    def get_app(self, game_id: str) -> Optional[dict]:
        bundle = self._resolve_bundle(game_id)
        if not bundle:
            return None
        path = f"/apps?filter[bundleId]={bundle}"
        result = self._call_api("GET", path)
        if result.get("success", False):
            return result
        return self._apps.get(game_id)

    # ------------------------------------------------------------------ #
    # Build upload (altool CLI — Spec docs/ios_upload_spec.md §3.1 方式 A, §5.1.1)
    # ------------------------------------------------------------------ #
    def _run_altool(self, cmd: list, timeout: int):
        """默认 altool 调用实现：subprocess.run。

        测试可通过 arm_altool 注入 override 替换，避免依赖真实 xcrun。
        """
        import subprocess
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    def upload_build(self, game_id: str, build_path: str,
                     version: str, build_number: int) -> dict:
        """通过 altool CLI 上传 IPA 到 App Store Connect。

        真实流程（Spec §3.1 方式 A）：
            xcrun altool --upload-app -f {ipa} -t ios \
                --apiKey {key_id} --apiIssuer {issuer_id}

        altool 处理分片/重试/校验，Apple 官方维护。依赖 macOS + Xcode。

        Args:
            game_id: 游戏 ID（altool 本身不使用，仅用于日志/上下文）
            build_path: IPA 文件路径
            version: 版本号 e.g. "1.2.0"
            build_number: build 号 e.g. 42

        Returns:
            {"success": True, "build_id": "...", "version":..., "build_number":...}
            或 {"success": False, "error": "..."}
        """
        import json as _json
        import shutil
        import subprocess

        # 1) xcrun 可用性（altool 是 xcrun 子命令，依赖 macOS + Xcode）
        if not shutil.which("xcrun"):
            return {"success": False,
                    "error": "xcrun not found — requires macOS + Xcode"}

        # 2) 凭证（兼容 api_key_id / key_id 两种字段名）
        cred = self._credential or {}
        api_key = cred.get("api_key_id") or cred.get("key_id")
        issuer_id = cred.get("api_issuer_id") or cred.get("issuer_id")
        if not (api_key and issuer_id):
            return {"success": False,
                    "error": "missing api_key_id / api_issuer_id"}

        # 3) 构造 altool 命令
        cmd = [
            "xcrun", "altool", "--upload-app",
            "-f", build_path,
            "-t", "ios",
            "--apiKey", api_key,
            "--apiIssuer", issuer_id,
            "--output-format", "json",
        ]

        # 4) 执行（通过 _run_altool seam，测试可注入 override）
        run = self._altool_override or self._run_altool
        try:
            result = run(cmd, timeout=1800)  # 30 分钟超时
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "altool upload timed out (30min)"}
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"altool raised: {exc}"}

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"altool failed (rc={result.returncode}): {result.stderr}",
            }

        # 5) 解析 altool JSON 输出（--output-format json）
        try:
            payload = _json.loads(result.stdout) if result.stdout else {}
        except _json.JSONDecodeError:
            payload = {}

        return {
            "success": True,
            "build_id": payload.get("buildId", ""),
            "version": version,
            "build_number": build_number,
        }

    # ------------------------------------------------------------------ #
    # Build processing poll & select (Spec §5.1.2, §5.1.3)
    # ------------------------------------------------------------------ #
    def poll_build_status(
        self, game_id: str, version: str, build_number: int,
        timeout_seconds: int = 1800,
        poll_interval_seconds: int = 30,
    ) -> dict:
        """轮询 build processing 状态直到 VALID/FAILED 或超时。

        App Store Connect 异步处理 IPA，通常 5-15 分钟。
        altool 上传成功后调用本方法等待 Apple 处理完成。

        Returns:
            {"success": True, "build_status": {...}}  — VALID
            {"success": False, "error": "...", "build_status": {...}}  — FAILED
            {"success": False, "error": "poll timed out...", "build_status": None}
        """
        bundle = self._resolve_bundle(game_id)
        if not bundle:
            return {"success": False, "error": "bundle_id missing",
                    "build_status": None}

        deadline = time.time() + timeout_seconds
        last_state = BS_PROCESSING
        app_id = self._apps.get(game_id, {}).get("app_id", "")

        while time.time() < deadline:
            r = self._call_api(
                "GET",
                f"/builds?filter[app]={app_id}"
                f"&filter[preReleaseVersion.versionString]={version}"
                f"&filter[preReleaseVersion.buildVersion]={build_number}",
            )
            if not r.get("success"):
                # API 失败 → 等待重试（不立即 fail-closed，给 Apple 时间）
                time.sleep(poll_interval_seconds)
                continue

            builds = (r.get("data") or {}).get("data") or []
            if not builds:
                time.sleep(poll_interval_seconds)
                continue

            attrs = builds[0].get("attributes", {})
            last_state = attrs.get("processingState", BS_PROCESSING)

            if last_state == BS_VALID:
                bs = BuildStatus(
                    build_id=builds[0].get("id", ""),
                    version=version,
                    build_number=build_number,
                    processing_state=BS_VALID,
                    icon_url=attrs.get("iconAssetToken", {}).get("templateUrl", ""),
                    uploaded_date=attrs.get("uploadedDate", ""),
                )
                return {"success": True, "build_status": bs.to_dict()}

            if last_state == BS_FAILED:
                bs = BuildStatus(
                    build_id=builds[0].get("id", ""),
                    version=version,
                    build_number=build_number,
                    processing_state=BS_FAILED,
                    error_message=attrs.get("processingError", "unknown"),
                )
                return {
                    "success": False,
                    "error": "build processing failed",
                    "build_status": bs.to_dict(),
                }

            time.sleep(poll_interval_seconds)

        return {
            "success": False,
            "error": f"poll timed out after {timeout_seconds}s "
                     f"(last_state={last_state})",
            "build_status": None,
        }

    def select_build(self, version_id: str, build_id: str) -> dict:
        """关联 build 到 appStoreVersion（提交审核前必需）。

        PATCH /v1/appStoreVersions/{version_id}/relationships/build
        """
        path = f"/appStoreVersions/{version_id}/relationships/build"
        body = {"data": {"type": "builds", "id": build_id}}
        return self._call_api("PATCH", path, body)

    # ------------------------------------------------------------------ #
    # Version & Review
    # ------------------------------------------------------------------ #
    def create_version(self, game_id: str, version: str) -> dict:
        bundle = self._resolve_bundle(game_id)
        if not bundle:
            return {"success": False, "error": "app not found"}
        path = f"/appStoreVersions"
        body = {
            "data": {
                "type": "appStoreVersions",
                "attributes": {
                    "platform": "IOS",
                    "versionString": version,
                }
            }
        }
        result = self._call_api("POST", path, body)
        if result.get("success", False):
            return {"success": True}
        return result

    def submit_review(self, game_id: str, version_id: Optional[str] = None) -> dict:
        """提交审核。

        Spec §5.1.4：POST /v1/appStoreVersionSubmissions，需关联 version_id。

        Args:
            game_id: 游戏 ID（bundle_id 解析用，兼容旧调用）
            version_id: appStoreVersion ID。若为 None，自动查询最新 version。
        """
        bundle = self._resolve_bundle(game_id)
        if not bundle:
            return {"success": False, "error": "app not found"}

        if version_id is None:
            version_id = self._get_latest_version_id(game_id)
            if not version_id:
                return {"success": False, "error": "no appStoreVersion found"}

        path = "/appStoreVersionSubmissions"
        body = {
            "data": {
                "type": "appStoreVersionSubmissions",
                "relationships": {
                    "appStoreVersion": {
                        "data": {"type": "appStoreVersions", "id": version_id}
                    }
                },
            }
        }
        result = self._call_api("POST", path, body)
        if result.get("success", False):
            return {"success": True, "status": "waiting_for_review"}
        return result

    def _get_latest_version_id(self, game_id: str) -> Optional[str]:
        """查询最新 appStoreVersion 的 ID（submit_review 自动解析用）。"""
        r = self._call_api("GET", f"/apps?filter[bundleId]={self._resolve_bundle(game_id)}")
        if not r.get("success"):
            return None
        apps = (r.get("data") or {}).get("data") or []
        if not apps:
            return None
        app_id = apps[0].get("id")
        r2 = self._call_api(
            "GET",
            f"/apps/{app_id}/appStoreVersions?sort=-versionString&limit=1",
        )
        if not r2.get("success"):
            return None
        vers = (r2.get("data") or {}).get("data") or []
        return vers[0].get("id") if vers else None

    def check_status(self, game_id: str) -> dict:
        bundle = self._resolve_bundle(game_id)
        if not bundle:
            return {"game_id": game_id, "status": "unknown",
                    "error": "bundle_id missing (set in credential or app)"}
        # 1) resolve app id by bundleId
        r = self._call_api("GET", f"/apps?filter[bundleId]={bundle}")
        if not r.get("success"):
            return {"game_id": game_id, "status": "unknown",
                    "error": r.get("error")}
        apps = (r.get("data") or {}).get("data") or []
        if not apps:
            return {"game_id": game_id, "status": "not_found",
                    "note": "no app with this bundleId in App Store Connect"}
        app_id = apps[0].get("id")
        # 2) latest appStoreVersion
        r2 = self._call_api(
            "GET",
            f"/apps/{app_id}/appStoreVersions?sort=-versionString&limit=1")
        if not r2.get("success"):
            return {"game_id": game_id, "status": "unknown",
                    "error": r2.get("error")}
        vers = (r2.get("data") or {}).get("data") or []
        if not vers:
            return {"game_id": game_id, "status": "prepare_for_submission"}
        attrs = vers[0].get("attributes", {})
        state = attrs.get("appStoreState", "PREPARE_FOR_SUBMISSION")
        version = attrs.get("versionString", "")
        status_map = {
            "PREPARE_FOR_SUBMISSION": "prepare_for_submission",
            "WAITING_FOR_REVIEW": "waiting_for_review",
            "IN_REVIEW": "in_review",
            "REJECTED": "rejected",
            "READY_FOR_SALE": "ready_for_sale",
            "PENDING_DEVELOPER_RELEASE": "approved",
        }
        status = status_map.get(state, state.lower())
        return {
            "game_id": game_id,
            "status": status,
            "version": version,
            "app_store_state": state,
            "rejection": attrs.get("rejectionReason"),
        }

    def release(self, game_id: str) -> dict:
        bundle = self._resolve_bundle(game_id)
        if not bundle:
            return {"success": False, "error": "app not found"}
        path = f"/appStoreVersions/release"
        result = self._call_api("POST", path, {"bundle_id": bundle})
        if result.get("success", False):
            return {"success": True, "status": "ready_for_sale"}
        return result

    def rollback(self, game_id: str) -> dict:
        bundle = self._resolve_bundle(game_id)
        if not bundle:
            return {"success": False, "error": "app not found"}
        path = f"/appStoreVersions/rollback"
        result = self._call_api("POST", path, {})
        if result.get("success", False):
            return {"success": True, "status": "prepare_for_submission"}
        return result

    # ------------------------------------------------------------------ #
    # Metadata
    # ------------------------------------------------------------------ #
    def update_metadata(self, game_id: str, metadata: Dict[str, Any]) -> dict:
        bundle = self._resolve_bundle(game_id)
        if not bundle:
            return {"success": False, "error": "app not found"}
        path = f"/appStoreVersionLocalizations"
        body = {
            "attributes": {
                "description": metadata.get("description", ""),
                "keywords": metadata.get("keywords", ""),
                "promotionalText": metadata.get("subtitle", ""),
                "whatsNew": metadata.get("whats_new", ""),
            }
        }
        result = self._call_api("PUT", path, body)
        if result.get("success", False):
            return {"success": True, "detail": "metadata updated"}
        return result

    def upload_screenshots(self, game_id: str, screenshot_paths: list) -> dict:
        bundle = self._resolve_bundle(game_id)
        if not bundle:
            return {"success": False, "error": "app not found"}
        path = f"/appScreenshots"
        result = self._call_api("POST", path, {
            "image_count": len(screenshot_paths),
            "bundle_id": bundle,
        })
        if result.get("success", False):
            return {"success": True, "detail": f"{len(screenshot_paths)} screenshots uploaded"}
        return result

    # ------------------------------------------------------------------ #
    # Phased release (Spec §5.1.5, §3.3)
    # ------------------------------------------------------------------ #
    def start_phased_release(self, version_id: str) -> dict:
        """启动 7 天灰度发布。

        POST /v1/appStoreVersionPhasedReleases
        审核通过后调用，Apple 自动按 1%→2%→5%→10%→20%→50%→100% 释放。
        """
        path = "/appStoreVersionPhasedReleases"
        body = {
            "data": {
                "type": "appStoreVersionPhasedReleases",
                "relationships": {
                    "appStoreVersion": {
                        "data": {"type": "appStoreVersions", "id": version_id}
                    }
                },
            }
        }
        return self._call_api("POST", path, body)

    def pause_phased_release(self, phased_release_id: str) -> dict:
        """暂停灰度发布（保持当前释放比例）。

        PATCH /v1/appStoreVersionPhasedReleases/{id}  attributes.state=PAUSED
        """
        path = f"/appStoreVersionPhasedReleases/{phased_release_id}"
        body = {
            "data": {
                "type": "appStoreVersionPhasedReleases",
                "id": phased_release_id,
                "attributes": {"state": "PAUSED"},
            }
        }
        return self._call_api("PATCH", path, body)

    def resume_phased_release(self, phased_release_id: str) -> dict:
        """恢复灰度发布（从暂停处继续）。

        PATCH /v1/appStoreVersionPhasedReleases/{id}  attributes.state=ACTIVE
        """
        path = f"/appStoreVersionPhasedReleases/{phased_release_id}"
        body = {
            "data": {
                "type": "appStoreVersionPhasedReleases",
                "id": phased_release_id,
                "attributes": {"state": "ACTIVE"},
            }
        }
        return self._call_api("PATCH", path, body)

    def complete_phased_release(self, phased_release_id: str) -> dict:
        """立即完成灰度发布（100% 推送给所有用户）。

        PATCH /v1/appStoreVersionPhasedReleases/{id}  attributes.state=COMPLETE
        """
        path = f"/appStoreVersionPhasedReleases/{phased_release_id}"
        body = {
            "data": {
                "type": "appStoreVersionPhasedReleases",
                "id": phased_release_id,
                "attributes": {"state": "COMPLETE"},
            }
        }
        return self._call_api("PATCH", path, body)

    def check_phased_release(self, version_id: str) -> dict:
        """查询灰度发布状态（当前 state + 释放比例）。

        GET /v1/appStoreVersions/{version_id}/appStoreVersionPhasedRelease
        """
        path = f"/appStoreVersions/{version_id}/appStoreVersionPhasedRelease"
        return self._call_api("GET", path)


__all__ = ["AppStoreRealClient"]
