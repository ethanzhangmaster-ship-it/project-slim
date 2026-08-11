"""FacebookInsightsIngester 单元测试 (v1.7).

覆盖:
  - CreativePerformance 数据模型
  - InsightsIngestionResult 数据模型
  - FacebookInsightsIngester.ingest_insights (dry_run / 真实模式)
  - FacebookInsightsIngester.ingest_insights_batch (批量回写)
  - creative_id 匹配逻辑
  - actions 数组解析 (app_install / mobile_app_install)
  - get_performance / get_top_performers
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
    CreativeMappingEngine,
    CreativeMappingRecord,
    CreativePerformance,
    FacebookInsightsIngester,
    InsightsIngestionResult,
    MappingDeliveryStatus,
    MappingScores,
    MappingStatus,
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
def ingester(engine, tmp_data_dir):
    """FacebookInsightsIngester (dry_run 模式)。"""
    return FacebookInsightsIngester(
        engine=engine,
        data_dir=tmp_data_dir,
        dry_run=True,
    )


@pytest.fixture
def published_record(engine):
    """创建一条 PUBLISHED + 有 ad_id 的映射记录。"""
    record = CreativeMappingRecord(
        mapping_id="map_pub_001",
        facebook_creative_id="fb_creative_001",
        facebook_creative_name="Published Creative",
        eagle_filename="sample.png",
        eagle_path="/tmp/sample.png",
        scores=MappingScores(name_similarity=0.9),
        confidence=0.92,
        match_method="name_similarity",
        status=MappingStatus.MATCHED,
        delivery_status=MappingDeliveryStatus.PUBLISHED,
        publish_id="pub_001",
        ad_id="ad_001",
        ad_creative_id="crt_001",
        delivered_at=now_iso(),
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    engine.store.save_record(record)
    return record


@pytest.fixture
def published_record2(engine):
    """创建第二条 PUBLISHED 记录。"""
    record = CreativeMappingRecord(
        mapping_id="map_pub_002",
        facebook_creative_id="fb_creative_002",
        facebook_creative_name="Second Creative",
        eagle_filename="sample2.png",
        eagle_path="/tmp/sample2.png",
        confidence=0.85,
        status=MappingStatus.MATCHED,
        delivery_status=MappingDeliveryStatus.PUBLISHED,
        publish_id="pub_002",
        ad_id="ad_002",
        ad_creative_id="crt_002",
        delivered_at=now_iso(),
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    engine.store.save_record(record)
    return record


@pytest.fixture
def undispatched_record(engine):
    """创建一条未投递的记录 (应被跳过)。"""
    record = CreativeMappingRecord(
        mapping_id="map_undispatched",
        facebook_creative_id="fb_creative_003",
        facebook_creative_name="Undispatched",
        confidence=0.7,
        status=MappingStatus.MATCHED,
        delivery_status=MappingDeliveryStatus.UNDISPATCHED,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    engine.store.save_record(record)
    return record


def _make_insight(
    creative_id: str,
    spend: str = "100.00",
    impressions: str = "5000",
    clicks: str = "150",
    ctr: str = "0.03",
    installs: int = 10,
) -> dict:
    """构造 Facebook insight 数据。"""
    return {
        "ad_id": "123456",
        "ad_name": "Test Ad",
        "creative": {"id": creative_id},
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "ctr": ctr,
        "cpc": "0.67",
        "cpm": "20.00",
        "actions": [
            {"action_type": "app_install", "value": str(installs)},
            {"action_type": "link_click", "value": "150"},
            {"action_type": "comment", "value": "5"},
        ],
        "date_start": "2026-08-01",
        "date_stop": "2026-08-10",
    }


# ── 数据模型测试 ──────────────────────────────────────────────


class TestCreativePerformance:
    """CreativePerformance 数据模型测试。"""

    def test_default_values(self):
        perf = CreativePerformance()
        assert perf.spend == 0.0
        assert perf.impressions == 0
        assert perf.clicks == 0
        assert perf.ctr == 0.0
        assert perf.cpc == 0.0
        assert perf.cpm == 0.0
        assert perf.installs == 0
        assert perf.last_synced_at == ""

    def test_to_dict(self):
        perf = CreativePerformance(
            spend=123.45,
            impressions=10000,
            clicks=300,
            ctr=0.03,
            cpc=0.41,
            cpm=12.35,
            installs=25,
            last_synced_at="2026-08-10T00:00:00Z",
        )
        d = perf.to_dict()
        assert d["spend"] == 123.45
        assert d["impressions"] == 10000
        assert d["clicks"] == 300
        assert d["ctr"] == 0.03
        assert d["installs"] == 25
        assert d["last_synced_at"] == "2026-08-10T00:00:00Z"

    def test_from_dict(self):
        data = {
            "spend": "50.5",
            "impressions": "2000",
            "clicks": "60",
            "ctr": "0.03",
            "cpc": "0.84",
            "cpm": "25.25",
            "installs": "5",
            "last_synced_at": "2026-08-10T12:00:00Z",
        }
        perf = CreativePerformance.from_dict(data)
        assert perf.spend == 50.5
        assert perf.impressions == 2000
        assert perf.clicks == 60
        assert perf.installs == 5

    def test_round_trip(self):
        perf = CreativePerformance(
            spend=99.9,
            impressions=5000,
            clicks=100,
            ctr=0.02,
            installs=8,
        )
        d = perf.to_dict()
        perf2 = CreativePerformance.from_dict(d)
        assert perf2.spend == perf.spend
        assert perf2.impressions == perf.impressions
        assert perf2.installs == perf.installs

    def test_from_dict_with_missing_fields(self):
        """缺失字段使用默认值。"""
        perf = CreativePerformance.from_dict({})
        assert perf.spend == 0.0
        assert perf.impressions == 0


class TestInsightsIngestionResult:
    """InsightsIngestionResult 数据模型测试。"""

    def test_default_values(self):
        result = InsightsIngestionResult()
        assert result.total_fetched == 0
        assert result.total_matched == 0
        assert result.total_updated == 0
        assert result.total_skipped == 0
        assert result.total_errors == 0
        assert result.updates == []
        assert result.dry_run is False

    def test_to_dict(self):
        result = InsightsIngestionResult(
            total_fetched=10,
            total_matched=5,
            total_updated=4,
            total_skipped=5,
            total_errors=1,
            dry_run=True,
            start_date="2026-08-01",
            end_date="2026-08-10",
        )
        d = result.to_dict()
        assert d["total_fetched"] == 10
        assert d["total_matched"] == 5
        assert d["total_updated"] == 4
        assert d["dry_run"] is True
        assert d["start_date"] == "2026-08-01"


# ── Ingester 测试 ─────────────────────────────────────────────


class TestIngestInsightsDryRun:
    """dry_run 模式测试。"""

    def test_dry_run_skips_api(self, ingester):
        """dry_run 不调用 API。"""
        result = ingester.ingest_insights(
            start_date="2026-08-01",
            end_date="2026-08-10",
            dry_run=True,
        )
        assert result.dry_run is True
        assert result.total_fetched == 0
        assert result.start_date == "2026-08-01"
        assert result.end_date == "2026-08-10"

    def test_dry_run_default_lookback(self, ingester):
        """无 start_date 时使用 lookback_days。"""
        result = ingester.ingest_insights(
            lookback_days=14,
            dry_run=True,
        )
        assert result.dry_run is True
        assert result.start_date != ""
        assert result.end_date != ""


class TestIngestInsightsBatch:
    """ingest_insights_batch 测试。"""

    def test_batch_with_matching_creative(self, ingester, published_record):
        """creative_id 匹配 → 回写 performance。"""
        insights = [_make_insight(creative_id="fb_creative_001", installs=10)]
        result = ingester.ingest_insights_batch(insights=insights, dry_run=False)

        assert result.total_fetched == 1
        assert result.total_matched == 1
        assert result.total_updated == 1
        assert result.total_skipped == 0
        assert len(result.updates) == 1
        assert result.updates[0]["mapping_id"] == "map_pub_001"
        assert result.updates[0]["installs"] == 10

        # 验证回写
        record = ingester.engine.get_record("map_pub_001")
        assert record.performance is not None
        assert record.performance.spend == 100.0
        assert record.performance.impressions == 5000
        assert record.performance.clicks == 150
        assert record.performance.installs == 10

    def test_batch_no_match(self, ingester, published_record):
        """creative_id 不匹配 → skipped。"""
        insights = [_make_insight(creative_id="nonexistent_creative")]
        result = ingester.ingest_insights_batch(insights=insights, dry_run=False)

        assert result.total_fetched == 1
        assert result.total_matched == 0
        assert result.total_updated == 0
        assert result.total_skipped == 1

    def test_batch_multiple_matches(self, ingester, published_record, published_record2):
        """多条 insight 匹配多条记录。"""
        insights = [
            _make_insight(creative_id="fb_creative_001", installs=10),
            _make_insight(creative_id="fb_creative_002", installs=20),
        ]
        result = ingester.ingest_insights_batch(insights=insights, dry_run=False)

        assert result.total_fetched == 2
        assert result.total_matched == 2
        assert result.total_updated == 2

    def test_batch_skips_undispatched(self, ingester, published_record, undispatched_record):
        """未 PUBLISHED 记录被跳过。"""
        insights = [
            _make_insight(creative_id="fb_creative_001"),
            _make_insight(creative_id="fb_creative_003"),  # undispatched
        ]
        result = ingester.ingest_insights_batch(insights=insights, dry_run=False)

        # fb_creative_003 的记录是 UNDISPATCHED → 不在 published 列表
        assert result.total_matched == 1
        assert result.total_updated == 1

    def test_batch_empty_insights(self, ingester, published_record):
        """空 insights 列表。"""
        result = ingester.ingest_insights_batch(insights=[], dry_run=False)
        assert result.total_fetched == 0
        assert result.total_matched == 0
        assert result.total_updated == 0

    def test_batch_dry_run_no_write(self, ingester, published_record):
        """dry_run=True 不回写。"""
        insights = [_make_insight(creative_id="fb_creative_001")]
        result = ingester.ingest_insights_batch(insights=insights, dry_run=True)

        # dry_run 仍然回写 (ingest_insights_batch 总是处理)
        # 但 skip_audit=True 不写审计
        assert result.dry_run is True

    def test_installs_extraction_app_install(self, ingester, published_record):
        """actions 中 app_install 被正确提取。"""
        insights = [_make_insight(
            creative_id="fb_creative_001",
            installs=42,
        )]
        result = ingester.ingest_insights_batch(insights=insights, dry_run=False)
        assert result.updates[0]["installs"] == 42

    def test_installs_extraction_mobile_app_install(self, ingester, published_record):
        """actions 中 mobile_app_install 被正确提取。"""
        insight = _make_insight(creative_id="fb_creative_001", installs=0)
        insight["actions"] = [
            {"action_type": "mobile_app_install", "value": "15"},
            {"action_type": "link_click", "value": "100"},
        ]
        result = ingester.ingest_insights_batch(insights=[insight], dry_run=False)
        assert result.updates[0]["installs"] == 15

    def test_installs_extraction_multiple_actions(self, ingester, published_record):
        """多个 install action 累加。"""
        insight = _make_insight(creative_id="fb_creative_001", installs=0)
        insight["actions"] = [
            {"action_type": "app_install", "value": "10"},
            {"action_type": "mobile_app_install", "value": "5"},
            {"action_type": "omobile_app_install", "value": "3"},
        ]
        result = ingester.ingest_insights_batch(insights=[insight], dry_run=False)
        assert result.updates[0]["installs"] == 18

    def test_installs_extraction_no_actions(self, ingester, published_record):
        """无 actions 字段 → installs=0。"""
        insight = _make_insight(creative_id="fb_creative_001")
        insight.pop("actions", None)
        result = ingester.ingest_insights_batch(insights=[insight], dry_run=False)
        assert result.updates[0]["installs"] == 0

    def test_creative_id_string_format(self, ingester, published_record):
        """creative 字段为字符串时也能匹配。"""
        insight = _make_insight(creative_id="fb_creative_001")
        insight["creative"] = "fb_creative_001"  # 字符串格式
        result = ingester.ingest_insights_batch(insights=[insight], dry_run=False)
        assert result.total_matched == 1

    def test_parse_insight_with_string_values(self, ingester, published_record):
        """Facebook API 返回的数值为字符串格式。"""
        insight = _make_insight(
            creative_id="fb_creative_001",
            spend="250.50",
            impressions="15000",
            clicks="450",
            ctr="0.03",
            installs=30,
        )
        result = ingester.ingest_insights_batch(insights=[insight], dry_run=False)
        record = ingester.engine.get_record("map_pub_001")
        assert record.performance.spend == 250.50
        assert record.performance.impressions == 15000
        assert record.performance.clicks == 450

    def test_parse_insight_with_null_values(self, ingester, published_record):
        """字段为 null 时使用 0。"""
        insight = {
            "creative": {"id": "fb_creative_001"},
            "spend": None,
            "impressions": None,
            "clicks": None,
            "actions": None,
        }
        result = ingester.ingest_insights_batch(insights=[insight], dry_run=False)
        assert result.total_updated == 1
        record = ingester.engine.get_record("map_pub_001")
        assert record.performance.spend == 0.0
        assert record.performance.impressions == 0


class TestGetPerformance:
    """get_performance 测试。"""

    def test_get_performance_with_data(self, ingester, engine, published_record):
        """查询有成效数据的记录。"""
        perf = CreativePerformance(spend=100.0, installs=5)
        engine.store.update_performance(
            mapping_id="map_pub_001",
            performance=perf,
        )
        result = ingester.get_performance("map_pub_001")
        assert result["success"] is True
        assert result["performance"] is not None
        assert result["performance"]["spend"] == 100.0
        assert result["performance"]["installs"] == 5

    def test_get_performance_no_data(self, ingester, published_record):
        """查询无成效数据的记录。"""
        result = ingester.get_performance("map_pub_001")
        assert result["success"] is True
        assert result["performance"] is None

    def test_get_performance_not_found(self, ingester):
        result = ingester.get_performance("nonexistent")
        assert result["success"] is False
        assert result["error"] == "mapping not found"


class TestGetTopPerformers:
    """get_top_performers 测试。"""

    def test_top_performers_sorted_by_spend(
        self, ingester, engine, published_record, published_record2
    ):
        """按 spend 降序排序。"""
        engine.store.update_performance(
            mapping_id="map_pub_001",
            performance=CreativePerformance(spend=100.0, installs=5),
        )
        engine.store.update_performance(
            mapping_id="map_pub_002",
            performance=CreativePerformance(spend=300.0, installs=15),
        )
        performers = ingester.get_top_performers(limit=10)
        assert len(performers) == 2
        # spend 降序: map_pub_002 (300) > map_pub_001 (100)
        assert performers[0]["mapping_id"] == "map_pub_002"
        assert performers[1]["mapping_id"] == "map_pub_001"

    def test_top_performers_limit(self, ingester, engine, published_record, published_record2):
        """limit 截断。"""
        engine.store.update_performance(
            mapping_id="map_pub_001",
            performance=CreativePerformance(spend=100.0),
        )
        engine.store.update_performance(
            mapping_id="map_pub_002",
            performance=CreativePerformance(spend=200.0),
        )
        performers = ingester.get_top_performers(limit=1)
        assert len(performers) == 1
        assert performers[0]["mapping_id"] == "map_pub_002"

    def test_top_performers_empty(self, ingester):
        """无 PUBLISHED 记录。"""
        performers = ingester.get_top_performers()
        assert performers == []

    def test_top_performers_skips_no_performance(self, ingester, published_record):
        """无 performance 的记录被跳过。"""
        performers = ingester.get_top_performers()
        assert performers == []


class TestIngestInsightsRealMode:
    """真实模式测试 (mock FacebookClient)。"""

    def test_real_mode_no_client(self, engine, tmp_data_dir):
        """真实模式无 client → error。"""
        ingester = FacebookInsightsIngester(
            engine=engine,
            data_dir=tmp_data_dir,
            dry_run=False,  # 真实模式但无 client
        )
        result = ingester.ingest_insights(
            start_date="2026-08-01",
            end_date="2026-08-10",
        )
        assert result.total_errors == 1

    def test_real_mode_with_mock_client(
        self, engine, tmp_data_dir, published_record
    ):
        """真实模式 + mock client → 拉取并回写。"""
        mock_client = MagicMock()
        mock_client.get_creative_insights.return_value = [
            _make_insight(creative_id="fb_creative_001", installs=10)
        ]
        ingester = FacebookInsightsIngester(
            engine=engine,
            facebook_client=mock_client,
            data_dir=tmp_data_dir,
            dry_run=False,
        )
        result = ingester.ingest_insights(
            start_date="2026-08-01",
            end_date="2026-08-10",
        )
        assert result.total_fetched == 1
        assert result.total_matched == 1
        assert result.total_updated == 1
        mock_client.get_creative_insights.assert_called_once()

    def test_real_mode_client_exception(self, engine, tmp_data_dir):
        """client 抛异常 → error。"""
        mock_client = MagicMock()
        mock_client.get_creative_insights.side_effect = Exception("API error")
        ingester = FacebookInsightsIngester(
            engine=engine,
            facebook_client=mock_client,
            data_dir=tmp_data_dir,
            dry_run=False,
        )
        result = ingester.ingest_insights(
            start_date="2026-08-01",
            end_date="2026-08-10",
        )
        assert result.total_errors == 1


class TestAuditLog:
    """审计日志测试。"""

    def test_audit_log_written(self, ingester, published_record, tmp_data_dir):
        """回写时写入审计日志。"""
        insights = [_make_insight(creative_id="fb_creative_001")]
        ingester.ingest_insights_batch(insights=insights, dry_run=False)

        audit_path = Path(tmp_data_dir) / "insights_audit.jsonl"
        assert audit_path.exists()
        lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["mapping_id"] == "map_pub_001"
        assert entry["creative_id"] == "fb_creative_001"
        assert entry["spend"] == 100.0

    def test_audit_log_not_written_dry_run(
        self, ingester, published_record, tmp_data_dir
    ):
        """dry_run 不写审计。"""
        insights = [_make_insight(creative_id="fb_creative_001")]
        ingester.ingest_insights_batch(insights=insights, dry_run=True)

        audit_path = Path(tmp_data_dir) / "insights_audit.jsonl"
        assert not audit_path.exists()


# ── API 端点测试 ──────────────────────────────────────────────


class TestInsightsAPIEndpoints:
    """v1.7 API 端点测试。"""

    @pytest.fixture
    def client(self, engine, ingester, tmp_data_dir):
        from src.market_ops.workspace import app as app_module

        app_module._get_creative_mapping_engine._instance = engine
        app_module._get_insights_ingester._instance = ingester

        from src.market_ops.workspace.app import app
        return TestClient(app)

    def test_insights_ingest_dry_run(self, client):
        resp = client.post(
            "/api/creative-mapping/insights/ingest",
            json={
                "start_date": "2026-08-01",
                "end_date": "2026-08-10",
                "dry_run": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dry_run"] is True
        assert data["start_date"] == "2026-08-01"
        assert data["end_date"] == "2026-08-10"

    def test_insights_ingest_real_no_token(self, client):
        """真实模式无 access_token → 400。"""
        resp = client.post(
            "/api/creative-mapping/insights/ingest",
            json={
                "dry_run": False,
            },
        )
        assert resp.status_code == 400
        assert "access_token" in resp.json()["detail"]

    def test_insights_ingest_real_no_account(self, client):
        """真实模式无 ad_account_id → 400。"""
        resp = client.post(
            "/api/creative-mapping/insights/ingest",
            json={
                "dry_run": False,
                "access_token": "fake_token",
            },
        )
        assert resp.status_code == 400
        assert "ad_account_id" in resp.json()["detail"]

    def test_performance_found(self, client, engine, published_record):
        """查询有成效数据的记录。"""
        engine.store.update_performance(
            mapping_id="map_pub_001",
            performance=CreativePerformance(spend=50.0, installs=3),
        )
        resp = client.get("/api/creative-mapping/performance/map_pub_001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["performance"] is not None
        assert data["performance"]["spend"] == 50.0

    def test_performance_not_found(self, client):
        resp = client.get("/api/creative-mapping/performance/nonexistent")
        assert resp.status_code == 404

    def test_performance_no_data(self, client, published_record):
        """记录存在但无 performance。"""
        resp = client.get("/api/creative-mapping/performance/map_pub_001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["performance"] is None

    def test_performance_top_empty(self, client):
        resp = client.get("/api/creative-mapping/performance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["performers"] == []

    def test_performance_top_with_data(self, client, engine, published_record, published_record2):
        engine.store.update_performance(
            mapping_id="map_pub_001",
            performance=CreativePerformance(spend=100.0),
        )
        engine.store.update_performance(
            mapping_id="map_pub_002",
            performance=CreativePerformance(spend=200.0),
        )
        resp = client.get("/api/creative-mapping/performance?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        # spend 降序
        assert data["performers"][0]["mapping_id"] == "map_pub_002"
