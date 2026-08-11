"""
E15.1.1 — Publishing Provider Contract (models)
=================================================

Mirrors E14 monetization/providers/models.py. Defines:
  * PublishingChange    — atomic, reversible publishing operation
  * PublishingResult    — unified return type
  * PublishingStatus    — review lifecycle states

Reuses from monetization/providers:
  * SandboxMode (SIMULATION|SHADOW|PRODUCTION)
  * CredentialRef
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from monetization.providers.models import CredentialRef, SandboxMode


def _uid(prefix: str = "pub") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Publishing status vocabulary
# --------------------------------------------------------------------------- #
# Google Play states
GP_DRAFT = "draft"
GP_IN_REVIEW = "in_review"
GP_REJECTED = "rejected"
GP_APPROVED = "approved"
GP_PUBLISHED = "published"

# App Store states
AS_PREPARE = "prepare_for_submission"
AS_WAITING = "waiting_for_review"
AS_IN_REVIEW = "in_review"
AS_REJECTED = "rejected"
AS_READY = "ready_for_sale"

# operation types
OP_CREATE_APP = "create_app"
OP_UPLOAD_BUILD = "upload_build"
OP_CREATE_RELEASE = "create_release"
OP_SUBMIT_REVIEW = "submit_review"
OP_CHECK_STATUS = "check_status"
OP_ROLLBACK = "rollback_release"
OP_UPDATE_METADATA = "update_metadata"
OP_RELEASE = "release_to_production"
OP_HEALTH_CHECK = "health_check"

# iOS App Store build upload & phased release (Spec docs/ios_upload_spec.md §4.1)
OP_UPLOAD_BUILD_ALTOOL = "upload_build_altool"          # altool CLI 上传 IPA
OP_POLL_BUILD_STATUS = "poll_build_status"              # 轮询 build processing 状态
OP_SELECT_BUILD = "select_build"                        # 关联 build 到 version
OP_START_PHASED_RELEASE = "start_phased_release"        # 启动 7 天灰度发布
OP_PAUSE_PHASED_RELEASE = "pause_phased_release"        # 暂停灰度发布
OP_RESUME_PHASED_RELEASE = "resume_phased_release"      # 恢复灰度发布
OP_COMPLETE_PHASED_RELEASE = "complete_phased_release"  # 立即完成灰度发布（100%）
OP_CHECK_PHASED_RELEASE = "check_phased_release"        # 查询灰度发布状态


# --------------------------------------------------------------------------- #
# PublishingChange
# --------------------------------------------------------------------------- #
@dataclass
class PublishingChange:
    """One atomic, reversible publishing operation.

    target example: "game_A/google_play/release_1.0.0"
    """
    target: str
    operation: str                              # OP_* constant
    provider: str = ""                          # "google_play" | "app_store"
    game_id: str = ""
    old: Any = None                             # for rollback
    new: Any = None                             # desired state (build_path, metadata, ...)
    note: str = ""
    sandbox: SandboxMode = SandboxMode.SIMULATION
    credential_ref: Optional[CredentialRef] = None
    change_id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "operation": self.operation,
            "provider": self.provider,
            "game_id": self.game_id,
            "note": self.note,
            "sandbox": self.sandbox.value,
            "credential_ref": self.credential_ref.to_dict() if self.credential_ref else None,
            "change_id": self.change_id,
            "created_at": self.created_at,
        }


# --------------------------------------------------------------------------- #
# PublishingResult
# --------------------------------------------------------------------------- #
@dataclass
class PublishingResult:
    """Unified return type for every publishing provider call."""
    provider: str                               # "google_play" | "app_store"
    operation: str                              # OP_* constant
    success: bool
    latency_ms: float = 0.0
    real_api_called: bool = False               # must be False in SIM/SHADOW
    change_id: str = ""
    detail: str = ""
    error: str = ""
    before: Any = None
    after: Any = None
    sandbox: str = "simulation"
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "operation": self.operation,
            "success": self.success,
            "latency_ms": self.latency_ms,
            "real_api_called": self.real_api_called,
            "change_id": self.change_id,
            "detail": self.detail,
            "error": self.error,
            "sandbox": self.sandbox,
            "extra": self.extra,
        }


# --------------------------------------------------------------------------- #
# Publishing status event
# --------------------------------------------------------------------------- #
@dataclass
class PublishingStatus:
    game_id: str
    platform: str                               # "android" | "ios"
    store: str                                  # "google_play" | "app_store"
    status: str                                 # GP_* / AS_* constants
    version: str = ""
    rejection_reason: str = ""
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id, "platform": self.platform,
            "store": self.store, "status": self.status,
            "version": self.version, "rejection_reason": self.rejection_reason,
            "updated_at": self.updated_at,
        }


# --------------------------------------------------------------------------- #
# Build processing status (iOS App Store Connect)
# Spec: docs/ios_upload_spec.md §4.3
# --------------------------------------------------------------------------- #
BS_PROCESSING = "PROCESSING"
BS_VALID = "VALID"
BS_FAILED = "FAILED"


@dataclass
class BuildStatus:
    """App Store Connect build processing 状态。

    altool 上传 IPA 后 Apple 异步处理，通过 poll_build_status 轮询得到。
    VALID → 可关联到 appStoreVersion 提交审核；FAILED → 阻塞人工介入。
    """
    build_id: str                               # App Store Connect build ID
    version: str                                # e.g. "1.2.0"
    build_number: int                           # e.g. 42
    processing_state: str                       # BS_PROCESSING | BS_VALID | BS_FAILED
    icon_url: str = ""
    uploaded_date: str = ""
    # FAILED 时填充
    error_code: str = ""
    error_message: str = ""

    @property
    def is_valid(self) -> bool:
        return self.processing_state == BS_VALID

    @property
    def is_processing(self) -> bool:
        return self.processing_state == BS_PROCESSING

    @property
    def is_failed(self) -> bool:
        return self.processing_state == BS_FAILED

    def to_dict(self) -> dict:
        return {
            "build_id": self.build_id,
            "version": self.version,
            "build_number": self.build_number,
            "processing_state": self.processing_state,
            "icon_url": self.icon_url,
            "uploaded_date": self.uploaded_date,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


__all__ = [
    "PublishingChange", "PublishingResult", "PublishingStatus", "BuildStatus",
    "SandboxMode", "CredentialRef",
    "GP_DRAFT", "GP_IN_REVIEW", "GP_REJECTED", "GP_APPROVED", "GP_PUBLISHED",
    "AS_PREPARE", "AS_WAITING", "AS_IN_REVIEW", "AS_REJECTED", "AS_READY",
    "BS_PROCESSING", "BS_VALID", "BS_FAILED",
    "OP_CREATE_APP", "OP_UPLOAD_BUILD", "OP_CREATE_RELEASE",
    "OP_SUBMIT_REVIEW", "OP_CHECK_STATUS", "OP_ROLLBACK",
    "OP_UPDATE_METADATA", "OP_RELEASE", "OP_HEALTH_CHECK",
    # iOS App Store build upload & phased release (ios_upload_spec.md §4.1)
    "OP_UPLOAD_BUILD_ALTOOL", "OP_POLL_BUILD_STATUS", "OP_SELECT_BUILD",
    "OP_START_PHASED_RELEASE", "OP_PAUSE_PHASED_RELEASE",
    "OP_RESUME_PHASED_RELEASE", "OP_COMPLETE_PHASED_RELEASE",
    "OP_CHECK_PHASED_RELEASE",
]
