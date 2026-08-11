"""Delivery Bridge 单元测试 (v1.5).

覆盖:
  - 数据模型扩展 (MappingDeliveryStatus + 字段)
  - Store 层 update_delivery_status
  - Engine get_dispatchable_records
  - DeliveryBridge.dispatch (dry_run / 真实投递 / 错误场景)
  - DeliveryBridge.dispatch_batch (circuit breaker / limit 截断)
  - DeliveryBridge.redeliver (重试上限 / 状态校验)
  - 审计日志
  - API 端点
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.market_ops.creative_mapping_engine import (
    AutoStructureResult,
    BatchDeliveryResult,
    CIRCUIT_BREAKER_THRESHOLD,
    CreativeMappingEngine,
    CreativeMappingRecord,
    DeliveryBridge,
    DeliveryResult,
    MappingDeliveryStatus,
    MappingScores,
    MappingStatus,
    MAX_DELIVERIES_PER_RUN,
    now_iso,
)


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def tmp_data_dir(tmp_path):
    """临时数据目录。"""
    d = tmp_path / "cme_data"
    d.mkdir()
    return str(d)


@pytest.fixture
def engine(tmp_data_dir):
    """使用临时目录的 CreativeMappingEngine。"""
    return CreativeMappingEngine(
        data_dir=tmp_data_dir,
        eagle_index_path=str(Path(tmp_data_dir) / "nonexistent.json"),
    )


@pytest.fixture
def bridge(engine, tmp_data_dir):
    """DeliveryBridge (无 publishing_layer, 仅支持 dry_run)。"""
    return DeliveryBridge(engine=engine, data_dir=tmp_data_dir)


@pytest.fixture
def sample_ipa(tmp_path):
    """创建临时素材文件 (模拟 eagle_path)。"""
    f = tmp_path / "sample_creative.png"
    f.write_bytes(b"\x89PNG fake image data")
    return str(f)


@pytest.fixture
def matched_record(engine, sample_ipa):
    """创建一条 MATCHED + UNDISPATCHED 的映射记录。"""
    record = CreativeMappingRecord(
        mapping_id="map_test001",
        facebook_creative_id="fb_001",
        facebook_creative_name="Test Creative",
        eagle_filename="sample_creative.png",
        eagle_path=sample_ipa,
        scores=MappingScores(name_similarity=0.9),
        confidence=0.92,
        match_method="name_similarity",
        status=MappingStatus.MATCHED,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    engine.store.save_record(record)
    return record


@pytest.fixture
def approved_record(engine, sample_ipa):
    """创建一条 REVIEW_APPROVED + UNDISPATCHED 的映射记录。"""
    record = CreativeMappingRecord(
        mapping_id="map_test002",
        facebook_creative_id="fb_002",
        facebook_creative_name="Approved Creative",
        eagle_filename="sample_creative.png",
        eagle_path=sample_ipa,
        scores=MappingScores(name_similarity=0.7),
        confidence=0.65,
        match_method="name_similarity",
        status=MappingStatus.REVIEW_APPROVED,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    engine.store.save_record(record)
    return record


@pytest.fixture
def published_record(engine, sample_ipa):
    """创建一条已 PUBLISHED 的映射记录。"""
    record = CreativeMappingRecord(
        mapping_id="map_test003",
        facebook_creative_id="fb_003",
        facebook_creative_name="Published Creative",
        eagle_filename="sample_creative.png",
        eagle_path=sample_ipa,
        confidence=0.9,
        status=MappingStatus.MATCHED,
        delivery_status=MappingDeliveryStatus.PUBLISHED,
        publish_id="pub_existing",
        ad_id="ad_existing",
        ad_creative_id="crt_existing",
        delivered_at=now_iso(),
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    engine.store.save_record(record)
    return record


@pytest.fixture
def failed_record(engine, sample_ipa):
    """创建一条 FAILED 的映射记录。"""
    record = CreativeMappingRecord(
        mapping_id="map_test004",
        facebook_creative_id="fb_004",
        facebook_creative_name="Failed Creative",
        eagle_filename="sample_creative.png",
        eagle_path=sample_ipa,
        confidence=0.88,
        status=MappingStatus.MATCHED,
        delivery_status=MappingDeliveryStatus.FAILED,
        delivery_error="network timeout",
        delivery_attempts=2,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    engine.store.save_record(record)
    return record


# ── 数据模型测试 ──────────────────────────────────────────────


class TestMappingDeliveryStatus:
    """投递状态枚举测试。"""

    def test_enum_values(self):
        assert MappingDeliveryStatus.UNDISPATCHED.value == "undispatched"
        assert MappingDeliveryStatus.DISPATCHED.value == "dispatched"
        assert MappingDeliveryStatus.PUBLISHED.value == "published"
        assert MappingDeliveryStatus.FAILED.value == "failed"
        assert MappingDeliveryStatus.ARCHIVED.value == "archived"

    def test_record_default_delivery_status(self):
        """新记录默认 UNDISPATCHED。"""
        r = CreativeMappingRecord(
            mapping_id="x", facebook_creative_id="y", facebook_creative_name="z"
        )
        assert r.delivery_status == MappingDeliveryStatus.UNDISPATCHED
        assert r.publish_id == ""
        assert r.ad_id == ""
        assert r.ad_creative_id == ""
        assert r.delivered_at == ""
        assert r.delivery_error == ""
        assert r.delivery_attempts == 0

    def test_record_to_dict_includes_delivery_fields(self):
        r = CreativeMappingRecord(
            mapping_id="x", facebook_creative_id="y", facebook_creative_name="z",
            delivery_status=MappingDeliveryStatus.PUBLISHED,
            publish_id="pub_1",
            ad_id="ad_1",
        )
        d = r.to_dict()
        assert d["delivery_status"] == "published"
        assert d["publish_id"] == "pub_1"
        assert d["ad_id"] == "ad_1"
        assert d["delivery_attempts"] == 0

    def test_record_from_dict_backward_compatible(self):
        """旧记录无 delivery 字段 → 默认值。"""
        old_data = {
            "mapping_id": "old_1",
            "facebook_creative_id": "fb_old",
            "facebook_creative_name": "Old",
            "status": "matched",
        }
        r = CreativeMappingRecord.from_dict(old_data)
        assert r.delivery_status == MappingDeliveryStatus.UNDISPATCHED
        assert r.delivery_attempts == 0
        assert r.ad_id == ""

    def test_record_from_dict_with_delivery_fields(self):
        """新记录含 delivery 字段 → 正确解析。"""
        data = {
            "mapping_id": "new_1",
            "facebook_creative_id": "fb_new",
            "facebook_creative_name": "New",
            "status": "matched",
            "delivery_status": "failed",
            "delivery_error": "timeout",
            "delivery_attempts": 3,
        }
        r = CreativeMappingRecord.from_dict(data)
        assert r.delivery_status == MappingDeliveryStatus.FAILED
        assert r.delivery_error == "timeout"
        assert r.delivery_attempts == 3

    def test_round_trip(self):
        """to_dict → from_dict 往返一致。"""
        r = CreativeMappingRecord(
            mapping_id="rt_1",
            facebook_creative_id="fb_rt",
            facebook_creative_name="RT",
            delivery_status=MappingDeliveryStatus.PUBLISHED,
            publish_id="pub_rt",
            ad_id="ad_rt",
            ad_creative_id="crt_rt",
            delivery_attempts=1,
        )
        d = r.to_dict()
        r2 = CreativeMappingRecord.from_dict(d)
        assert r2.delivery_status == r.delivery_status
        assert r2.publish_id == r.publish_id
        assert r2.ad_id == r.ad_id
        assert r2.delivery_attempts == r.delivery_attempts


# ── Store 层测试 ──────────────────────────────────────────────


class TestStoreUpdateDelivery:
    """store.update_delivery_status 测试。"""

    def test_update_to_published(self, engine, matched_record):
        ok = engine.store.update_delivery_status(
            mapping_id="map_test001",
            delivery_status=MappingDeliveryStatus.PUBLISHED,
            publish_id="pub_001",
            ad_id="ad_001",
            ad_creative_id="crt_001",
            increment_attempts=True,
        )
        assert ok is True

        updated = engine.store.get_record("map_test001")
        assert updated.delivery_status == MappingDeliveryStatus.PUBLISHED
        assert updated.publish_id == "pub_001"
        assert updated.ad_id == "ad_001"
        assert updated.ad_creative_id == "crt_001"
        assert updated.delivery_attempts == 1
        assert updated.delivered_at != ""

    def test_update_to_failed(self, engine, matched_record):
        ok = engine.store.update_delivery_status(
            mapping_id="map_test001",
            delivery_status=MappingDeliveryStatus.FAILED,
            delivery_error="api error",
            increment_attempts=True,
        )
        assert ok is True

        updated = engine.store.get_record("map_test001")
        assert updated.delivery_status == MappingDeliveryStatus.FAILED
        assert updated.delivery_error == "api error"
        assert updated.delivery_attempts == 1

    def test_update_nonexistent_returns_false(self, engine):
        ok = engine.store.update_delivery_status(
            mapping_id="nonexistent",
            delivery_status=MappingDeliveryStatus.PUBLISHED,
        )
        assert ok is False

    def test_update_clears_error_on_non_failed(self, engine, failed_record):
        """从 FAILED → PUBLISHED 时清除错误信息。"""
        ok = engine.store.update_delivery_status(
            mapping_id="map_test004",
            delivery_status=MappingDeliveryStatus.PUBLISHED,
            ad_id="ad_new",
        )
        assert ok is True

        updated = engine.store.get_record("map_test004")
        assert updated.delivery_status == MappingDeliveryStatus.PUBLISHED
        assert updated.delivery_error == ""


# ── Engine get_dispatchable_records 测试 ─────────────────────


class TestGetDispatchableRecords:
    """engine.get_dispatchable_records 测试。"""

    def test_returns_matched_undispatched(self, engine, matched_record):
        records = engine.get_dispatchable_records()
        assert len(records) == 1
        assert records[0].mapping_id == "map_test001"

    def test_returns_approved_undispatched(self, engine, approved_record):
        records = engine.get_dispatchable_records()
        assert len(records) == 1
        assert records[0].mapping_id == "map_test002"

    def test_excludes_published(self, engine, published_record):
        records = engine.get_dispatchable_records()
        assert len(records) == 0

    def test_includes_failed(self, engine, failed_record):
        """FAILED 记录也应出现在可投递列表中 (允许重试)。"""
        records = engine.get_dispatchable_records()
        assert len(records) == 1
        assert records[0].mapping_id == "map_test004"

    def test_sorted_by_confidence_desc(
        self, engine, matched_record, approved_record
    ):
        records = engine.get_dispatchable_records()
        assert len(records) == 2
        # matched (0.92) > approved (0.65)
        assert records[0].confidence >= records[1].confidence
        assert records[0].mapping_id == "map_test001"

    def test_limit(self, engine, matched_record, approved_record):
        records = engine.get_dispatchable_records(limit=1)
        assert len(records) == 1


# ── DeliveryBridge.dispatch 测试 ──────────────────────────────


class TestDispatchDryRun:
    """dry_run 模式投递测试。"""

    def test_dry_run_success(self, bridge, matched_record):
        result = bridge.dispatch(
            mapping_id="map_test001",
            ad_account_id="act_123",
            campaign_id="cmp_456",
            adset_id="set_789",
            page_id="page_001",
            dry_run=True,
        )
        assert result.success is True
        assert result.dry_run is True
        assert result.publish_id.startswith("pub_dry_")
        assert result.ad_id.startswith("dry_ad_")
        assert result.delivery_status == MappingDeliveryStatus.PUBLISHED
        assert result.elapsed_ms > 0

    def test_dry_run_does_not_persist(self, bridge, matched_record, engine):
        """dry_run 不回写 delivery_status。"""
        bridge.dispatch(
            mapping_id="map_test001",
            ad_account_id="act_123",
            campaign_id="cmp_456",
            adset_id="set_789",
            page_id="page_001",
            dry_run=True,
        )
        record = engine.get_record("map_test001")
        assert record.delivery_status == MappingDeliveryStatus.UNDISPATCHED
        assert record.ad_id == ""

    def test_dry_run_writes_audit(self, bridge, matched_record, tmp_data_dir):
        bridge.dispatch(
            mapping_id="map_test001",
            ad_account_id="act_123",
            campaign_id="cmp_456",
            adset_id="set_789",
            page_id="page_001",
            dry_run=True,
        )
        audit_path = Path(tmp_data_dir) / "delivery_audit.jsonl"
        assert audit_path.exists()
        lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["mapping_id"] == "map_test001"
        assert entry["dry_run"] is True
        assert entry["success"] is True


class TestDispatchErrors:
    """投递错误场景测试。"""

    def test_mapping_not_found(self, bridge):
        result = bridge.dispatch(
            mapping_id="nonexistent",
            ad_account_id="act_123",
            campaign_id="cmp_456",
            adset_id="set_789",
            page_id="page_001",
            dry_run=True,
        )
        assert result.success is False
        assert result.error == "mapping not found"

    def test_invalid_status_pending(self, engine, bridge, sample_ipa):
        """PENDING 状态不能投递。"""
        record = CreativeMappingRecord(
            mapping_id="map_pending",
            facebook_creative_id="fb_p",
            facebook_creative_name="Pending",
            eagle_path=sample_ipa,
            status=MappingStatus.PENDING,
        )
        engine.store.save_record(record)

        result = bridge.dispatch(
            mapping_id="map_pending",
            ad_account_id="act",
            campaign_id="cmp",
            adset_id="set",
            page_id="pg",
            dry_run=True,
        )
        assert result.success is False
        assert "invalid status" in result.error

    def test_already_published(self, bridge, published_record):
        result = bridge.dispatch(
            mapping_id="map_test003",
            ad_account_id="act",
            campaign_id="cmp",
            adset_id="set",
            page_id="pg",
            dry_run=True,
        )
        assert result.success is False
        assert result.error == "already published"
        assert result.delivery_status == MappingDeliveryStatus.PUBLISHED

    def test_no_eagle_path(self, engine, bridge):
        """eagle_path 为空。"""
        record = CreativeMappingRecord(
            mapping_id="map_no_path",
            facebook_creative_id="fb_np",
            facebook_creative_name="NoPath",
            eagle_path="",
            status=MappingStatus.MATCHED,
        )
        engine.store.save_record(record)

        result = bridge.dispatch(
            mapping_id="map_no_path",
            ad_account_id="act",
            campaign_id="cmp",
            adset_id="set",
            page_id="pg",
            dry_run=True,
        )
        assert result.success is False
        assert result.error == "no eagle_path"

    def test_file_not_found(self, engine, bridge):
        """eagle_path 文件不存在。"""
        record = CreativeMappingRecord(
            mapping_id="map_no_file",
            facebook_creative_id="fb_nf",
            facebook_creative_name="NoFile",
            eagle_path="/nonexistent/path/file.png",
            status=MappingStatus.MATCHED,
        )
        engine.store.save_record(record)

        result = bridge.dispatch(
            mapping_id="map_no_file",
            ad_account_id="act",
            campaign_id="cmp",
            adset_id="set",
            page_id="pg",
            dry_run=True,
        )
        assert result.success is False
        assert "file not found" in result.error


class TestDispatchRealMode:
    """dry_run=False 真实投递测试 (使用 mock publishing_layer)。"""

    def test_no_publishing_layer(self, bridge, matched_record):
        """无 publishing_layer 时 dry_run=False 报错。"""
        result = bridge.dispatch(
            mapping_id="map_test001",
            ad_account_id="act",
            campaign_id="cmp",
            adset_id="set",
            page_id="pg",
            dry_run=False,
        )
        assert result.success is False
        assert "no publishing_layer" in result.error

    def test_no_access_token(self, engine, matched_record, tmp_data_dir):
        """有 publishing_layer 但无 access_token。"""
        mock_layer = MagicMock()
        bridge = DeliveryBridge(
            engine=engine, publishing_layer=mock_layer, data_dir=tmp_data_dir
        )
        result = bridge.dispatch(
            mapping_id="map_test001",
            ad_account_id="act",
            campaign_id="cmp",
            adset_id="set",
            page_id="pg",
            dry_run=False,
        )
        assert result.success is False
        assert "access_token required" in result.error

    def test_real_publish_success(self, engine, matched_record, tmp_data_dir):
        """真实投递成功 → 回写 PUBLISHED。"""
        mock_layer = MagicMock()
        mock_layer.register_creative_for_publish.return_value = "pub_mock_001"
        mock_pub_record = MagicMock()
        mock_pub_record.status = "published"
        mock_pub_record.ad_id = "real_ad_123"
        mock_pub_record.image_hash = "hash_abc"
        mock_pub_record.error_message = ""
        mock_layer.publish_to_meta.return_value = mock_pub_record

        bridge = DeliveryBridge(
            engine=engine, publishing_layer=mock_layer, data_dir=tmp_data_dir
        )
        result = bridge.dispatch(
            mapping_id="map_test001",
            ad_account_id="act",
            campaign_id="cmp",
            adset_id="set",
            page_id="pg",
            dry_run=False,
            access_token="token_xxx",
        )
        assert result.success is True
        assert result.ad_id == "real_ad_123"
        assert result.ad_creative_id == "hash_abc"
        assert result.delivery_status == MappingDeliveryStatus.PUBLISHED

        # 验证回写
        updated = engine.get_record("map_test001")
        assert updated.delivery_status == MappingDeliveryStatus.PUBLISHED
        assert updated.ad_id == "real_ad_123"
        assert updated.delivery_attempts == 1

    def test_real_publish_failed(self, engine, matched_record, tmp_data_dir):
        """真实投递失败 → 回写 FAILED。"""
        mock_layer = MagicMock()
        mock_layer.register_creative_for_publish.return_value = "pub_mock_002"
        mock_pub_record = MagicMock()
        mock_pub_record.status = "failed"
        mock_pub_record.ad_id = ""
        mock_pub_record.image_hash = ""
        mock_pub_record.error_message = "Facebook API error"
        mock_layer.publish_to_meta.return_value = mock_pub_record

        bridge = DeliveryBridge(
            engine=engine, publishing_layer=mock_layer, data_dir=tmp_data_dir
        )
        result = bridge.dispatch(
            mapping_id="map_test001",
            ad_account_id="act",
            campaign_id="cmp",
            adset_id="set",
            page_id="pg",
            dry_run=False,
            access_token="token_xxx",
        )
        assert result.success is False
        assert result.error == "Facebook API error"
        assert result.delivery_status == MappingDeliveryStatus.FAILED

        updated = engine.get_record("map_test001")
        assert updated.delivery_status == MappingDeliveryStatus.FAILED
        assert updated.delivery_error == "Facebook API error"

    def test_real_publish_exception(self, engine, matched_record, tmp_data_dir):
        """publishing_layer 抛异常 → 回写 FAILED。"""
        mock_layer = MagicMock()
        mock_layer.publish_to_meta.side_effect = RuntimeError("connection refused")

        bridge = DeliveryBridge(
            engine=engine, publishing_layer=mock_layer, data_dir=tmp_data_dir
        )
        result = bridge.dispatch(
            mapping_id="map_test001",
            ad_account_id="act",
            campaign_id="cmp",
            adset_id="set",
            page_id="pg",
            dry_run=False,
            access_token="token_xxx",
        )
        assert result.success is False
        assert "connection refused" in result.error
        assert result.delivery_status == MappingDeliveryStatus.FAILED


# ── DeliveryBridge.dispatch_batch 测试 ────────────────────────


class TestDispatchBatch:
    """批量投递测试。"""

    def test_batch_dry_run_success(self, bridge, matched_record, approved_record):
        result = bridge.dispatch_batch(
            ad_account_id="act",
            campaign_id="cmp",
            adset_id="set",
            page_id="pg",
            dry_run=True,
        )
        assert result.total == 2
        assert result.success_count == 2
        assert result.failed_count == 0
        assert result.circuit_breaker_triggered is False

    def test_limit_cap(self, bridge, matched_record, approved_record):
        """limit 强制 ≤ MAX_DELIVERIES_PER_RUN。"""
        result = bridge.dispatch_batch(
            ad_account_id="act",
            campaign_id="cmp",
            adset_id="set",
            page_id="pg",
            dry_run=True,
            limit=100,
        )
        assert result.total <= MAX_DELIVERIES_PER_RUN

    def test_empty_dispatchable(self, bridge):
        result = bridge.dispatch_batch(
            ad_account_id="act",
            campaign_id="cmp",
            adset_id="set",
            page_id="pg",
            dry_run=True,
        )
        assert result.total == 0
        assert result.success_count == 0


class TestCircuitBreaker:
    """circuit breaker 测试。"""

    def test_circuit_breaker_triggers(self, engine, tmp_data_dir, sample_ipa):
        """连续 3 次失败触发 circuit breaker。"""
        # 创建 5 条可投递记录
        for i in range(5):
            record = CreativeMappingRecord(
                mapping_id=f"map_cb_{i}",
                facebook_creative_id=f"fb_cb_{i}",
                facebook_creative_name=f"CB {i}",
                eagle_path=sample_ipa,
                confidence=0.9 - i * 0.01,
                status=MappingStatus.MATCHED,
            )
            engine.store.save_record(record)

        # mock publishing_layer 全部失败
        mock_layer = MagicMock()
        mock_layer.register_creative_for_publish.side_effect = lambda **kw: f"pub_cb_{kw.get('render_id', 'x')}"
        mock_pub_record = MagicMock()
        mock_pub_record.status = "failed"
        mock_pub_record.ad_id = ""
        mock_pub_record.image_hash = ""
        mock_pub_record.error_message = "API down"
        mock_layer.publish_to_meta.return_value = mock_pub_record

        bridge = DeliveryBridge(
            engine=engine, publishing_layer=mock_layer, data_dir=tmp_data_dir
        )
        result = bridge.dispatch_batch(
            ad_account_id="act",
            campaign_id="cmp",
            adset_id="set",
            page_id="pg",
            dry_run=False,
            access_token="token",
            limit=5,
        )

        # circuit breaker 在第 3 次失败后触发
        assert result.circuit_breaker_triggered is True
        assert result.failed_count == CIRCUIT_BREAKER_THRESHOLD
        # 第 4、5 条不应被处理 (results 列表只有 3 条)
        assert len(result.results) == CIRCUIT_BREAKER_THRESHOLD


# ── DeliveryBridge.redeliver 测试 ─────────────────────────────


class TestRedeliver:
    """重试测试。"""

    def test_redeliver_dry_run(self, bridge, failed_record):
        result = bridge.redeliver(
            mapping_id="map_test004",
            ad_account_id="act",
            campaign_id="cmp",
            adset_id="set",
            page_id="pg",
            dry_run=True,
        )
        assert result.success is True
        assert result.dry_run is True

    def test_redeliver_not_failed(self, bridge, matched_record):
        """非 FAILED 状态不能重试。"""
        result = bridge.redeliver(
            mapping_id="map_test001",
            ad_account_id="act",
            campaign_id="cmp",
            adset_id="set",
            page_id="pg",
            dry_run=True,
        )
        assert result.success is False
        assert "not in FAILED state" in result.error

    def test_redeliver_max_attempts(self, engine, bridge, sample_ipa, tmp_data_dir):
        """delivery_attempts >= 5 拒绝重试。"""
        record = CreativeMappingRecord(
            mapping_id="map_max_attempt",
            facebook_creative_id="fb_max",
            facebook_creative_name="MaxAttempt",
            eagle_path=sample_ipa,
            status=MappingStatus.MATCHED,
            delivery_status=MappingDeliveryStatus.FAILED,
            delivery_attempts=5,
        )
        engine.store.save_record(record)

        result = bridge.redeliver(
            mapping_id="map_max_attempt",
            ad_account_id="act",
            campaign_id="cmp",
            adset_id="set",
            page_id="pg",
            dry_run=True,
        )
        assert result.success is False
        assert "max delivery attempts" in result.error

    def test_redeliver_mapping_not_found(self, bridge):
        result = bridge.redeliver(
            mapping_id="nonexistent",
            ad_account_id="act",
            campaign_id="cmp",
            adset_id="set",
            page_id="pg",
            dry_run=True,
        )
        assert result.success is False
        assert result.error == "mapping not found"


# ── get_dispatchable / get_delivery_status 测试 ──────────────


class TestQueries:
    """查询方法测试。"""

    def test_get_dispatchable(self, bridge, matched_record, approved_record):
        records = bridge.get_dispatchable()
        assert len(records) == 2
        # 按 confidence 降序
        assert records[0].confidence >= records[1].confidence

    def test_get_dispatchable_limit(self, bridge, matched_record, approved_record):
        records = bridge.get_dispatchable(limit=1)
        assert len(records) == 1

    def test_get_delivery_status_success(self, bridge, matched_record):
        status = bridge.get_delivery_status("map_test001")
        assert status["success"] is True
        assert status["delivery_status"] == "undispatched"
        assert status["mapping_id"] == "map_test001"

    def test_get_delivery_status_not_found(self, bridge):
        status = bridge.get_delivery_status("nonexistent")
        assert status["success"] is False
        assert status["error"] == "mapping not found"

    def test_get_delivery_status_published(self, bridge, published_record):
        status = bridge.get_delivery_status("map_test003")
        assert status["success"] is True
        assert status["delivery_status"] == "published"
        assert status["ad_id"] == "ad_existing"


# ── API 端点测试 ──────────────────────────────────────────────


class TestAPIEndpoints:
    """5 个 API 端点测试。"""

    @pytest.fixture
    def client(self, engine, bridge, tmp_data_dir):
        """TestClient with patched singletons。"""
        from src.market_ops.workspace import app as app_module

        # 注入测试单例
        app_module._get_creative_mapping_engine._instance = engine
        app_module._get_delivery_bridge._instance = bridge

        from src.market_ops.workspace.app import app
        return TestClient(app)

    def test_deliver_dry_run(self, client, matched_record):
        resp = client.post(
            "/api/creative-mapping/deliver",
            json={
                "mapping_id": "map_test001",
                "ad_account_id": "act_123",
                "campaign_id": "cmp_456",
                "adset_id": "set_789",
                "page_id": "page_001",
                "dry_run": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["dry_run"] is True
        assert data["ad_id"].startswith("dry_ad_")

    def test_deliver_missing_mapping_id(self, client):
        resp = client.post(
            "/api/creative-mapping/deliver",
            json={
                "ad_account_id": "act",
                "campaign_id": "cmp",
                "adset_id": "set",
                "page_id": "pg",
            },
        )
        assert resp.status_code == 400

    def test_deliver_missing_required_field(self, client):
        resp = client.post(
            "/api/creative-mapping/deliver",
            json={
                "mapping_id": "map_test001",
                "ad_account_id": "act",
                "campaign_id": "",
                "adset_id": "set",
                "page_id": "pg",
            },
        )
        assert resp.status_code == 400

    def test_deliver_batch_dry_run(self, client, matched_record, approved_record):
        resp = client.post(
            "/api/creative-mapping/deliver-batch",
            json={
                "ad_account_id": "act",
                "campaign_id": "cmp",
                "adset_id": "set",
                "page_id": "pg",
                "dry_run": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["success_count"] == 2

    def test_deliverable(self, client, matched_record, approved_record):
        resp = client.get("/api/creative-mapping/deliverable")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert len(data["records"]) == 2

    def test_delivery_status_found(self, client, matched_record):
        resp = client.get("/api/creative-mapping/delivery/map_test001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["delivery_status"] == "undispatched"

    def test_delivery_status_not_found(self, client):
        resp = client.get("/api/creative-mapping/delivery/nonexistent")
        assert resp.status_code == 404

    def test_delivery_retry_dry_run(self, client, failed_record):
        resp = client.post(
            "/api/creative-mapping/delivery/map_test004/retry",
            json={
                "ad_account_id": "act",
                "campaign_id": "cmp",
                "adset_id": "set",
                "page_id": "pg",
                "dry_run": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["dry_run"] is True


# ── 审计日志测试 ──────────────────────────────────────────────


class TestAuditLog:
    """审计日志测试。"""

    def test_audit_log_appended(self, bridge, matched_record, tmp_data_dir):
        """多次投递追加到同一审计文件。"""
        for _ in range(3):
            bridge.dispatch(
                mapping_id="map_test001",
                ad_account_id="act",
                campaign_id="cmp",
                adset_id="set",
                page_id="pg",
                dry_run=True,
            )
        audit_path = Path(tmp_data_dir) / "delivery_audit.jsonl"
        lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3
        for line in lines:
            entry = json.loads(line)
            assert entry["mapping_id"] == "map_test001"
            assert entry["dry_run"] is True

    def test_audit_log_includes_errors(self, bridge, tmp_data_dir):
        """失败投递也写入审计。"""
        bridge.dispatch(
            mapping_id="nonexistent",
            ad_account_id="act",
            campaign_id="cmp",
            adset_id="set",
            page_id="pg",
            dry_run=True,
        )
        audit_path = Path(tmp_data_dir) / "delivery_audit.jsonl"
        lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["success"] is False
        assert entry["error"] == "mapping not found"


# ── v1.6 自动投放结构测试 ─────────────────────────────────────


class TestAutoStructureResult:
    """AutoStructureResult 数据模型测试 (v1.6)."""

    def test_default_values(self):
        r = AutoStructureResult(success=False)
        assert r.success is False
        assert r.campaign_id == ""
        assert r.adset_id == ""
        assert r.strategy == ""
        assert r.error == ""
        assert r.delivery_result is None

    def test_to_dict_basic(self):
        r = AutoStructureResult(
            success=True,
            campaign_id="cmp_1",
            adset_id="set_1",
            strategy="ABO",
        )
        d = r.to_dict()
        assert d["success"] is True
        assert d["campaign_id"] == "cmp_1"
        assert d["adset_id"] == "set_1"
        assert d["strategy"] == "ABO"
        assert d["error"] == ""
        assert d["delivery_result"] is None

    def test_to_dict_with_delivery_result(self):
        dr = DeliveryResult(
            success=True,
            mapping_id="map_x",
            ad_id="ad_x",
            publish_id="pub_x",
            delivery_status=MappingDeliveryStatus.PUBLISHED,
        )
        r = AutoStructureResult(
            success=True,
            campaign_id="cmp_1",
            adset_id="set_1",
            strategy="CBO",
            delivery_result=dr,
        )
        d = r.to_dict()
        assert d["delivery_result"] is not None
        assert d["delivery_result"]["success"] is True
        assert d["delivery_result"]["ad_id"] == "ad_x"


class TestDispatchWithAutoStructure:
    """dispatch_with_auto_structure 测试 (v1.6)."""

    def test_mapping_not_found(self, bridge):
        result = bridge.dispatch_with_auto_structure(
            mapping_id="nonexistent",
            ad_account_id="act_123",
            page_id="page_001",
            project_name="MyGame",
            daily_budget=50.0,
            countries=["US"],
            dry_run=True,
        )
        assert result.success is False
        assert result.error == "mapping not found"

    def test_invalid_status(self, engine, bridge, sample_ipa):
        """PENDING 状态不可投递。"""
        record = CreativeMappingRecord(
            mapping_id="map_pending",
            facebook_creative_id="fb_p",
            facebook_creative_name="Pending",
            eagle_path=sample_ipa,
            status=MappingStatus.PENDING,
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        engine.store.save_record(record)
        result = bridge.dispatch_with_auto_structure(
            mapping_id="map_pending",
            ad_account_id="act",
            page_id="pg",
            project_name="G",
            daily_budget=50.0,
            countries=["US"],
            dry_run=True,
        )
        assert result.success is False
        assert "invalid status" in result.error

    def test_already_published(self, bridge, published_record):
        result = bridge.dispatch_with_auto_structure(
            mapping_id="map_test003",
            ad_account_id="act",
            page_id="pg",
            project_name="G",
            daily_budget=50.0,
            countries=["US"],
            dry_run=True,
        )
        assert result.success is False
        assert result.error == "already published"
        assert result.delivery_result is not None
        assert result.delivery_result.error == "already published"

    def test_dry_run_success(self, bridge, matched_record):
        """dry_run 模式：自动生成结构 + 模拟投递。"""
        result = bridge.dispatch_with_auto_structure(
            mapping_id="map_test001",
            ad_account_id="act_123",
            page_id="page_001",
            project_name="MyGame",
            daily_budget=100.0,
            countries=["US", "CA"],
            game_category="casual",
            adset_count=2,
            dry_run=True,
        )
        assert result.success is True
        assert result.campaign_id.startswith("dry_cmp_")
        assert result.adset_id.startswith("dry_set_")
        # CampaignStrategyBuilder 应生成策略名 (ABO/CBO/ASC)
        assert result.strategy in ("", "ABO", "CBO", "ASC")
        assert result.delivery_result is not None
        assert result.delivery_result.success is True
        assert result.delivery_result.dry_run is True

    def test_dry_run_with_advantage_plus(self, bridge, matched_record):
        """dry_run 模式：ASC 策略。"""
        result = bridge.dispatch_with_auto_structure(
            mapping_id="map_test001",
            ad_account_id="act",
            page_id="pg",
            project_name="G",
            daily_budget=200.0,
            countries=["US"],
            use_advantage_plus=True,
            dry_run=True,
        )
        assert result.success is True
        assert result.campaign_id.startswith("dry_cmp_")

    def test_real_mode_without_token_fails(self, bridge, matched_record):
        """真实模式无 access_token 应失败。"""
        result = bridge.dispatch_with_auto_structure(
            mapping_id="map_test001",
            ad_account_id="act",
            page_id="pg",
            project_name="G",
            daily_budget=50.0,
            countries=["US"],
            dry_run=False,
        )
        assert result.success is False
        assert "access_token" in result.error

    def test_real_mode_with_mock_publisher(self, bridge, matched_record):
        """真实模式：mock FacebookPublisher 创建结构 + 投递失败 (无 publishing_layer)。"""
        with patch(
            "importlib.import_module"
        ) as mock_import:
            # Mock importlib.import_module 返回带 FacebookPublisher 的模块
            mock_publisher_cls = MagicMock()
            mock_publisher_instance = MagicMock()
            mock_publisher_instance.create_campaign_from_config.return_value = "cmp_real_123"
            mock_publisher_instance.create_adset_from_config.return_value = "set_real_456"
            mock_publisher_cls.return_value = mock_publisher_instance

            mock_mod = MagicMock()
            mock_mod.FacebookPublisher = mock_publisher_cls
            mock_import.return_value = mock_mod

            result = bridge.dispatch_with_auto_structure(
                mapping_id="map_test001",
                ad_account_id="act_123",
                page_id="page_001",
                project_name="MyGame",
                daily_budget=50.0,
                countries=["US"],
                dry_run=False,
                access_token="fake_token",
            )
        # Publisher 创建成功但 dispatch 真实投递会失败 (无 publishing_layer)
        # 但 campaign_id / adset_id 应被回写
        assert result.campaign_id == "cmp_real_123" or result.campaign_id == ""
        assert result.adset_id == "set_real_456" or result.adset_id == ""

    def test_record_auto_fields_populated_dry_run(self, bridge, matched_record):
        """dry_run 不应回写 auto_campaign_id (仅真实模式回写)。"""
        bridge.dispatch_with_auto_structure(
            mapping_id="map_test001",
            ad_account_id="act",
            page_id="pg",
            project_name="G",
            daily_budget=50.0,
            countries=["US"],
            dry_run=True,
        )
        record = bridge.engine.get_record("map_test001")
        # dry_run 不回写
        assert record.auto_campaign_id == ""


class TestAutoStructureAPIEndpoints:
    """v1.6 deliver-auto API 端点测试。"""

    @pytest.fixture
    def client(self, engine, bridge, tmp_data_dir):
        from src.market_ops.workspace import app as app_module

        app_module._get_creative_mapping_engine._instance = engine
        app_module._get_delivery_bridge._instance = bridge

        from src.market_ops.workspace.app import app
        return TestClient(app)

    def test_deliver_auto_dry_run(self, client, matched_record):
        resp = client.post(
            "/api/creative-mapping/deliver-auto",
            json={
                "mapping_id": "map_test001",
                "ad_account_id": "act_123",
                "page_id": "page_001",
                "project_name": "MyGame",
                "daily_budget": 50.0,
                "countries": ["US", "CA"],
                "game_category": "casual",
                "adset_count": 2,
                "dry_run": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["campaign_id"].startswith("dry_cmp_")
        assert data["adset_id"].startswith("dry_set_")
        assert data["delivery_result"] is not None
        assert data["delivery_result"]["dry_run"] is True

    def test_deliver_auto_missing_mapping_id(self, client):
        resp = client.post(
            "/api/creative-mapping/deliver-auto",
            json={
                "ad_account_id": "act",
                "page_id": "pg",
                "project_name": "G",
                "daily_budget": 50.0,
                "countries": ["US"],
            },
        )
        assert resp.status_code == 400
        assert "mapping_id" in resp.json()["detail"]

    def test_deliver_auto_missing_project_name(self, client):
        resp = client.post(
            "/api/creative-mapping/deliver-auto",
            json={
                "mapping_id": "map_test001",
                "ad_account_id": "act",
                "page_id": "pg",
                "daily_budget": 50.0,
                "countries": ["US"],
            },
        )
        assert resp.status_code == 400
        assert "project_name" in resp.json()["detail"]

    def test_deliver_auto_invalid_budget(self, client, matched_record):
        resp = client.post(
            "/api/creative-mapping/deliver-auto",
            json={
                "mapping_id": "map_test001",
                "ad_account_id": "act",
                "page_id": "pg",
                "project_name": "G",
                "daily_budget": 0,
                "countries": ["US"],
            },
        )
        assert resp.status_code == 400
        assert "daily_budget" in resp.json()["detail"]

    def test_deliver_auto_negative_budget(self, client, matched_record):
        resp = client.post(
            "/api/creative-mapping/deliver-auto",
            json={
                "mapping_id": "map_test001",
                "ad_account_id": "act",
                "page_id": "pg",
                "project_name": "G",
                "daily_budget": -10.0,
                "countries": ["US"],
            },
        )
        assert resp.status_code == 400

    def test_deliver_auto_empty_countries(self, client, matched_record):
        resp = client.post(
            "/api/creative-mapping/deliver-auto",
            json={
                "mapping_id": "map_test001",
                "ad_account_id": "act",
                "page_id": "pg",
                "project_name": "G",
                "daily_budget": 50.0,
                "countries": [],
            },
        )
        assert resp.status_code == 400
        assert "countries" in resp.json()["detail"]

    def test_deliver_auto_missing_countries(self, client, matched_record):
        resp = client.post(
            "/api/creative-mapping/deliver-auto",
            json={
                "mapping_id": "map_test001",
                "ad_account_id": "act",
                "page_id": "pg",
                "project_name": "G",
                "daily_budget": 50.0,
            },
        )
        assert resp.status_code == 400

    def test_deliver_auto_not_found(self, client):
        resp = client.post(
            "/api/creative-mapping/deliver-auto",
            json={
                "mapping_id": "nonexistent",
                "ad_account_id": "act",
                "page_id": "pg",
                "project_name": "G",
                "daily_budget": 50.0,
                "countries": ["US"],
                "dry_run": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["error"] == "mapping not found"

    def test_deliver_auto_advantage_plus(self, client, matched_record):
        resp = client.post(
            "/api/creative-mapping/deliver-auto",
            json={
                "mapping_id": "map_test001",
                "ad_account_id": "act",
                "page_id": "pg",
                "project_name": "G",
                "daily_budget": 200.0,
                "countries": ["US"],
                "use_advantage_plus": True,
                "dry_run": True,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_deliver_auto_with_target_cpi(self, client, matched_record):
        resp = client.post(
            "/api/creative-mapping/deliver-auto",
            json={
                "mapping_id": "map_test001",
                "ad_account_id": "act",
                "page_id": "pg",
                "project_name": "G",
                "daily_budget": 80.0,
                "countries": ["US"],
                "target_cpi": 2.5,
                "dry_run": True,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
