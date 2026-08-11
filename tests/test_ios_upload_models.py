"""iOS App Store 上架能力 — D16 models 单元测试

Spec: docs/ios_upload_spec.md §4.1 (操作常量) + §4.3 (BuildStatus)

覆盖：
  * 8 个新增 iOS 操作常量存在且字符串值符合 Spec
  * 3 个 BS_* build processing 状态常量
  * BuildStatus 数据类：构造 / 状态属性 / to_dict
  * PublishingChange 可承载新操作（集成兼容）
  * __all__ 导出完整（防止漏导出）
  * 现有常量与类不受影响（回归安全）
"""
from __future__ import annotations

import inspect

from operation.publishing.providers import models as M
from operation.publishing.providers.models import (
    AS_IN_REVIEW, AS_PREPARE, AS_READY, AS_REJECTED, AS_WAITING,
    BS_FAILED, BS_PROCESSING, BS_VALID,
    BuildStatus,
    GP_APPROVED, GP_DRAFT, GP_IN_REVIEW, GP_PUBLISHED, GP_REJECTED,
    OP_CHECK_PHASED_RELEASE, OP_CHECK_STATUS, OP_COMPLETE_PHASED_RELEASE,
    OP_CREATE_APP, OP_CREATE_RELEASE, OP_HEALTH_CHECK, OP_PAUSE_PHASED_RELEASE,
    OP_POLL_BUILD_STATUS, OP_RELEASE, OP_RESUME_PHASED_RELEASE, OP_ROLLBACK,
    OP_SELECT_BUILD, OP_START_PHASED_RELEASE, OP_SUBMIT_REVIEW,
    OP_UPDATE_METADATA, OP_UPLOAD_BUILD, OP_UPLOAD_BUILD_ALTOOL,
    PublishingChange, PublishingResult, PublishingStatus,
)
from monetization.providers.models import CredentialRef, SandboxMode


# --------------------------------------------------------------------------- #
# Spec §4.1 — 新增 iOS 操作常量
# --------------------------------------------------------------------------- #
class TestIOSOperationConstants:
    """验证 8 个新增操作常量的字符串值与 Spec §4.1 一致。"""

    def test_build_upload_constants(self):
        assert OP_UPLOAD_BUILD_ALTOOL == "upload_build_altool"
        assert OP_POLL_BUILD_STATUS == "poll_build_status"
        assert OP_SELECT_BUILD == "select_build"

    def test_phased_release_constants(self):
        assert OP_START_PHASED_RELEASE == "start_phased_release"
        assert OP_PAUSE_PHASED_RELEASE == "pause_phased_release"
        assert OP_RESUME_PHASED_RELEASE == "resume_phased_release"
        assert OP_COMPLETE_PHASED_RELEASE == "complete_phased_release"
        assert OP_CHECK_PHASED_RELEASE == "check_phased_release"

    def test_new_constants_are_unique_strings(self):
        new_constants = [
            OP_UPLOAD_BUILD_ALTOOL, OP_POLL_BUILD_STATUS, OP_SELECT_BUILD,
            OP_START_PHASED_RELEASE, OP_PAUSE_PHASED_RELEASE,
            OP_RESUME_PHASED_RELEASE, OP_COMPLETE_PHASED_RELEASE,
            OP_CHECK_PHASED_RELEASE,
        ]
        # 全部为非空字符串
        assert all(isinstance(c, str) and c for c in new_constants)
        # 互不重复
        assert len(set(new_constants)) == 8
        # 不与现有常量冲突
        existing = {
            OP_CREATE_APP, OP_UPLOAD_BUILD, OP_CREATE_RELEASE,
            OP_SUBMIT_REVIEW, OP_CHECK_STATUS, OP_ROLLBACK,
            OP_UPDATE_METADATA, OP_RELEASE, OP_HEALTH_CHECK,
        }
        assert not (set(new_constants) & existing)

    def test_new_constants_exported_in_all(self):
        new_names = {
            "OP_UPLOAD_BUILD_ALTOOL", "OP_POLL_BUILD_STATUS", "OP_SELECT_BUILD",
            "OP_START_PHASED_RELEASE", "OP_PAUSE_PHASED_RELEASE",
            "OP_RESUME_PHASED_RELEASE", "OP_COMPLETE_PHASED_RELEASE",
            "OP_CHECK_PHASED_RELEASE",
        }
        assert new_names.issubset(set(M.__all__))


