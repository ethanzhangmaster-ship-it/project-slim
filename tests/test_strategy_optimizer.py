"""DeliveryStrategyOptimizer 单元测试 (v1.8).

覆盖:
  - ArchiveResult 数据模型
  - compute_performance_score 归一化算法
  - compute_priority 联合排序
  - evaluate_and_archive 自动归档 (CTR/CPI 阈值)
  - rank_dispatchable 优先级排名
  - get_strategy_summary
  - API 端点
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.market_ops.creative_mapping_engine import (
    ArchiveResult,
    CreativeMappingEngine,
    CreativeMappingRecord,
    CreativePerformance,
    DeliveryStrategyOptimizer,
    MappingDeliveryStatus,
    MappingScores,
    MappingStatus,
    now_iso,
)


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def tmp_data_dir(tmp_path):
    d = tmp_path / "cme_data"
    d.mkdir()
    return str(d)


@pytest.fixture
def engine(tmp_data_dir):
    return CreativeMappingEngine(
        data_dir=tmp_data_dir,
        eagle_index_path=str(Path(tmp_data_dir) / "nonexistent.json"),
    )


@pytest.fixture
def optimizer(engine, tmp_data_dir):
    return DeliveryStrategyOptimizer(
        engine=engine,
        data_dir=tmp_data_dir,
    )


def _make_published_record(
    engine,
    mapping_id="map_pub_001",
    creative_id="fb_001",
    confidence=0.85,
    perf=None,
    auto_archived=False,
):
    """创建 PUBLISHED 记录。"""
    record = CreativeMappingRecord(
        mapping_id=mapping_id,
        facebook_creative_id=creative_id,
        facebook_creative_name=f"Creative {creative_id}",
        confidence=confidence,
        status=MappingStatus.MATCHED,
        delivery_status=MappingDeliveryStatus.PUBLISHED,
        ad_id=f"ad_{mapping_id}",
        publish_id=f"pub_{mapping_id}",
        auto_archived=auto_archived,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    if perf is not None:
        record.performance = perf
    engine.store.save_record(record)
    return record


def _make_dispatchable_record(
    engine,
    mapping_id="map_disp_001",
    creative_id="fb_disp_001",
    confidence=0.8,
    perf=None,
):
    """创建可投递记录 (MATCHED + UNDISPATCHED)。"""
    record = CreativeMappingRecord(
        mapping_id=mapping_id,
        facebook_creative_id=creative_id,
        facebook_creative_name=f"Disp {creative_id}",
        confidence=confidence,
        status=MappingStatus.MATCHED,
        delivery_status=MappingDeliveryStatus.UNDISPATCHED,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    if perf is not None:
        record.performance = perf
    engine.store.save_record(record)
    return record


# ── 数据模型测试 ──────────────────────────────────────────────


class TestArchiveResult:
    """ArchiveResult 数据模型测试。"""

    def test_default_values(self):
        r = ArchiveResult()
        assert r.total_evaluated == 0
        assert r.total_archived == 0
        assert r.total_skipped == 0
        assert r.archives == []
        assert r.dry_run is True

    def test_to_dict(self):
        r = ArchiveResult(
            total_evaluated=10,
            total_archived=3,
            total_skipped=7,
            dry_run=False,
        )
        d = r.to_dict()
        assert d["total_evaluated"] == 10
        assert d["total_archived"] == 3
        assert d["total_skipped"] == 7
        assert d["dry_run"] is False


# ── compute_performance_score 测试 ────────────────────────────


class TestComputePerformanceScore:
    """compute_performance_score 测试。"""

    def test_none_performance(self, optimizer):
        assert optimizer.compute_performance_score(None) == 0.0

    def test_zero_impressions(self, optimizer):
        perf = CreativePerformance(impressions=0)
        assert optimizer.compute_performance_score(perf) == 0.0

    def test_high_ctr_high_score(self, optimizer):
        """高 CTR → 高分。"""
        perf = CreativePerformance(
            impressions=5000,
            clicks=250,
            ctr=0.05,  # 5% CTR (满分)
            installs=50,
            spend=100.0,
        )
        score = optimizer.compute_performance_score(perf)
        assert 0.5 < score <= 1.0

    def test_low_ctr_low_score(self, optimizer):
        """低 CTR → 低分。"""
        perf = CreativePerformance(
            impressions=5000,
            clicks=10,
            ctr=0.002,  # 0.2% CTR
            installs=1,
            spend=100.0,
        )
        score = optimizer.compute_performance_score(perf)
        assert score < 0.5

    def test_low_cpi_high_score(self, optimizer):
        """低 CPI → 高分。"""
        perf = CreativePerformance(
            impressions=5000,
            clicks=200,
            ctr=0.04,
            installs=50,
            spend=50.0,  # CPI = 1.0
        )
        score = optimizer.compute_performance_score(perf)
        assert score > 0.5

    def test_high_cpi_low_score(self, optimizer):
        """高 CPI → 低分。"""
        perf = CreativePerformance(
            impressions=5000,
            clicks=200,
            ctr=0.04,
            installs=1,
            spend=100.0,  # CPI = 100
        )
        score = optimizer.compute_performance_score(perf)
        assert score < 0.8

    def test_score_in_range(self, optimizer):
        """得分在 [0, 1] 范围内。"""
        perf = CreativePerformance(
            impressions=1000,
            clicks=50,
            ctr=0.05,
            installs=10,
            spend=100.0,
        )
        score = optimizer.compute_performance_score(perf)
        assert 0.0 <= score <= 1.0

    def test_no_installs_no_clicks(self, optimizer):
        """无 installs 无 clicks。"""
        perf = CreativePerformance(
            impressions=2000,
            clicks=0,
            ctr=0.0,
            installs=0,
            spend=50.0,
        )
        score = optimizer.compute_performance_score(perf)
        assert 0.0 <= score <= 1.0


# ── compute_priority 测试 ─────────────────────────────────────


class TestComputePriority:
    """compute_priority 测试。"""

    def test_no_performance(self, optimizer):
        """无 performance → priority = confidence * 0.4。"""
        record = CreativeMappingRecord(
            mapping_id="x",
            facebook_creative_id="y",
            facebook_creative_name="z",
            confidence=0.8,
        )
        priority = optimizer.compute_priority(record)
        assert priority == round(0.8 * 0.4, 4)

    def test_with_performance(self, optimizer):
        """有 performance → priority = confidence * 0.4 + perf_score * 0.6。"""
        perf = CreativePerformance(
            impressions=5000,
            clicks=250,
            ctr=0.05,
            installs=50,
            spend=100.0,
        )
        record = CreativeMappingRecord(
            mapping_id="x",
            facebook_creative_id="y",
            facebook_creative_name="z",
            confidence=0.8,
            performance=perf,
        )
        priority = optimizer.compute_priority(record)
        perf_score = optimizer.compute_performance_score(perf)
        expected = round(0.8 * 0.4 + perf_score * 0.6, 4)
        assert priority == expected

    def test_priority_in_range(self, optimizer):
        """priority 在 [0, 1] 范围内。"""
        record = CreativeMappingRecord(
            mapping_id="x",
            facebook_creative_id="y",
            facebook_creative_name="z",
            confidence=1.0,
        )
        priority = optimizer.compute_priority(record)
        assert 0.0 <= priority <= 1.0


# ── evaluate_and_archive 测试 ─────────────────────────────────


class TestEvaluateAndArchive:
    """evaluate_and_archive 测试。"""

    def test_dry_run_no_write(self, optimizer, engine):
        """dry_run=True 不回写。"""
        perf = CreativePerformance(
            impressions=2000,
            clicks=5,
            ctr=0.002,  # 低 CTR
            installs=0,
            spend=100.0,
        )
        _make_published_record(engine, perf=perf)

        result = optimizer.evaluate_and_archive(dry_run=True)
        assert result.dry_run is True
        assert result.total_evaluated == 1
        assert result.total_archived == 1
        assert result.total_skipped == 0

        # 验证未回写
        record = engine.get_record("map_pub_001")
        assert record.auto_archived is False

    def test_real_mode_writes(self, optimizer, engine):
        """dry_run=False 回写归档。"""
        perf = CreativePerformance(
            impressions=2000,
            clicks=5,
            ctr=0.002,  # CTR < 0.005
            installs=0,
            spend=100.0,
        )
        _make_published_record(engine, perf=perf)

        result = optimizer.evaluate_and_archive(dry_run=False)
        assert result.total_archived == 1

        # 验证回写
        record = engine.get_record("map_pub_001")
        assert record.auto_archived is True
        assert "CTR" in record.auto_archived_reason

    def test_low_ctr_triggers_archive(self, optimizer, engine):
        """CTR < 阈值 → 归档。"""
        perf = CreativePerformance(
            impressions=2000,
            clicks=4,
            ctr=0.002,  # < 0.005
            installs=2,
            spend=50.0,
        )
        _make_published_record(engine, perf=perf)

        result = optimizer.evaluate_and_archive(dry_run=True)
        assert result.total_archived == 1
        assert "CTR" in result.archives[0]["reason"]

    def test_high_cpi_triggers_archive(self, optimizer, engine):
        """CPI > 阈值 → 归档。"""
        perf = CreativePerformance(
            impressions=2000,
            clicks=100,
            ctr=0.05,  # 正常 CTR
            installs=1,
            spend=100.0,  # CPI = 100 > 50
        )
        _make_published_record(engine, perf=perf)

        result = optimizer.evaluate_and_archive(dry_run=True)
        assert result.total_archived == 1
        assert "CPI" in result.archives[0]["reason"]

    def test_good_performance_not_archived(self, optimizer, engine):
        """良好表现不归档。"""
        perf = CreativePerformance(
            impressions=2000,
            clicks=100,
            ctr=0.05,  # 正常 CTR
            installs=20,
            spend=40.0,  # CPI = 2 < 50
        )
        _make_published_record(engine, perf=perf)

        result = optimizer.evaluate_and_archive(dry_run=True)
        assert result.total_archived == 0
        assert result.total_skipped == 1

    def test_insufficient_data_skipped(self, optimizer, engine):
        """数据量不足 → 跳过。"""
        perf = CreativePerformance(
            impressions=500,  # < 1000
            clicks=2,
            ctr=0.001,
            installs=0,
            spend=10.0,
        )
        _make_published_record(engine, perf=perf)

        result = optimizer.evaluate_and_archive(dry_run=True)
        assert result.total_archived == 0
        assert result.total_skipped == 1

    def test_no_performance_skipped(self, optimizer, engine):
        """无 performance → 跳过。"""
        _make_published_record(engine, perf=None)

        result = optimizer.evaluate_and_archive(dry_run=True)
        assert result.total_archived == 0
        assert result.total_skipped == 1

    def test_already_archived_skipped(self, optimizer, engine):
        """已归档记录 → 跳过。"""
        perf = CreativePerformance(
            impressions=2000,
            clicks=4,
            ctr=0.002,
            installs=0,
            spend=100.0,
        )
        _make_published_record(engine, perf=perf, auto_archived=True)

        result = optimizer.evaluate_and_archive(dry_run=True)
        assert result.total_evaluated == 0
        assert result.total_archived == 0

    def test_multiple_records(self, optimizer, engine):
        """多条记录混合评估。"""
        # 记录1: 低 CTR → 归档
        _make_published_record(
            engine, mapping_id="map_001", creative_id="fb_001",
            perf=CreativePerformance(impressions=2000, clicks=4, ctr=0.002),
        )
        # 记录2: 良好 → 不归档
        _make_published_record(
            engine, mapping_id="map_002", creative_id="fb_002",
            perf=CreativePerformance(
                impressions=2000, clicks=100, ctr=0.05, installs=20, spend=40.0
            ),
        )
        # 记录3: 高 CPI → 归档
        _make_published_record(
            engine, mapping_id="map_003", creative_id="fb_003",
            perf=CreativePerformance(
                impressions=2000, clicks=100, ctr=0.05, installs=1, spend=100.0
            ),
        )

        result = optimizer.evaluate_and_archive(dry_run=True)
        assert result.total_evaluated == 3
        assert result.total_archived == 2
        assert result.total_skipped == 1

    def test_custom_thresholds(self, engine, tmp_data_dir):
        """自定义阈值。"""
        opt = DeliveryStrategyOptimizer(
            engine=engine,
            data_dir=tmp_data_dir,
            ctr_threshold=0.02,  # 更高阈值
            cpi_threshold=10.0,
            min_data_points=500,
        )
        perf = CreativePerformance(
            impressions=600,
            clicks=18,
            ctr=0.03,  # > 0.02 (不触发 CTR)
            installs=3,
            spend=40.0,  # CPI = 13.3 > 10 (触发 CPI)
        )
        _make_published_record(engine, perf=perf)

        result = opt.evaluate_and_archive(dry_run=True)
        assert result.total_archived == 1
        assert "CPI" in result.archives[0]["reason"]


# ── rank_dispatchable 测试 ────────────────────────────────────


class TestRankDispatchable:
    """rank_dispatchable 测试。"""

    def test_empty(self, optimizer):
        """无记录。"""
        ranking = optimizer.rank_dispatchable()
        assert ranking == []

    def test_single_record(self, optimizer, engine):
        """单条记录。"""
        _make_dispatchable_record(engine, confidence=0.8)
        ranking = optimizer.rank_dispatchable()
        assert len(ranking) == 1
        assert ranking[0]["mapping_id"] == "map_disp_001"
        assert ranking[0]["delivery_priority"] == round(0.8 * 0.4, 4)

    def test_sorted_by_priority(self, optimizer, engine):
        """按 priority 降序。"""
        _make_dispatchable_record(
            engine, mapping_id="map_low", creative_id="fb_low",
            confidence=0.5,
        )
        _make_dispatchable_record(
            engine, mapping_id="map_high", creative_id="fb_high",
            confidence=0.95,
        )
        ranking = optimizer.rank_dispatchable()
        assert len(ranking) == 2
        # 高 confidence 排前
        assert ranking[0]["mapping_id"] == "map_high"
        assert ranking[1]["mapping_id"] == "map_low"

    def test_excludes_archived(self, optimizer, engine):
        """排除已归档记录。"""
        record = CreativeMappingRecord(
            mapping_id="map_archived",
            facebook_creative_id="fb_arch",
            facebook_creative_name="Archived",
            confidence=0.9,
            status=MappingStatus.MATCHED,
            delivery_status=MappingDeliveryStatus.UNDISPATCHED,
            auto_archived=True,
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        engine.store.save_record(record)
        _make_dispatchable_record(engine, confidence=0.7)

        ranking = optimizer.rank_dispatchable()
        assert len(ranking) == 1
        assert ranking[0]["mapping_id"] == "map_disp_001"

    def test_excludes_published(self, optimizer, engine):
        """排除已 PUBLISHED 记录。"""
        _make_published_record(engine, confidence=0.9)
        _make_dispatchable_record(engine, confidence=0.7)

        ranking = optimizer.rank_dispatchable()
        assert len(ranking) == 1
        assert ranking[0]["mapping_id"] == "map_disp_001"

    def test_limit(self, optimizer, engine):
        """limit 截断。"""
        for i in range(5):
            _make_dispatchable_record(
                engine,
                mapping_id=f"map_{i}",
                creative_id=f"fb_{i}",
                confidence=0.5 + i * 0.1,
            )
        ranking = optimizer.rank_dispatchable(limit=3)
        assert len(ranking) == 3

    def test_with_performance(self, optimizer, engine):
        """有 performance 的记录 priority 更高。"""
        perf = CreativePerformance(
            impressions=5000,
            clicks=250,
            ctr=0.05,
            installs=50,
            spend=100.0,
        )
        _make_dispatchable_record(
            engine, mapping_id="map_perf", creative_id="fb_perf",
            confidence=0.5, perf=perf,
        )
        _make_dispatchable_record(
            engine, mapping_id="map_noperf", creative_id="fb_noperf",
            confidence=0.9, perf=None,
        )
        ranking = optimizer.rank_dispatchable()
        # map_perf: 0.5 * 0.4 + perf_score * 0.6
        # map_noperf: 0.9 * 0.4 = 0.36
        # 高 perf_score 可能使 map_perf 排前
        assert len(ranking) == 2


# ── get_strategy_summary 测试 ─────────────────────────────────


class TestGetStrategySummary:
    """get_strategy_summary 测试。"""

    def test_empty(self, optimizer):
        summary = optimizer.get_strategy_summary()
        assert summary["total_published"] == 0
        assert summary["total_archived"] == 0
        assert summary["total_with_performance"] == 0
        assert summary["ctr_threshold"] == 0.005
        assert summary["cpi_threshold"] == 50.0
        assert summary["min_data_points"] == 1000
        assert summary["confidence_weight"] == 0.4
        assert summary["performance_weight"] == 0.6

    def test_with_data(self, optimizer, engine):
        _make_published_record(
            engine, mapping_id="map_1", creative_id="fb_1",
            perf=CreativePerformance(spend=100.0),
        )
        _make_published_record(
            engine, mapping_id="map_2", creative_id="fb_2",
            perf=None,
        )
        summary = optimizer.get_strategy_summary()
        assert summary["total_published"] == 2
        assert summary["total_with_performance"] == 1
        assert summary["total_archived"] == 0


# ── API 端点测试 ──────────────────────────────────────────────


class TestStrategyAPIEndpoints:
    """v1.8 API 端点测试。"""

    @pytest.fixture
    def client(self, engine, optimizer, tmp_data_dir):
        from src.market_ops.workspace import app as app_module

        app_module._get_creative_mapping_engine._instance = engine
        app_module._get_strategy_optimizer._instance = optimizer

        from src.market_ops.workspace.app import app
        return TestClient(app)

    def test_strategy_evaluate_dry_run(self, client, engine):
        """dry_run 评估。"""
        perf = CreativePerformance(
            impressions=2000,
            clicks=4,
            ctr=0.002,
            installs=0,
            spend=100.0,
        )
        _make_published_record(engine, perf=perf)

        resp = client.post(
            "/api/creative-mapping/strategy/evaluate",
            json={"dry_run": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dry_run"] is True
        assert data["total_evaluated"] == 1
        assert data["total_archived"] == 1

    def test_strategy_evaluate_empty(self, client):
        resp = client.post(
            "/api/creative-mapping/strategy/evaluate",
            json={"dry_run": True},
        )
        assert resp.status_code == 200
        assert resp.json()["total_evaluated"] == 0

    def test_strategy_ranking_empty(self, client):
        resp = client.get("/api/creative-mapping/strategy/ranking")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["ranking"] == []

    def test_strategy_ranking_with_data(self, client, engine):
        _make_dispatchable_record(
            engine, mapping_id="map_1", creative_id="fb_1",
            confidence=0.8,
        )
        _make_dispatchable_record(
            engine, mapping_id="map_2", creative_id="fb_2",
            confidence=0.95,
        )
        resp = client.get("/api/creative-mapping/strategy/ranking?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        # 高 confidence 排前
        assert data["ranking"][0]["mapping_id"] == "map_2"

    def test_strategy_summary(self, client):
        resp = client.get("/api/creative-mapping/strategy/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_published" in data
        assert "ctr_threshold" in data
        assert "cpi_threshold" in data
        assert data["confidence_weight"] == 0.4
        assert data["performance_weight"] == 0.6

    def test_strategy_evaluate_real_mode(self, client, engine):
        """真实模式回写归档。"""
        perf = CreativePerformance(
            impressions=2000,
            clicks=4,
            ctr=0.002,
            installs=0,
            spend=100.0,
        )
        _make_published_record(engine, perf=perf)

        resp = client.post(
            "/api/creative-mapping/strategy/evaluate",
            json={"dry_run": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dry_run"] is False
        assert data["total_archived"] == 1

        # 验证回写
        record = engine.get_record("map_pub_001")
        assert record.auto_archived is True
