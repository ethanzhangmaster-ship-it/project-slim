"""E13.7 Real Execution Layer — 测试套件.

覆盖:
  - Adapter Models (ExecutionMode, APIRequest/Response, RealExecutionResult, VerificationResult, AdapterMetrics)
  - Meta Executor (MetaAPIClient, MetaExecutor, 动作分发, 干运行, 回滚)
  - Creative Executor (CreativeAsset, CreativeGenerationClient, CreativeExecutor, 素材生命周期)
  - Adjust Verifier (AdjustDataClient, AdjustVerifier, VerificationConfig, 校验, 批量)
  - Execution Policy (ExecutionPolicy, PolicyEngine, PolicyDecision, 模式解析, 降级, 审批)
  - Executor Gateway (GatewayResult, ExecutorGateway, 路由, 降级, 审批, 批量)
  - Integration (完整链路: Action → Gateway → Executor → Verifier → Result)
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from market_ops.creative_vision_runtime.growth_runtime.execution import (
    ExecutionAction,
    ExecutionActionType,
    ExecutionDomain,
    ExecutionPriority,
    ExecutionResult,
    ExecutionResultStatus,
    GuardContext,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.adapters import (
    ACTION_RISK_MAP,
    APIRequest,
    APIResponse,
    AdapterMetrics,
    AdjustDataClient,
    AdjustVerifier,
    ActionRiskLevel,
    CreativeAsset,
    CreativeExecutor,
    CreativeGenerationClient,
    DegradeReason,
    ExecutionMode,
    ExecutionPolicy,
    ExecutorGateway,
    GatewayResult,
    GatewayResultStatus,
    MetaAPIClient,
    MetaExecutor,
    PlatformType,
    PolicyDecision,
    PolicyEngine,
    PolicyMode,
    RealExecutionResult,
    VerificationConfig,
    VerificationResult,
    create_conservative_policy,
    create_development_policy,
    create_full_auto_policy,
    create_safe_real_policy,
    create_testing_policy,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def make_action(
    action_type: ExecutionActionType = ExecutionActionType.MONITOR,
    domain: ExecutionDomain = ExecutionDomain.MONITOR,
    **params,
) -> ExecutionAction:
    """创建测试用 ExecutionAction."""
    return ExecutionAction(
        action_type=action_type,
        domain=domain,
        parameters=params,
    )


def make_guard_context(
    risk_level: str = "safe",
    requires_approval: bool = False,
    confidence: float = 0.8,
    budget_impact: float = 0.0,
) -> GuardContext:
    """创建测试用 GuardContext."""
    return GuardContext(
        risk_level=risk_level,
        requires_approval=requires_approval,
        confidence=confidence,
        budget_impact=budget_impact,
    )


# ═══════════════════════════════════════════════════════════════
# 1. Adapter Models
# ═══════════════════════════════════════════════════════════════


class TestExecutionMode:
    """测试 ExecutionMode 枚举."""

    def test_mode_values(self):
        assert ExecutionMode.MOCK == "mock"
        assert ExecutionMode.DRY_RUN == "dry_run"
        assert ExecutionMode.REAL == "real"
        assert ExecutionMode.APPROVAL_REQUIRED == "approval_required"

    def test_mode_string_conversion(self):
        assert ExecutionMode("mock") == ExecutionMode.MOCK
        assert ExecutionMode("real") == ExecutionMode.REAL


class TestPlatformType:
    """测试 PlatformType 枚举."""

    def test_platform_values(self):
        assert PlatformType.META == "meta"
        assert PlatformType.ADJUST == "adjust"
        assert PlatformType.INTERNAL == "internal"


class TestAPIRequest:
    """测试 APIRequest 模型."""

    def test_default_creation(self):
        req = APIRequest()
        assert req.platform == PlatformType.META
        assert req.method == "POST"
        assert req.max_retries == 3
        assert req.retry_count == 0

    def test_custom_creation(self):
        req = APIRequest(
            platform=PlatformType.ADJUST,
            method="GET",
            endpoint="/v1/metrics",
            body={"key": "value"},
            timeout_seconds=60,
        )
        assert req.platform == PlatformType.ADJUST
        assert req.method == "GET"
        assert req.endpoint == "/v1/metrics"
        assert req.body == {"key": "value"}
        assert req.timeout_seconds == 60

    def test_request_id_auto_generated(self):
        req1 = APIRequest()
        req2 = APIRequest()
        assert req1.request_id != req2.request_id


class TestAPIResponse:
    """测试 APIResponse 模型."""

    def test_default_creation(self):
        resp = APIResponse()
        assert resp.status_code == 0
        assert resp.success is False

    def test_success_response(self):
        resp = APIResponse(
            status_code=200,
            success=True,
            data={"id": "camp_123"},
            platform_id="camp_123",
        )
        assert resp.success is True
        assert resp.platform_id == "camp_123"

    def test_error_response(self):
        resp = APIResponse(
            status_code=500,
            success=False,
            error_code="INTERNAL_ERROR",
            error_message="Server error",
        )
        assert resp.success is False
        assert resp.is_retryable is True

    def test_rate_limited(self):
        resp = APIResponse(status_code=429)
        assert resp.is_rate_limited is True
        assert resp.is_retryable is True

    def test_not_retryable(self):
        resp = APIResponse(status_code=400)
        assert resp.is_retryable is False


class TestRealExecutionResult:
    """测试 RealExecutionResult 模型."""

    def test_default_creation(self):
        result = RealExecutionResult()
        assert result.platform == PlatformType.META
        assert result.mode == ExecutionMode.MOCK
        assert result.success is False

    def test_success_result(self):
        api_req = APIRequest(method="POST", endpoint="/campaigns")
        api_resp = APIResponse(
            status_code=200,
            success=True,
            platform_id="camp_456",
            latency_ms=100.0,
        )
        result = RealExecutionResult(
            action_id="act_1",
            action_type="create_campaign",
            platform=PlatformType.META,
            mode=ExecutionMode.REAL,
            success=True,
            api_request=api_req,
            api_response=api_resp,
            platform_entity_id="camp_456",
        )
        assert result.success is True
        assert result.platform_entity_id == "camp_456"
        assert result.duration_ms == 100.0

    def test_to_dict(self):
        result = RealExecutionResult(
            action_id="act_1",
            action_type="create_campaign",
            success=True,
            platform_entity_id="camp_789",
        )
        d = result.to_dict()
        assert d["action_id"] == "act_1"
        assert d["platform_entity_id"] == "camp_789"
        assert d["success"] is True
        assert d["mode"] == "mock"


class TestVerificationResult:
    """测试 VerificationResult 模型."""

    def test_default_creation(self):
        v = VerificationResult()
        assert v.verified is False
        assert v.data_available is False
        assert v.confidence == 0.0

    def test_verified_result(self):
        v = VerificationResult(
            execution_result_id="res_1",
            verified=True,
            data_available=True,
            confidence=0.95,
            reason="all_checks_passed",
            metrics={"spend": 100, "impressions": 5000},
        )
        assert v.verified is True
        assert v.confidence == 0.95
        assert v.metrics["spend"] == 100

    def test_to_dict(self):
        v = VerificationResult(
            execution_result_id="res_1",
            verified=True,
            confidence=1.0,
            metrics={"spend": 50},
        )
        d = v.to_dict()
        assert d["verified"] is True
        assert d["confidence"] == 1.0
        assert d["metrics"]["spend"] == 50


class TestAdapterMetrics:
    """测试 AdapterMetrics 模型."""

    def test_default_creation(self):
        m = AdapterMetrics()
        assert m.total_requests == 0
        assert m.success_rate == 1.0

    def test_record_success(self):
        m = AdapterMetrics(adapter_name="test")
        result = RealExecutionResult(
            success=True,
            mode=ExecutionMode.REAL,
        )
        result.api_response = APIResponse(status_code=200, latency_ms=50.0)
        m.record(result)
        assert m.total_requests == 1
        assert m.success_count == 1
        assert m.real_count == 1

    def test_record_failure(self):
        m = AdapterMetrics(adapter_name="test")
        result = RealExecutionResult(
            success=False,
            error_message="API error",
        )
        m.record(result)
        assert m.total_requests == 1
        assert m.failure_count == 1
        assert m.success_rate == 0.0

    def test_record_mock(self):
        m = AdapterMetrics(adapter_name="test")
        result = RealExecutionResult(
            success=True,
            mode=ExecutionMode.MOCK,
        )
        m.record(result)
        assert m.mock_count == 1

    def test_record_rate_limit(self):
        m = AdapterMetrics(adapter_name="test")
        result = RealExecutionResult(
            success=True,
            mode=ExecutionMode.REAL,
        )
        result.api_response = APIResponse(status_code=429)
        m.record(result)
        assert m.rate_limit_hits == 1

    def test_to_dict(self):
        m = AdapterMetrics(adapter_name="test", platform=PlatformType.META)
        d = m.to_dict()
        assert d["adapter_name"] == "test"
        assert d["platform"] == "meta"
        assert d["success_rate"] == 1.0

    def test_avg_latency(self):
        m = AdapterMetrics(adapter_name="test")
        r1 = RealExecutionResult(success=True)
        r1.api_response = APIResponse(latency_ms=100.0)
        r2 = RealExecutionResult(success=True)
        r2.api_response = APIResponse(latency_ms=200.0)
        m.record(r1)
        m.record(r2)
        assert m.avg_latency_ms == 150.0


# ═══════════════════════════════════════════════════════════════
# 2. Meta Executor
# ═══════════════════════════════════════════════════════════════


class TestMetaAPIClient:
    """测试 MetaAPIClient."""

    def test_create_mock_client(self):
        client = MetaAPIClient(use_mock=True)
        assert client.request_count == 0

    def test_create_campaign(self):
        client = MetaAPIClient(ad_account_id="act_123")
        resp = client.create_campaign(name="Test Campaign")
        assert resp.success is True
        assert resp.status_code == 200
        assert resp.platform_id.startswith("meta_")
        assert client.request_count == 1

    def test_create_campaign_with_budget(self):
        client = MetaAPIClient(ad_account_id="act_123")
        resp = client.create_campaign(
            name="Budget Campaign",
            daily_budget=100.0,
            lifetime_budget=1000.0,
        )
        assert resp.success is True

    def test_update_campaign(self):
        client = MetaAPIClient()
        resp = client.update_campaign(
            campaign_id="camp_123",
            name="Updated",
            status="ACTIVE",
        )
        assert resp.success is True

    def test_pause_campaign(self):
        client = MetaAPIClient()
        resp = client.pause_campaign("camp_123")
        assert resp.success is True

    def test_create_ad_set(self):
        client = MetaAPIClient(ad_account_id="act_123")
        resp = client.create_ad_set(
            campaign_id="camp_123",
            name="Test AdSet",
            daily_budget=50.0,
        )
        assert resp.success is True

    def test_update_budget(self):
        client = MetaAPIClient()
        resp = client.update_budget("camp_123", daily_budget=200.0)
        assert resp.success is True

    def test_upload_creative(self):
        client = MetaAPIClient(ad_account_id="act_123")
        resp = client.upload_creative(
            ad_account_id="act_123",
            name="Test Creative",
            video_url="https://example.com/video.mp4",
        )
        assert resp.success is True

    def test_pause_creative(self):
        client = MetaAPIClient()
        resp = client.pause_creative("creative_123")
        assert resp.success is True

    def test_request_count_increments(self):
        client = MetaAPIClient()
        client.create_campaign(name="C1")
        client.create_campaign(name="C2")
        assert client.request_count == 2


class TestMetaExecutor:
    """测试 MetaExecutor."""

    def test_create_executor(self):
        executor = MetaExecutor()
        assert executor.name == "MetaExecutor"
        assert executor.mode == ExecutionMode.MOCK

    def test_mode_setter(self):
        executor = MetaExecutor()
        executor.mode = ExecutionMode.REAL
        assert executor.mode == ExecutionMode.REAL

    def test_execute_create_campaign(self):
        executor = MetaExecutor(mode=ExecutionMode.MOCK)
        action = make_action(
            ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
            name="AI Campaign",
            objective="APP_INSTALLS",
            daily_budget=100.0,
        )
        result = executor.execute(action, make_guard_context())
        assert result.is_success is True
        assert "meta_api" in result.reason
        assert result.metadata["platform"] == "meta"

    def test_execute_create_ad_set(self):
        executor = MetaExecutor(mode=ExecutionMode.MOCK)
        action = make_action(
            ExecutionActionType.CREATE_AD_SET,
            domain=ExecutionDomain.CAMPAIGN,
            campaign_id="camp_123",
            name="Test AdSet",
            daily_budget=50.0,
        )
        result = executor.execute(action, make_guard_context())
        assert result.is_success is True

    def test_execute_update_budget(self):
        executor = MetaExecutor(mode=ExecutionMode.MOCK)
        action = make_action(
            ExecutionActionType.UPDATE_BUDGET,
            domain=ExecutionDomain.BUDGET,
            daily_budget=150.0,
        )
        action.target_entity = "camp_456"
        result = executor.execute(action, make_guard_context())
        assert result.is_success is True

    def test_execute_scale_budget(self):
        executor = MetaExecutor(mode=ExecutionMode.MOCK)
        action = make_action(
            ExecutionActionType.SCALE_BUDGET,
            domain=ExecutionDomain.BUDGET,
            daily_budget=200.0,
        )
        action.target_entity = "camp_789"
        result = executor.execute(action, make_guard_context())
        assert result.is_success is True

    def test_execute_reduce_budget(self):
        executor = MetaExecutor(mode=ExecutionMode.MOCK)
        action = make_action(
            ExecutionActionType.REDUCE_BUDGET,
            domain=ExecutionDomain.BUDGET,
            daily_budget=50.0,
        )
        action.target_entity = "camp_789"
        result = executor.execute(action, make_guard_context())
        assert result.is_success is True

    def test_execute_pause_campaign(self):
        executor = MetaExecutor(mode=ExecutionMode.MOCK)
        action = make_action(
            ExecutionActionType.PAUSE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
        )
        action.target_entity = "camp_123"
        result = executor.execute(action, make_guard_context())
        assert result.is_success is True

    def test_execute_freeze_campaign(self):
        executor = MetaExecutor(mode=ExecutionMode.MOCK)
        action = make_action(
            ExecutionActionType.FREEZE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
        )
        action.target_entity = "camp_123"
        result = executor.execute(action, make_guard_context())
        assert result.is_success is True

    def test_execute_upload_creative(self):
        executor = MetaExecutor(mode=ExecutionMode.MOCK)
        action = make_action(
            ExecutionActionType.UPLOAD_CREATIVE,
            domain=ExecutionDomain.CREATIVE,
            name="Test Creative",
            video_url="https://example.com/video.mp4",
        )
        result = executor.execute(action, make_guard_context())
        assert result.is_success is True

    def test_execute_pause_creative(self):
        executor = MetaExecutor(mode=ExecutionMode.MOCK)
        action = make_action(
            ExecutionActionType.PAUSE_CREATIVE,
            domain=ExecutionDomain.CREATIVE,
        )
        action.target_entity = "creative_123"
        result = executor.execute(action, make_guard_context())
        assert result.is_success is True

    def test_unsupported_action(self):
        executor = MetaExecutor()
        action = make_action(
            ExecutionActionType.COLLECT_RESULT,
            domain=ExecutionDomain.MONITOR,
        )
        result = executor.execute(action, make_guard_context())
        assert result.status == ExecutionResultStatus.SKIPPED

    def test_dry_run_mode(self):
        executor = MetaExecutor(mode=ExecutionMode.DRY_RUN)
        action = make_action(
            ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
            name="Test",
        )
        result = executor.execute(action, make_guard_context())
        assert result.is_success is True
        assert result.metadata["mode"] == "dry_run"

    def test_approval_required(self):
        executor = MetaExecutor()
        action = make_action(
            ExecutionActionType.SCALE_BUDGET,
            domain=ExecutionDomain.BUDGET,
            daily_budget=500.0,
        )
        action.target_entity = "camp_123"
        gc = GuardContext(requires_approval=True, confidence=0.7)
        result = executor.execute(action, gc)
        assert result.status == ExecutionResultStatus.PENDING_APPROVAL

    def test_pre_validation_fails(self):
        executor = MetaExecutor()
        action = make_action(
            ExecutionActionType.UPDATE_BUDGET,
            domain=ExecutionDomain.BUDGET,
        )
        action.target_entity = "camp_123"
        # Missing required param: daily_budget
        result = executor.execute(action, make_guard_context())
        assert result.status == ExecutionResultStatus.SKIPPED

    def test_rollback_create_campaign(self):
        executor = MetaExecutor()
        action = make_action(
            ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
        )
        action.target_entity = "camp_123"
        result = executor.rollback(action)
        assert result.status == ExecutionResultStatus.ROLLED_BACK

    def test_rollback_budget_change(self):
        executor = MetaExecutor()
        action = make_action(
            ExecutionActionType.SCALE_BUDGET,
            domain=ExecutionDomain.BUDGET,
            original_budget=100.0,
            daily_budget=200.0,
        )
        action.target_entity = "camp_123"
        result = executor.rollback(action)
        assert result.status == ExecutionResultStatus.ROLLED_BACK

    def test_metrics_recording(self):
        executor = MetaExecutor(mode=ExecutionMode.MOCK)
        action = make_action(
            ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
            name="Test",
        )
        executor.execute(action, make_guard_context())
        executor.execute(action, make_guard_context())
        assert executor.metrics.total_requests == 2
        assert executor.metrics.success_count == 2

    def test_stats(self):
        executor = MetaExecutor()
        stats = executor.stats()
        assert stats["name"] == "MetaExecutor"
        assert "execution_count" in stats


# ═══════════════════════════════════════════════════════════════
# 3. Creative Executor
# ═══════════════════════════════════════════════════════════════


class TestCreativeAsset:
    """测试 CreativeAsset 模型."""

    def test_default_creation(self):
        asset = CreativeAsset()
        assert asset.asset_type == "VIDEO"
        assert asset.generation == 1

    def test_custom_creation(self):
        asset = CreativeAsset(
            name="Test Asset",
            dna_id="dna_123",
            asset_type="VIDEO",
            generation=2,
            parent_asset_id="parent_456",
        )
        assert asset.name == "Test Asset"
        assert asset.dna_id == "dna_123"
        assert asset.generation == 2
        assert asset.parent_asset_id == "parent_456"

    def test_to_dict(self):
        asset = CreativeAsset(
            asset_id="ca_123",
            name="Test",
            dna_id="dna_1",
            tags=["tag1", "tag2"],
        )
        d = asset.to_dict()
        assert d["asset_id"] == "ca_123"
        assert d["name"] == "Test"
        assert d["tags"] == ["tag1", "tag2"]


class TestCreativeGenerationClient:
    """测试 CreativeGenerationClient."""

    def test_generate_asset(self):
        client = CreativeGenerationClient(use_mock=True)
        asset = client.generate_asset(
            dna_id="dna_1",
            name="Test Video",
            asset_type="VIDEO",
            hypothesis_id="hyp_1",
        )
        assert asset.dna_id == "dna_1"
        assert asset.name == "Test Video"
        assert asset.asset_type == "VIDEO"
        assert asset.hypothesis_id == "hyp_1"
        assert asset.generation == 1
        assert client.generation_count == 1

    def test_mutate_asset(self):
        client = CreativeGenerationClient(use_mock=True)
        parent = client.generate_asset(dna_id="dna_1", name="Parent")
        child = client.mutate_asset(parent, {})
        assert child.dna_id == "dna_1"
        assert child.parent_asset_id == parent.asset_id
        assert child.generation == 2
        assert "M2" in child.name
        assert client.generation_count == 2

    def test_mock_asset_has_urls(self):
        client = CreativeGenerationClient(use_mock=True)
        asset = client.generate_asset(dna_id="dna_1", name="Test")
        assert asset.video_url != ""
        assert asset.thumbnail_url != ""


class TestCreativeExecutor:
    """测试 CreativeExecutor."""

    def test_create_executor(self):
        executor = CreativeExecutor()
        assert executor.name == "CreativeExecutor"
        assert executor.mode == ExecutionMode.MOCK

    def test_execute_create_creative(self):
        executor = CreativeExecutor(mode=ExecutionMode.MOCK)
        action = make_action(
            ExecutionActionType.CREATE_CREATIVE,
            domain=ExecutionDomain.CREATIVE,
            dna_id="dna_1",
            name="AI Creative",
            asset_type="VIDEO",
        )
        result = executor.execute(action, make_guard_context())
        assert result.is_success is True
        assert "asset_id" in result.metadata
        assert result.metadata["dna_id"] == "dna_1"
        assert result.metadata["generation"] == 1

    def test_execute_mutate_creative(self):
        executor = CreativeExecutor(mode=ExecutionMode.MOCK)
        # First create a parent
        create_action = make_action(
            ExecutionActionType.CREATE_CREATIVE,
            domain=ExecutionDomain.CREATIVE,
            dna_id="dna_1",
            name="Parent",
        )
        create_result = executor.execute(create_action, make_guard_context())
        parent_id = create_result.metadata["asset_id"]

        # Then mutate
        mutate_action = make_action(
            ExecutionActionType.MUTATE_CREATIVE,
            domain=ExecutionDomain.CREATIVE,
            parent_asset_id=parent_id,
            mutation_params={"visual_brightness": "+20%"},
        )
        mutate_result = executor.execute(mutate_action, make_guard_context())
        assert mutate_result.is_success is True
        assert mutate_result.metadata["generation"] == 2

    def test_execute_upload_creative(self):
        executor = CreativeExecutor(mode=ExecutionMode.MOCK)
        action = make_action(
            ExecutionActionType.UPLOAD_CREATIVE,
            domain=ExecutionDomain.CREATIVE,
            asset_id="ca_123",
            name="Uploaded",
            video_url="https://example.com/video.mp4",
        )
        result = executor.execute(action, make_guard_context())
        assert result.is_success is True

    def test_execute_pause_creative(self):
        executor = CreativeExecutor(mode=ExecutionMode.MOCK)
        action = make_action(
            ExecutionActionType.PAUSE_CREATIVE,
            domain=ExecutionDomain.CREATIVE,
        )
        action.target_entity = "ca_123"
        result = executor.execute(action, make_guard_context())
        assert result.is_success is True

    def test_unsupported_action(self):
        executor = CreativeExecutor()
        action = make_action(
            ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
        )
        result = executor.execute(action, make_guard_context())
        assert result.status == ExecutionResultStatus.SKIPPED

    def test_dry_run_mode(self):
        executor = CreativeExecutor(mode=ExecutionMode.DRY_RUN)
        action = make_action(
            ExecutionActionType.CREATE_CREATIVE,
            domain=ExecutionDomain.CREATIVE,
            dna_id="dna_1",
        )
        result = executor.execute(action, make_guard_context())
        assert result.metadata["mode"] == "dry_run"

    def test_asset_registry(self):
        executor = CreativeExecutor(mode=ExecutionMode.MOCK)
        action = make_action(
            ExecutionActionType.CREATE_CREATIVE,
            domain=ExecutionDomain.CREATIVE,
            dna_id="dna_1",
            name="Test",
        )
        result = executor.execute(action, make_guard_context())
        asset_id = result.metadata["asset_id"]

        asset = executor.get_asset(asset_id)
        assert asset is not None
        assert asset.name == "Test"

    def test_get_assets_by_dna(self):
        executor = CreativeExecutor(mode=ExecutionMode.MOCK)
        for i in range(3):
            action = make_action(
                ExecutionActionType.CREATE_CREATIVE,
                domain=ExecutionDomain.CREATIVE,
                dna_id="dna_shared",
                name=f"Asset_{i}",
            )
            executor.execute(action, make_guard_context())

        assets = executor.get_assets_by_dna("dna_shared")
        assert len(assets) == 3

    def test_get_assets_by_generation(self):
        executor = CreativeExecutor(mode=ExecutionMode.MOCK)
        action = make_action(
            ExecutionActionType.CREATE_CREATIVE,
            domain=ExecutionDomain.CREATIVE,
            dna_id="dna_1",
            name="G1",
        )
        executor.execute(action, make_guard_context())

        gen1 = executor.get_assets_by_generation(1)
        assert len(gen1) == 1

    def test_rollback_creative(self):
        executor = CreativeExecutor()
        action = make_action(
            ExecutionActionType.CREATE_CREATIVE,
            domain=ExecutionDomain.CREATIVE,
        )
        result = executor.rollback(action)
        assert result.status == ExecutionResultStatus.ROLLED_BACK

    def test_clear_registry(self):
        executor = CreativeExecutor()
        action = make_action(
            ExecutionActionType.CREATE_CREATIVE,
            domain=ExecutionDomain.CREATIVE,
            dna_id="dna_1",
        )
        executor.execute(action, make_guard_context())
        executor.clear_registry()
        assert len(executor.get_asset_registry()) == 0


# ═══════════════════════════════════════════════════════════════
# 4. Adjust Verifier
# ═══════════════════════════════════════════════════════════════


class TestVerificationConfig:
    """测试 VerificationConfig."""

    def test_default_config(self):
        config = VerificationConfig()
        assert config.wait_minutes == 30
        assert config.min_spend_threshold == 0.01
        assert config.min_impressions_threshold == 100
        assert config.enabled is True

    def test_custom_config(self):
        config = VerificationConfig(
            wait_minutes=60,
            min_spend_threshold=1.0,
            min_impressions_threshold=500,
            enabled=False,
        )
        assert config.wait_minutes == 60
        assert config.min_spend_threshold == 1.0
        assert config.enabled is False


class TestAdjustDataClient:
    """测试 AdjustDataClient."""

    def test_query_entity_metrics(self):
        client = AdjustDataClient(use_mock=True)
        metrics = client.query_entity_metrics("camp_123")
        assert "spend" in metrics
        assert "impressions" in metrics
        assert "installs" in metrics
        assert "revenue" in metrics
        assert "roas" in metrics
        assert metrics["data_available"] is True

    def test_query_creative_metrics(self):
        client = AdjustDataClient(use_mock=True)
        metrics = client.query_creative_metrics("creative_123")
        assert "spend" in metrics
        assert "creative_id" in metrics
        assert metrics["creative_id"] == "creative_123"


class TestAdjustVerifier:
    """测试 AdjustVerifier."""

    def test_create_verifier(self):
        verifier = AdjustVerifier()
        assert verifier.verification_count == 0
        assert verifier.verified_count == 0

    def test_verify_success(self):
        verifier = AdjustVerifier()
        result = RealExecutionResult(
            action_id="act_1",
            platform=PlatformType.META,
            platform_entity_id="camp_123",
            success=True,
        )
        verification = verifier.verify(result)
        # Mock data has sufficient metrics, so should pass
        assert verification.data_available is True
        assert verification.verified is True

    def test_verify_increments_count(self):
        verifier = AdjustVerifier()
        result = RealExecutionResult(
            platform=PlatformType.META,
            platform_entity_id="camp_123",
            success=True,
        )
        verifier.verify(result)
        assert verifier.verification_count == 1
        assert verifier.verified_count == 1

    def test_verify_disabled(self):
        config = VerificationConfig(enabled=False)
        verifier = AdjustVerifier(config=config)
        result = RealExecutionResult(
            platform=PlatformType.META,
            platform_entity_id="camp_123",
        )
        verification = verifier.verify(result)
        assert verification.verified is True
        assert verification.reason == "verification_disabled"

    def test_verify_batch(self):
        verifier = AdjustVerifier()
        results = [
            RealExecutionResult(
                platform=PlatformType.META,
                platform_entity_id=f"camp_{i}",
                success=True,
            )
            for i in range(5)
        ]
        verifications = verifier.verify_batch(results)
        assert len(verifications) == 5
        assert all(v.verified for v in verifications)

    def test_metrics_in_verification(self):
        verifier = AdjustVerifier()
        result = RealExecutionResult(
            platform=PlatformType.META,
            platform_entity_id="camp_123",
            success=True,
        )
        verification = verifier.verify(result)
        assert "spend" in verification.metrics
        assert "impressions" in verification.metrics
        assert verification.confidence > 0

    def test_verified_rate(self):
        verifier = AdjustVerifier()
        for i in range(4):
            result = RealExecutionResult(
                platform=PlatformType.META,
                platform_entity_id=f"camp_{i}",
                success=True,
            )
            verifier.verify(result)
        assert verifier.verified_rate == 1.0

    def test_stats(self):
        verifier = AdjustVerifier()
        stats = verifier.stats()
        assert stats["name"] == "AdjustVerifier"
        assert stats["verification_count"] == 0
        assert "config" in stats

    def test_reset(self):
        verifier = AdjustVerifier()
        result = RealExecutionResult(
            platform=PlatformType.META,
            platform_entity_id="camp_123",
        )
        verifier.verify(result)
        verifier.reset()
        assert verifier.verification_count == 0
        assert verifier.verified_count == 0


# ═══════════════════════════════════════════════════════════════
# 5. Execution Policy
# ═══════════════════════════════════════════════════════════════


class TestActionRiskLevel:
    """测试 ActionRiskLevel."""

    def test_risk_values(self):
        assert ActionRiskLevel.SAFE == "safe"
        assert ActionRiskLevel.LOW == "low"
        assert ActionRiskLevel.MEDIUM == "medium"
        assert ActionRiskLevel.HIGH == "high"
        assert ActionRiskLevel.CRITICAL == "critical"

    def test_risk_mapping(self):
        assert ACTION_RISK_MAP["monitor"] == ActionRiskLevel.SAFE
        assert ACTION_RISK_MAP["pause_campaign"] == ActionRiskLevel.LOW
        assert ACTION_RISK_MAP["update_budget"] == ActionRiskLevel.MEDIUM
        assert ACTION_RISK_MAP["create_campaign"] == ActionRiskLevel.HIGH
        assert ACTION_RISK_MAP["batch_create"] == ActionRiskLevel.CRITICAL


class TestExecutionPolicy:
    """测试 ExecutionPolicy."""

    def test_default_policy(self):
        policy = ExecutionPolicy()
        assert policy.mode == PolicyMode.SAFE_REAL
        assert policy.default_execution_mode == ExecutionMode.REAL

    def test_resolve_mode_full_mock(self):
        policy = create_development_policy()
        mode = policy.resolve_mode("create_campaign")
        assert mode == ExecutionMode.MOCK

    def test_resolve_mode_dry_run(self):
        policy = create_testing_policy()
        mode = policy.resolve_mode("create_campaign")
        assert mode == ExecutionMode.DRY_RUN

    def test_resolve_mode_full_real(self):
        policy = create_full_auto_policy()
        mode = policy.resolve_mode("create_campaign")
        assert mode == ExecutionMode.REAL

    def test_resolve_mode_safe_real_high_risk(self):
        policy = create_safe_real_policy()
        mode = policy.resolve_mode("create_campaign")
        assert mode == ExecutionMode.APPROVAL_REQUIRED

    def test_resolve_mode_safe_real_low_risk(self):
        policy = create_safe_real_policy()
        mode = policy.resolve_mode("pause_creative")
        assert mode == ExecutionMode.REAL

    def test_resolve_mode_conservative(self):
        policy = create_conservative_policy()
        mode = policy.resolve_mode("update_budget")
        assert mode == ExecutionMode.APPROVAL_REQUIRED

    def test_needs_approval_high_risk(self):
        policy = create_safe_real_policy()
        assert policy.needs_approval("create_campaign") is True

    def test_needs_approval_low_risk(self):
        policy = create_safe_real_policy()
        assert policy.needs_approval("pause_creative") is False

    def test_should_degrade(self):
        policy = ExecutionPolicy()
        assert policy.should_degrade(DegradeReason.API_UNAVAILABLE) is True
        assert policy.should_degrade(DegradeReason.AUTH_FAILURE) is False

    def test_disabled_policy(self):
        policy = ExecutionPolicy(enabled=False)
        mode = policy.resolve_mode("create_campaign")
        assert mode == ExecutionMode.DRY_RUN

    def test_to_dict(self):
        policy = create_safe_real_policy()
        d = policy.to_dict()
        assert d["name"] == "safe_real"
        assert d["mode"] == "safe_real"


class TestPolicyEngine:
    """测试 PolicyEngine."""

    def test_create_engine(self):
        engine = PolicyEngine()
        assert engine.policy.name == "safe_real"

    def test_evaluate_safe_action(self):
        engine = PolicyEngine(policy=create_safe_real_policy())
        decision = engine.evaluate("monitor")
        assert decision.resolved_mode == ExecutionMode.REAL
        assert decision.needs_approval is False
        assert decision.risk_level == ActionRiskLevel.SAFE

    def test_evaluate_high_risk_action(self):
        engine = PolicyEngine(policy=create_safe_real_policy())
        decision = engine.evaluate("create_campaign")
        assert decision.resolved_mode == ExecutionMode.APPROVAL_REQUIRED
        assert decision.needs_approval is True
        assert decision.risk_level == ActionRiskLevel.HIGH

    def test_evaluate_degraded_platform(self):
        engine = PolicyEngine(policy=create_safe_real_policy())
        engine.degrade_platform(PlatformType.META, DegradeReason.API_UNAVAILABLE)
        decision = engine.evaluate("create_campaign")
        assert decision.resolved_mode == ExecutionMode.MOCK
        assert decision.degraded is True
        assert decision.degrade_reason == DegradeReason.API_UNAVAILABLE

    def test_restore_platform(self):
        engine = PolicyEngine(policy=create_safe_real_policy())
        engine.degrade_platform(PlatformType.META, DegradeReason.API_UNAVAILABLE)
        engine.restore_platform(PlatformType.META)
        assert engine.is_degraded(PlatformType.META) is False

    def test_is_degraded(self):
        engine = PolicyEngine()
        assert engine.is_degraded(PlatformType.META) is False
        engine.degrade_platform(PlatformType.META, DegradeReason.TIMEOUT)
        assert engine.is_degraded(PlatformType.META) is True

    def test_get_degraded_platforms(self):
        engine = PolicyEngine()
        engine.degrade_platform(PlatformType.META, DegradeReason.API_UNAVAILABLE)
        engine.degrade_platform(PlatformType.GOOGLE_ADS, DegradeReason.TIMEOUT)
        degraded = engine.get_degraded_platforms()
        assert len(degraded) == 2

    def test_clear_degraded(self):
        engine = PolicyEngine()
        engine.degrade_platform(PlatformType.META, DegradeReason.API_UNAVAILABLE)
        engine.clear_degraded()
        assert len(engine.get_degraded_platforms()) == 0

    def test_update_policy(self):
        engine = PolicyEngine()
        engine.update_policy(create_full_auto_policy())
        assert engine.policy.name == "full_auto"
        decision = engine.evaluate("create_campaign")
        assert decision.needs_approval is False

    def test_decision_count(self):
        engine = PolicyEngine()
        for _ in range(5):
            engine.evaluate("monitor")
        assert engine.decision_count == 5

    def test_stats(self):
        engine = PolicyEngine()
        stats = engine.stats()
        assert stats["policy_name"] == "safe_real"
        assert stats["decision_count"] == 0


class TestPolicyDecision:
    """测试 PolicyDecision."""

    def test_default_decision(self):
        d = PolicyDecision()
        assert d.action_type == ""
        assert d.resolved_mode == ExecutionMode.MOCK
        assert d.degraded is False

    def test_decision_with_approval(self):
        d = PolicyDecision(
            action_type="create_campaign",
            resolved_mode=ExecutionMode.APPROVAL_REQUIRED,
            needs_approval=True,
            risk_level=ActionRiskLevel.HIGH,
            policy_name="safe_real",
        )
        assert d.needs_approval is True
        assert d.risk_level == ActionRiskLevel.HIGH


class TestPolicyFactory:
    """测试 Policy Factory 函数."""

    def test_development_policy(self):
        p = create_development_policy()
        assert p.mode == PolicyMode.FULL_MOCK
        assert p.resolve_mode("create_campaign") == ExecutionMode.MOCK

    def test_testing_policy(self):
        p = create_testing_policy()
        assert p.mode == PolicyMode.DRY_RUN_ONLY
        assert p.resolve_mode("create_campaign") == ExecutionMode.DRY_RUN

    def test_safe_real_policy(self):
        p = create_safe_real_policy()
        assert p.mode == PolicyMode.SAFE_REAL
        assert p.resolve_mode("monitor") == ExecutionMode.REAL
        assert p.resolve_mode("create_campaign") == ExecutionMode.APPROVAL_REQUIRED

    def test_full_auto_policy(self):
        p = create_full_auto_policy()
        assert p.mode == PolicyMode.FULL_REAL
        assert p.resolve_mode("create_campaign") == ExecutionMode.REAL
        assert p.resolve_mode("scale_budget") == ExecutionMode.REAL

    def test_conservative_policy(self):
        p = create_conservative_policy()
        assert p.mode == PolicyMode.CUSTOM
        assert p.resolve_mode("monitor") == ExecutionMode.REAL
        assert p.resolve_mode("update_budget") == ExecutionMode.APPROVAL_REQUIRED
        assert p.resolve_mode("scale_budget") == ExecutionMode.APPROVAL_REQUIRED


# ═══════════════════════════════════════════════════════════════
# 6. Executor Gateway
# ═══════════════════════════════════════════════════════════════


class TestGatewayResult:
    """测试 GatewayResult."""

    def test_default_creation(self):
        result = GatewayResult()
        assert result.status == GatewayResultStatus.SUCCESS
        assert result.degraded is False

    def test_success_result(self):
        result = GatewayResult(
            action_id="act_1",
            action_type="create_campaign",
            status=GatewayResultStatus.SUCCESS,
        )
        assert result.is_success is True
        assert result.is_degraded is False

    def test_degraded_result(self):
        result = GatewayResult(
            status=GatewayResultStatus.DEGRADED,
            degraded=True,
            degrade_reason="api_unavailable",
        )
        assert result.is_degraded is True
        assert result.is_success is False

    def test_approval_required(self):
        result = GatewayResult(
            status=GatewayResultStatus.APPROVAL_REQUIRED,
        )
        assert result.needs_approval is True

    def test_to_dict(self):
        result = GatewayResult(
            action_id="act_1",
            action_type="create_campaign",
            status=GatewayResultStatus.SUCCESS,
        )
        d = result.to_dict()
        assert d["action_id"] == "act_1"
        assert d["status"] == "success"


class TestExecutorGateway:
    """测试 ExecutorGateway."""

    def _create_gateway(self) -> ExecutorGateway:
        """创建测试用 Gateway (使用 full_auto 策略, 允许直接执行)."""
        from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.execution_policy import (
            PolicyEngine,
            create_full_auto_policy,
        )
        meta = MetaExecutor(mode=ExecutionMode.MOCK)
        creative = CreativeExecutor(mode=ExecutionMode.MOCK)
        verifier = AdjustVerifier()
        return ExecutorGateway(
            meta_executor=meta,
            creative_executor=creative,
            verifier=verifier,
            policy_engine=PolicyEngine(policy=create_full_auto_policy()),
        )

    def test_create_gateway(self):
        gateway = self._create_gateway()
        assert gateway.total_requests == 0

    def test_execute_meta_action(self):
        gateway = self._create_gateway()
        action = make_action(
            ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
            name="Test Campaign",
        )
        result = gateway.execute(action, make_guard_context())
        assert result.is_success is True
        assert result.real_result is not None
        assert result.execution_result is not None

    def test_execute_creative_action(self):
        gateway = self._create_gateway()
        action = make_action(
            ExecutionActionType.CREATE_CREATIVE,
            domain=ExecutionDomain.CREATIVE,
            dna_id="dna_1",
            name="Test Creative",
        )
        result = gateway.execute(action, make_guard_context())
        assert result.is_success is True

    def test_execute_approval_required(self):
        gateway = self._create_gateway()
        # Use safe_real policy which requires approval for high-risk actions
        from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.execution_policy import (
            PolicyEngine,
            create_safe_real_policy,
        )
        gateway._policy_engine = PolicyEngine(policy=create_safe_real_policy())

        action = make_action(
            ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
            name="High Risk Campaign",
        )
        result = gateway.execute(action, make_guard_context())
        assert result.status == GatewayResultStatus.APPROVAL_REQUIRED

    def test_execute_degraded_platform(self):
        gateway = self._create_gateway()
        gateway.degrade_platform(PlatformType.META, "api_unavailable")

        action = make_action(
            ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
            name="Degraded Campaign",
        )
        result = gateway.execute(action, make_guard_context())
        assert result.status == GatewayResultStatus.DEGRADED
        assert result.degraded is True

    def test_execute_batch(self):
        gateway = self._create_gateway()
        actions = [
            make_action(
                ExecutionActionType.CREATE_CAMPAIGN,
                domain=ExecutionDomain.CAMPAIGN,
                name=f"Campaign_{i}",
            )
            for i in range(3)
        ]
        results = gateway.execute_batch(actions, make_guard_context())
        assert len(results) == 3
        assert all(r.is_success for r in results)

    def test_execute_plan(self):
        gateway = self._create_gateway()
        actions = [
            make_action(
                ExecutionActionType.CREATE_CAMPAIGN,
                domain=ExecutionDomain.CAMPAIGN,
                name="Plan Campaign",
            ),
            make_action(
                ExecutionActionType.CREATE_CREATIVE,
                domain=ExecutionDomain.CREATIVE,
                dna_id="dna_1",
            ),
        ]
        results = gateway.execute_plan(actions, make_guard_context())
        assert len(results) == 2
        assert all(r.is_success for r in results)

    def test_can_execute(self):
        gateway = self._create_gateway()
        action = make_action(
            ExecutionActionType.PAUSE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
        )
        action.target_entity = "camp_123"
        assert gateway.can_execute(action) is True

    def test_needs_approval(self):
        gateway = self._create_gateway()
        from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.execution_policy import (
            PolicyEngine,
            create_safe_real_policy,
        )
        gateway._policy_engine = PolicyEngine(policy=create_safe_real_policy())

        action = make_action(
            ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
        )
        assert gateway.needs_approval(action) is True

    def test_get_risk_level(self):
        gateway = self._create_gateway()
        action = make_action(
            ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
        )
        assert gateway.get_risk_level(action) == "high"

    def test_route_not_found(self):
        # Gateway without any executor registered, use full_auto to bypass approval
        from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.execution_policy import (
            PolicyEngine,
            create_full_auto_policy,
        )
        gateway = ExecutorGateway(policy_engine=PolicyEngine(policy=create_full_auto_policy()))
        action = make_action(
            ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
        )
        result = gateway.execute(action, make_guard_context())
        assert result.status == GatewayResultStatus.ROUTE_NOT_FOUND

    def test_restore_platform(self):
        gateway = self._create_gateway()
        gateway.degrade_platform(PlatformType.META, "api_unavailable")
        gateway.restore_platform(PlatformType.META)

        action = make_action(
            ExecutionActionType.PAUSE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
        )
        action.target_entity = "camp_123"
        result = gateway.execute(action, make_guard_context())
        assert result.status == GatewayResultStatus.SUCCESS

    def test_verify_disabled(self):
        gateway = self._create_gateway()
        action = make_action(
            ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
            name="No Verify",
        )
        result = gateway.execute(action, make_guard_context(), verify=False)
        assert result.is_success is True
        assert result.verification is None

    def test_stats(self):
        gateway = self._create_gateway()
        action = make_action(
            ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
            name="Stats Test",
        )
        gateway.execute(action, make_guard_context())
        stats = gateway.stats()
        assert stats["total_requests"] == 1
        assert stats["success_count"] == 1
        assert "policy" in stats

    def test_reset(self):
        gateway = self._create_gateway()
        action = make_action(
            ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
            name="Reset Test",
        )
        gateway.execute(action, make_guard_context())
        gateway.reset()
        assert gateway.total_requests == 0


# ═══════════════════════════════════════════════════════════════
# 7. Integration Tests
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """集成测试 — 完整链路."""

    def test_full_meta_chain(self):
        """测试完整 Meta 执行链路: Action → Gateway → MetaExecutor → RealResult."""
        from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.execution_policy import (
            PolicyEngine,
            create_full_auto_policy,
        )
        gateway = ExecutorGateway(
            meta_executor=MetaExecutor(mode=ExecutionMode.MOCK),
            creative_executor=CreativeExecutor(mode=ExecutionMode.MOCK),
            verifier=AdjustVerifier(),
            policy_engine=PolicyEngine(policy=create_full_auto_policy()),
        )

        action = make_action(
            ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
            name="Integration Campaign",
            daily_budget=100.0,
            objective="APP_INSTALLS",
        )
        result = gateway.execute(action, make_guard_context())

        assert result.is_success is True
        assert result.real_result is not None
        assert result.real_result.platform == PlatformType.META
        assert result.real_result.platform_entity_id != ""
        assert result.execution_result is not None
        assert result.execution_result.is_success is True

    def test_full_creative_chain(self):
        """测试完整创意执行链路: Action → Gateway → CreativeExecutor → Asset."""
        gateway = ExecutorGateway(
            meta_executor=MetaExecutor(mode=ExecutionMode.MOCK),
            creative_executor=CreativeExecutor(mode=ExecutionMode.MOCK),
            verifier=AdjustVerifier(),
        )

        action = make_action(
            ExecutionActionType.CREATE_CREATIVE,
            domain=ExecutionDomain.CREATIVE,
            dna_id="dna_integration",
            name="Integration Creative",
            asset_type="VIDEO",
        )
        result = gateway.execute(action, make_guard_context())

        assert result.is_success is True
        assert result.execution_result is not None
        assert "asset_id" in result.execution_result.metadata

    def test_full_chain_with_verification(self):
        """测试完整链路 + Adjust 验证."""
        from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.execution_policy import (
            PolicyEngine,
            create_full_auto_policy,
        )
        verifier = AdjustVerifier()
        gateway = ExecutorGateway(
            meta_executor=MetaExecutor(mode=ExecutionMode.REAL),
            creative_executor=CreativeExecutor(mode=ExecutionMode.MOCK),
            verifier=verifier,
            policy_engine=PolicyEngine(policy=create_full_auto_policy()),
        )

        action = make_action(
            ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
            name="Verified Campaign",
        )
        result = gateway.execute(action, make_guard_context(), verify=True)

        assert result.is_success is True
        assert result.verification is not None
        assert result.verification.verified is True

    def test_policy_approval_gate(self):
        """测试策略审批门: 高风险动作被拦截."""
        from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.execution_policy import (
            PolicyEngine,
            create_safe_real_policy,
        )

        gateway = ExecutorGateway(
            meta_executor=MetaExecutor(mode=ExecutionMode.MOCK),
            creative_executor=CreativeExecutor(mode=ExecutionMode.MOCK),
            policy_engine=PolicyEngine(policy=create_safe_real_policy()),
        )

        action = make_action(
            ExecutionActionType.SCALE_BUDGET,
            domain=ExecutionDomain.BUDGET,
            daily_budget=500.0,
        )
        action.target_entity = "camp_123"
        result = gateway.execute(action, make_guard_context())

        assert result.status == GatewayResultStatus.APPROVAL_REQUIRED

    def test_degraded_chain(self):
        """测试降级链路: 平台不可用 → MOCK."""
        gateway = ExecutorGateway(
            meta_executor=MetaExecutor(mode=ExecutionMode.MOCK),
            creative_executor=CreativeExecutor(mode=ExecutionMode.MOCK),
        )
        gateway.degrade_platform(PlatformType.META, "api_unavailable")

        action = make_action(
            ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
            name="Should Degrade",
        )
        result = gateway.execute(action, make_guard_context())

        assert result.status == GatewayResultStatus.DEGRADED
        assert result.degraded is True

    def test_batch_execution_all_success(self):
        """测试批量执行全部成功."""
        from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.execution_policy import (
            PolicyEngine,
            create_full_auto_policy,
        )
        gateway = ExecutorGateway(
            meta_executor=MetaExecutor(mode=ExecutionMode.MOCK),
            creative_executor=CreativeExecutor(mode=ExecutionMode.MOCK),
            policy_engine=PolicyEngine(policy=create_full_auto_policy()),
        )

        actions = [
            make_action(
                ExecutionActionType.CREATE_CAMPAIGN,
                domain=ExecutionDomain.CAMPAIGN,
                name=f"Batch_Campaign_{i}",
            )
            for i in range(5)
        ]
        results = gateway.execute_batch(actions, make_guard_context())

        assert len(results) == 5
        assert all(r.is_success for r in results)
        assert gateway.total_requests == 5

    def test_multi_platform_routing(self):
        """测试多平台路由: Meta + Creative."""
        gateway = ExecutorGateway(
            meta_executor=MetaExecutor(mode=ExecutionMode.MOCK),
            creative_executor=CreativeExecutor(mode=ExecutionMode.MOCK),
        )

        # Meta action
        meta_action = make_action(
            ExecutionActionType.UPDATE_BUDGET,
            domain=ExecutionDomain.BUDGET,
            daily_budget=150.0,
        )
        meta_action.target_entity = "camp_123"
        meta_result = gateway.execute(meta_action, make_guard_context())
        assert meta_result.is_success is True

        # Creative action
        creative_action = make_action(
            ExecutionActionType.MUTATE_CREATIVE,
            domain=ExecutionDomain.CREATIVE,
            parent_asset_id="ca_123",
        )
        creative_result = gateway.execute(creative_action, make_guard_context())
        assert creative_result.is_success is True

    def test_gateway_result_to_dict_full(self):
        """测试完整 GatewayResult 序列化."""
        from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.execution_policy import (
            PolicyEngine,
            create_full_auto_policy,
        )
        gateway = ExecutorGateway(
            meta_executor=MetaExecutor(mode=ExecutionMode.MOCK),
            verifier=AdjustVerifier(),
            policy_engine=PolicyEngine(policy=create_full_auto_policy()),
        )

        action = make_action(
            ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
            name="Serializable",
        )
        result = gateway.execute(action, make_guard_context())

        d = result.to_dict()
        assert d["status"] == "success"
        assert d["action_id"] == action.action_id
        assert d["real_result"] is not None
        assert d["execution_result"] is not None

    def test_policy_engine_integration(self):
        """测试 PolicyEngine 与 Gateway 集成."""
        from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.execution_policy import (
            PolicyEngine,
            create_full_auto_policy,
        )

        gateway = ExecutorGateway(
            meta_executor=MetaExecutor(mode=ExecutionMode.MOCK),
            policy_engine=PolicyEngine(policy=create_full_auto_policy()),
        )

        # 全自动策略下，高风险动作也不需要审批
        action = make_action(
            ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
            name="Auto Campaign",
        )
        result = gateway.execute(action, make_guard_context())
        assert result.is_success is True

    def test_gateway_success_rate(self):
        """测试网关成功率统计."""
        from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.execution_policy import (
            PolicyEngine,
            create_full_auto_policy,
        )
        gateway = ExecutorGateway(
            meta_executor=MetaExecutor(mode=ExecutionMode.MOCK),
            policy_engine=PolicyEngine(policy=create_full_auto_policy()),
        )

        for i in range(10):
            action = make_action(
                ExecutionActionType.CREATE_CAMPAIGN,
                domain=ExecutionDomain.CAMPAIGN,
                name=f"Rate_{i}",
            )
            gateway.execute(action, make_guard_context())

        assert gateway.total_requests == 10
        assert gateway.success_rate == 1.0

    def test_approval_count_tracking(self):
        """测试审批计数."""
        from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.execution_policy import (
            PolicyEngine,
            create_safe_real_policy,
        )

        gateway = ExecutorGateway(
            meta_executor=MetaExecutor(mode=ExecutionMode.MOCK),
            policy_engine=PolicyEngine(policy=create_safe_real_policy()),
        )

        for _ in range(3):
            action = make_action(
                ExecutionActionType.CREATE_CAMPAIGN,
                domain=ExecutionDomain.CAMPAIGN,
            )
            gateway.execute(action, make_guard_context())

        assert gateway.stats()["approval_count"] == 3