# --------------------------------------------------------------------------- #
# Spec §4.3 — BuildStatus 数据类
# --------------------------------------------------------------------------- #
class TestBuildStatus:
    def test_construct_minimal(self):
        bs = BuildStatus(
            build_id="bld_123", version="1.2.0",
            build_number=42, processing_state=BS_PROCESSING,
        )
        assert bs.build_id == "bld_123"
        assert bs.version == "1.2.0"
        assert bs.build_number == 42
        assert bs.processing_state == BS_PROCESSING
        # 默认值
        assert bs.icon_url == ""
        assert bs.uploaded_date == ""
        assert bs.error_code == ""
        assert bs.error_message == ""

    def test_state_properties_processing(self):
        bs = BuildStatus("b1", "1.0.0", 1, BS_PROCESSING)
        assert bs.is_processing is True
        assert bs.is_valid is False
        assert bs.is_failed is False

    def test_state_properties_valid(self):
        bs = BuildStatus("b1", "1.0.0", 1, BS_VALID)
        assert bs.is_valid is True
        assert bs.is_processing is False
        assert bs.is_failed is False

    def test_state_properties_failed(self):
        bs = BuildStatus(
            "b1", "1.0.0", 1, BS_FAILED,
            error_code="INVALID_SIGNING", error_message="missing provisioning profile",
        )
        assert bs.is_failed is True
        assert bs.is_valid is False
        assert bs.is_processing is False
        assert bs.error_code == "INVALID_SIGNING"
        assert bs.error_message == "missing provisioning profile"

    def test_to_dict_round_trip(self):
        bs = BuildStatus(
            build_id="bld_99", version="2.0.1", build_number=7,
            processing_state=BS_VALID,
            icon_url="https://example.com/icon.png",
            uploaded_date="2026-08-06T10:00:00Z",
        )
        d = bs.to_dict()
        assert d == {
            "build_id": "bld_99",
            "version": "2.0.1",
            "build_number": 7,
            "processing_state": BS_VALID,
            "icon_url": "https://example.com/icon.png",
            "uploaded_date": "2026-08-06T10:00:00Z",
            "error_code": "",
            "error_message": "",
        }

    def test_bs_state_constants_values(self):
        assert BS_PROCESSING == "PROCESSING"
        assert BS_VALID == "VALID"
        assert BS_FAILED == "FAILED"

    def test_build_status_exported_in_all(self):
        assert "BuildStatus" in M.__all__
        assert "BS_PROCESSING" in M.__all__
        assert "BS_VALID" in M.__all__
        assert "BS_FAILED" in M.__all__

    def test_build_status_is_dataclass(self):
        # dataclass 有 __dataclass_fields__
        assert hasattr(BuildStatus, "__dataclass_fields__")
        fields = set(BuildStatus.__dataclass_fields__)
        assert {
            "build_id", "version", "build_number", "processing_state",
            "icon_url", "uploaded_date", "error_code", "error_message",
        }.issubset(fields)


