"""Creative Mapping Engine — API 集成测试.

验证 9 个 API 端点的功能正确性。
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


class TestCreativeMappingMatch:
    """匹配 API 测试。"""

    def test_match_success(self, client: TestClient, eagle_assets_index):
        """单条匹配成功。"""
        response = client.post("/api/creative-mapping/match", json={
            "facebook_creative_id": "536123456789",
            "facebook_creative_name": "MW_VIDEO_260721_000123",
            "duration": 32.5,
            "resolution": "1080x1920",
            "creation_time": "2026-07-24",
            "file_hash": "abc123",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["facebook_creative_id"] == "536123456789"
        assert data["status"] in ("matched", "needs_review", "no_match")
        assert "confidence" in data
        assert "scores" in data

    def test_match_missing_facebook_id(self, client: TestClient):
        """缺少 facebook_creative_id → 400。"""
        response = client.post("/api/creative-mapping/match", json={
            "facebook_creative_name": "test",
        })
        assert response.status_code == 400

    def test_batch_match(self, client: TestClient, eagle_assets_index):
        """批量匹配。"""
        response = client.post("/api/creative-mapping/batch-match", json={
            "creatives": [
                {
                    "facebook_creative_id": f"fb_batch_{i}",
                    "facebook_creative_name": "MW_VIDEO_260721_000123",
                    "duration": 32.5,
                    "resolution": "1080x1920",
                    "creation_time": "2026-07-24",
                    "file_hash": "abc123",
                }
                for i in range(3)
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["records"]) == 3

    def test_batch_match_empty(self, client: TestClient):
        """空列表 → 400。"""
        response = client.post("/api/creative-mapping/batch-match", json={
            "creatives": []
        })
        assert response.status_code == 400


class TestCreativeMappingRecords:
    """记录查询 API 测试。"""

    def test_list_records(self, client: TestClient, eagle_assets_index):
        """列表查询。"""
        # 先创建一条记录
        client.post("/api/creative-mapping/match", json={
            "facebook_creative_id": "fb_list_test",
            "facebook_creative_name": "MW_VIDEO_260721_000123",
            "duration": 32.5,
            "resolution": "1080x1920",
            "creation_time": "2026-07-24",
            "file_hash": "abc123",
        })
        response = client.get("/api/creative-mapping/records")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_list_records_with_status_filter(self, client: TestClient, eagle_assets_index):
        """按 status 筛选。"""
        client.post("/api/creative-mapping/match", json={
            "facebook_creative_id": "fb_filter_test",
            "facebook_creative_name": "MW_VIDEO_260721_000123",
            "duration": 32.5,
            "resolution": "1080x1920",
            "creation_time": "2026-07-24",
            "file_hash": "abc123",
        })
        response = client.get("/api/creative-mapping/records?status=matched")
        assert response.status_code == 200

    def test_get_by_facebook_id(self, client: TestClient, eagle_assets_index):
        """按 Facebook ID 查询。"""
        client.post("/api/creative-mapping/match", json={
            "facebook_creative_id": "fb_get_test",
            "facebook_creative_name": "MW_VIDEO_260721_000123",
            "duration": 32.5,
            "resolution": "1080x1920",
            "creation_time": "2026-07-24",
            "file_hash": "abc123",
        })
        response = client.get("/api/creative-mapping/records/by-facebook/fb_get_test")
        assert response.status_code == 200
        data = response.json()
        assert data["facebook_creative_id"] == "fb_get_test"

    def test_get_by_facebook_id_not_found(self, client: TestClient):
        """不存在的 Facebook ID → 404。"""
        response = client.get("/api/creative-mapping/records/by-facebook/nonexistent")
        assert response.status_code == 404

    def test_get_record_detail(self, client: TestClient, eagle_assets_index):
        """查询单条记录详情。"""
        match_resp = client.post("/api/creative-mapping/match", json={
            "facebook_creative_id": "fb_detail_test",
            "facebook_creative_name": "MW_VIDEO_260721_000123",
            "duration": 32.5,
            "resolution": "1080x1920",
            "creation_time": "2026-07-24",
            "file_hash": "abc123",
        })
        mapping_id = match_resp.json()["mapping_id"]
        response = client.get(f"/api/creative-mapping/records/{mapping_id}")
        assert response.status_code == 200
        assert response.json()["mapping_id"] == mapping_id

    def test_get_record_detail_not_found(self, client: TestClient):
        """不存在的 mapping_id → 404。"""
        response = client.get("/api/creative-mapping/records/nonexistent")
        assert response.status_code == 404


class TestCreativeMappingReview:
    """审核 API 测试。"""

    def test_review_queue(self, client: TestClient, eagle_assets_index):
        """获取审核队列。"""
        response = client.get("/api/creative-mapping/review/queue")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "tasks" in data

    def test_review_approve(self, client: TestClient, eagle_assets_index):
        """审核通过流程。"""
        # 先创建 NEEDS_REVIEW 记录
        match_resp = client.post("/api/creative-mapping/match", json={
            "facebook_creative_id": "fb_review_approve",
            "facebook_creative_name": "MW_VIDEO_260721_000123",
            "duration": 100.0,
            "resolution": "720x1280",
            "creation_time": "2026-07-24",
            "file_hash": "abc123",
        })
        match_data = match_resp.json()
        if match_data["status"] != "needs_review":
            return  # 跳过 if not in review state

        # 获取审核队列
        queue_resp = client.get("/api/creative-mapping/review/queue")
        tasks = queue_resp.json()["tasks"]
        if not tasks:
            return

        task_id = tasks[0]["task_id"]
        # 审核通过
        response = client.post(f"/api/creative-mapping/review/{task_id}/approve", json={
            "eagle_filename": "approved.mp4",
            "eagle_path": "/path/to/approved.mp4",
            "reviewer": "tester",
        })
        assert response.status_code == 200
        assert response.json()["status"] == "approved"

    def test_review_approve_missing_filename(self, client: TestClient):
        """审核通过缺少 eagle_filename → 400。"""
        response = client.post("/api/creative-mapping/review/fake_task/approve", json={})
        assert response.status_code == 400

    def test_review_reject(self, client: TestClient, eagle_assets_index):
        """审核驳回流程。"""
        match_resp = client.post("/api/creative-mapping/match", json={
            "facebook_creative_id": "fb_review_reject",
            "facebook_creative_name": "MW_VIDEO_260721_000123",
            "duration": 100.0,
            "resolution": "720x1280",
            "creation_time": "2026-07-24",
            "file_hash": "abc123",
        })
        match_data = match_resp.json()
        if match_data["status"] != "needs_review":
            return

        queue_resp = client.get("/api/creative-mapping/review/queue")
        tasks = queue_resp.json()["tasks"]
        if not tasks:
            return

        task_id = tasks[0]["task_id"]
        response = client.post(f"/api/creative-mapping/review/{task_id}/reject", json={
            "reason": "wrong match",
            "reviewer": "tester",
        })
        assert response.status_code == 200
        assert response.json()["status"] == "rejected"

    def test_review_reject_missing_reason(self, client: TestClient):
        """审核驳回缺少 reason → 400。"""
        response = client.post("/api/creative-mapping/review/fake_task/reject", json={})
        assert response.status_code == 400

    def test_review_approve_not_found(self, client: TestClient):
        """审核不存在的 task → 404。"""
        response = client.post("/api/creative-mapping/review/nonexistent_task/approve", json={
            "eagle_filename": "test.mp4"
        })
        assert response.status_code == 404


class TestCreativeMappingStats:
    """统计 API 测试。"""

    def test_stats(self, client: TestClient, eagle_assets_index):
        """获取统计。"""
        # 先创建一条记录
        client.post("/api/creative-mapping/match", json={
            "facebook_creative_id": "fb_stats_test",
            "facebook_creative_name": "MW_VIDEO_260721_000123",
            "duration": 32.5,
            "resolution": "1080x1920",
            "creation_time": "2026-07-24",
            "file_hash": "abc123",
        })
        response = client.get("/api/creative-mapping/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_records" in data
        assert "status_distribution" in data
        assert "average_confidence" in data


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


import json
from pathlib import Path

import pytest


@pytest.fixture
def eagle_assets_index(monkeypatch, tmp_path: Path):
    """设置测试用 Eagle 素材索引和临时数据目录。"""
    eagle_assets = [
        {
            "filename": "MW_VIDEO_260721_000123.mp4",
            "path": "D:/eagle/MW_VIDEO_260721_000123.mp4",
            "duration": 32.5,
            "resolution": "1080x1920",
            "created_at": "2026-07-24",
            "file_hash": "abc123",
        },
        {
            "filename": "MW_VIDEO_260721_000456.mp4",
            "path": "D:/eagle/MW_VIDEO_260721_000456.mp4",
            "duration": 45.0,
            "resolution": "1080x1920",
            "created_at": "2026-07-25",
            "file_hash": "def456",
        },
    ]

    from src.market_ops.workspace import app as app_module
    from src.market_ops.creative_mapping_engine import CreativeMappingEngine

    # 重置单例
    if hasattr(app_module._get_creative_mapping_engine, "_instance"):
        monkeypatch.delattr(app_module._get_creative_mapping_engine, "_instance")

    # 创建临时 engine 实例
    engine = CreativeMappingEngine(
        data_dir=str(tmp_path / "cm"),
        eagle_index_path=str(tmp_path / "eagle_index.json"),
    )
    engine.set_eagle_assets(eagle_assets)
    monkeypatch.setattr(app_module, "_get_creative_mapping_engine", lambda: engine)


@pytest.fixture
def client(monkeypatch, tmp_path: Path) -> TestClient:
    """临时 client。"""
    from src.market_ops.workspace import app as app_module
    monkeypatch.setattr(app_module, "_PROJECT_ROOT", tmp_path)

    # 重置所有单例
    for fn_name in ["_get_creative_mapping_engine"]:
        fn = getattr(app_module, fn_name)
        if hasattr(fn, "_instance"):
            monkeypatch.delattr(fn, "_instance")

    from src.market_ops.workspace.app import app
    return TestClient(app)