# --------------------------------------------------------------------------- #
# PublishingChange 承载新操作（集成兼容）
# --------------------------------------------------------------------------- #
class TestPublishingChangeWithNewOps:
    """新操作常量可作为 PublishingChange.operation 使用（Spec §4.2）。"""

    def test_upload_build_altool_change(self):
        change = PublishingChange(
            target="game_A/app_store/release_1.2.0",
            operation=OP_UPLOAD_BUILD_ALTOOL,
            provider="app_store",
            game_id="game_A",
            new={
                "ipa_path": "/path/to/app.ipa",
                "version": "1.2.0",
                "build_number": 42,
                "api_key_id": "KEY",
                "api_issuer_id": "ISSUER",
            },
        )
        assert change.operation == OP_UPLOAD_BUILD_ALTOOL
        d = change.to_dict()
        assert d["operation"] == "upload_build_altool"
        assert d["provider"] == "app_store"
        assert d["game_id"] == "game_A"

    def test_poll_build_status_change(self):
        change = PublishingChange(
            target="game_A/app_store/poll",
            operation=OP_POLL_BUILD_STATUS,
            provider="app_store",
            game_id="game_A",
            new={"version": "1.2.0", "build_number": 42, "timeout_seconds": 1800},
        )
        assert change.operation == OP_POLL_BUILD_STATUS
        assert change.change_id  # 自动生成
        assert change.created_at  # 自动生成

    def test_phased_release_changes(self):
        for op in (
            OP_START_PHASED_RELEASE, OP_PAUSE_PHASED_RELEASE,
            OP_RESUME_PHASED_RELEASE, OP_COMPLETE_PHASED_RELEASE,
            OP_CHECK_PHASED_RELEASE,
        ):
            change = PublishingChange(
                target=f"game_A/app_store/{op}",
                operation=op,
                provider="app_store",
                game_id="game_A",
                new={"version_id": "v1.2.0", "phased_release_id": "pr_1"},
            )
            assert change.operation == op
            assert change.to_dict()["operation"] == op

    def test_change_supports_credential_ref(self):
        cred = CredentialRef(
            game_id="game_A", provider="app_store", key_ref="credentials/game_A/appstore",
        )
        change = PublishingChange(
            target="game_A/app_store/release_1.2.0",
            operation=OP_SELECT_BUILD,
            provider="app_store",
            game_id="game_A",
            new={"version_id": "v1.2.0", "build_id": "bld_42"},
            sandbox=SandboxMode.PRODUCTION,
            credential_ref=cred,
        )
        d = change.to_dict()
        assert d["sandbox"] == "production"
        assert d["credential_ref"]["key_ref"] == "credentials/game_A/appstore"
        assert d["credential_ref"]["provider"] == "app_store"


# --------------------------------------------------------------------------- #
# 回归安全 — 现有常量与类不受影响
# --------------------------------------------------------------------------- #
class TestRegressionSafety:
    def test_existing_status_constants_unchanged(self):
        assert GP_DRAFT == "draft"
        assert GP_IN_REVIEW == "in_review"
        assert GP_REJECTED == "rejected"
        assert GP_APPROVED == "approved"
        assert GP_PUBLISHED == "published"
        assert AS_PREPARE == "prepare_for_submission"
        assert AS_WAITING == "waiting_for_review"
        assert AS_IN_REVIEW == "in_review"
        assert AS_REJECTED == "rejected"
        assert AS_READY == "ready_for_sale"

    def test_existing_op_constants_unchanged(self):
        assert OP_CREATE_APP == "create_app"
        assert OP_UPLOAD_BUILD == "upload_build"
        assert OP_CREATE_RELEASE == "create_release"
        assert OP_SUBMIT_REVIEW == "submit_review"
        assert OP_CHECK_STATUS == "check_status"
        assert OP_ROLLBACK == "rollback_release"
        assert OP_UPDATE_METADATA == "update_metadata"
        assert OP_RELEASE == "release_to_production"
        assert OP_HEALTH_CHECK == "health_check"

    def test_existing_classes_still_present(self):
        assert inspect.isclass(PublishingChange)
        assert inspect.isclass(PublishingResult)
        assert inspect.isclass(PublishingStatus)

    def test_existing_exports_preserved_in_all(self):
        must_have = {
            "PublishingChange", "PublishingResult", "PublishingStatus",
            "SandboxMode", "CredentialRef",
            "GP_DRAFT", "GP_IN_REVIEW", "GP_REJECTED", "GP_APPROVED", "GP_PUBLISHED",
            "AS_PREPARE", "AS_WAITING", "AS_IN_REVIEW", "AS_REJECTED", "AS_READY",
            "OP_CREATE_APP", "OP_UPLOAD_BUILD", "OP_CREATE_RELEASE",
            "OP_SUBMIT_REVIEW", "OP_CHECK_STATUS", "OP_ROLLBACK",
            "OP_UPDATE_METADATA", "OP_RELEASE", "OP_HEALTH_CHECK",
        }
        assert must_have.issubset(set(M.__all__))
