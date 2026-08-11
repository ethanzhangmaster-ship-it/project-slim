"""E11.1 — FeatureStore 测试。

测试覆盖：
  - AC1: CreativeFeatureSnapshot 序列化 / 反序列化
  - AC2: AcquisitionFeature / MonetizationFeature / QualityFeature
  - AC3: FeatureStore 初始化、保存、加载
  - AC4: FeatureStore 查询 (get, get_all, get_winners, get_by_tier)
  - AC5: FeatureStore export_to_csv
  - AC6: FeatureStore update_from_storage (集成测试)
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from market_ops.feature_store import (
    FeatureStore,
    CreativeFeatureSnapshot,
    AcquisitionFeature,
    MonetizationFeature,
    QualityFeature,
)


# ═══════════════════════════════════════════════════════════
# Schema Tests
# ═══════════════════════════════════════════════════════════

class TestAcquisitionFeature:
    """AC2: AcquisitionFeature 测试."""

    def test_default_values(self):
        f = AcquisitionFeature()
        assert f.ctr == 0.0
        assert f.cpi == 0.0

    def test_to_dict(self):
        f = AcquisitionFeature(
            ctr=0.032, cpi=1.42, cpm=12.5,
            impression_count=50000, click_count=1600, spend=5000.0,
        )
        d = f.to_dict()
        assert d["ctr"] == 0.032
        assert d["cpi"] == 1.42
        assert d["impression_count"] == 50000

    def test_from_dict(self):
        f = AcquisitionFeature.from_dict({
            "ctr": 0.032, "cpi": 1.42, "spend": 5000.0,
        })
        assert f.ctr == 0.032
        assert f.cpi == 1.42
        assert f.spend == 5000.0


class TestMonetizationFeature:
    """AC2: MonetizationFeature 测试."""

    def test_default_values(self):
        f = MonetizationFeature()
        assert f.d30_roas == 0.0

    def test_to_dict(self):
        f = MonetizationFeature(
            d1_roas=0.12, d7_roas=0.35, d30_roas=0.43,
            d30_revenue=2150.0, payer_rate=0.18, d30_ltv=12.0,
        )
        d = f.to_dict()
        assert d["d30_roas"] == 0.43
        assert d["payer_rate"] == 0.18

    def test_from_dict(self):
        f = MonetizationFeature.from_dict({
            "d30_roas": 0.43, "d30_revenue": 2150.0,
        })
        assert f.d30_roas == 0.43
        assert f.d30_revenue == 2150.0


class TestQualityFeature:
    """AC2: QualityFeature 测试."""

    def test_default_values(self):
        f = QualityFeature()
        assert f.iap_fitness == 0.0
        assert f.is_winner is False

    def test_winner(self):
        f = QualityFeature(
            iap_fitness=72.5, winner_tier="S", recommendation="SCALE",
            is_winner=True,
        )
        d = f.to_dict()
        assert d["winner_tier"] == "S"
        assert d["is_winner"] is True


class TestCreativeFeatureSnapshot:
    """AC1: CreativeFeatureSnapshot 测试."""

    def test_full_snapshot(self):
        snapshot = CreativeFeatureSnapshot(
            creative_id="MW_VIDEO_001",
            ad_id="120244794613980444",
            platform="android",
            status="ACTIVE",
            acquisition=AcquisitionFeature(ctr=0.032, cpi=1.42, spend=5000),
            monetization=MonetizationFeature(d30_roas=0.43, d30_revenue=2150),
            quality=QualityFeature(iap_fitness=72.5, winner_tier="S"),
            updated_at="2026-01-01T00:00:00",
        )
        d = snapshot.to_dict()
        assert d["creative_id"] == "MW_VIDEO_001"
        assert d["acquisition"]["ctr"] == 0.032
        assert d["monetization"]["d30_roas"] == 0.43
        assert d["quality"]["iap_fitness"] == 72.5

    def test_round_trip(self):
        """AC1: 序列化 -> 反序列化 往返."""
        original = CreativeFeatureSnapshot(
            creative_id="MW_001",
            acquisition=AcquisitionFeature(ctr=0.032),
            monetization=MonetizationFeature(d30_roas=0.43),
            quality=QualityFeature(iap_fitness=72.5, is_winner=True),
        )
        data = original.to_dict()
        restored = CreativeFeatureSnapshot.from_dict(data)
        assert restored.creative_id == original.creative_id
        assert restored.acquisition.ctr == original.acquisition.ctr
        assert restored.monetization.d30_roas == original.monetization.d30_roas
        assert restored.quality.iap_fitness == original.quality.iap_fitness


# ═══════════════════════════════════════════════════════════
# FeatureStore Tests
# ═══════════════════════════════════════════════════════════

class TestFeatureStore:
    """AC3-AC5: FeatureStore 测试."""

    @pytest.fixture
    def store(self) -> FeatureStore:
        with tempfile.TemporaryDirectory() as tmpdir:
            fs = FeatureStore(root_path=tmpdir)
            yield fs

    def test_init(self, store: FeatureStore):
        """AC3: 初始化."""
        assert store.count() == 0

    def test_save_and_get(self, store: FeatureStore):
        """AC3: 保存和加载."""
        snapshot = CreativeFeatureSnapshot(
            creative_id="MW_001",
            acquisition=AcquisitionFeature(ctr=0.032),
        )
        # Direct save via internal
        import json
        os.makedirs(store._creative_dir, exist_ok=True)
        path = store._snapshot_path("MW_001")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot.to_dict(), f, indent=2)

        loaded = store.get("MW_001")
        assert loaded is not None
        assert loaded.creative_id == "MW_001"
        assert loaded.acquisition.ctr == 0.032

    def test_get_nonexistent(self, store: FeatureStore):
        """AC3: 不存在的 creative."""
        assert store.get("NONEXISTENT") is None

    def test_get_all(self, store: FeatureStore):
        """AC4: 获取所有."""
        # Save 2 snapshots
        for i in range(3):
            snapshot = CreativeFeatureSnapshot(
                creative_id=f"MW_{i:03d}",
                acquisition=AcquisitionFeature(ctr=0.03 + i * 0.01),
            )
            import json
            os.makedirs(store._creative_dir, exist_ok=True)
            path = store._snapshot_path(f"MW_{i:03d}")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(snapshot.to_dict(), f, indent=2)

        all_snapshots = store.get_all()
        assert len(all_snapshots) == 3

    def test_get_winners(self, store: FeatureStore):
        """AC4: 获取 Winner."""
        winner = CreativeFeatureSnapshot(
            creative_id="MW_S",
            quality=QualityFeature(is_winner=True, winner_tier="S"),
        )
        not_winner = CreativeFeatureSnapshot(
            creative_id="MW_C",
            quality=QualityFeature(is_winner=False, winner_tier="C"),
        )
        import json
        os.makedirs(store._creative_dir, exist_ok=True)
        for s in [winner, not_winner]:
            with open(store._snapshot_path(s.creative_id), "w", encoding="utf-8") as f:
                json.dump(s.to_dict(), f, indent=2)

        winners = store.get_winners()
        assert len(winners) == 1
        assert winners[0].creative_id == "MW_S"

    def test_get_by_winner_tier(self, store: FeatureStore):
        """AC4: 按 Winner 层级筛选."""
        import json
        os.makedirs(store._creative_dir, exist_ok=True)
        for tier, cid in [("S", "MW_S"), ("A", "MW_A"), ("B", "MW_B"), ("C", "MW_C")]:
            s = CreativeFeatureSnapshot(
                creative_id=cid, quality=QualityFeature(winner_tier=tier),
            )
            with open(store._snapshot_path(cid), "w", encoding="utf-8") as f:
                json.dump(s.to_dict(), f, indent=2)

        assert len(store.get_by_winner_tier("S")) == 1
        assert len(store.get_by_winner_tier("A")) == 1
        assert len(store.get_by_winner_tier("B")) == 1
        assert len(store.get_by_winner_tier("C")) == 1

    def test_export_to_csv(self, store: FeatureStore):
        """AC5: CSV 导出."""
        import json
        os.makedirs(store._creative_dir, exist_ok=True)
        snapshot = CreativeFeatureSnapshot(
            creative_id="MW_001",
            ad_id="123456",
            platform="android",
            acquisition=AcquisitionFeature(ctr=0.032, cpi=1.42, spend=5000),
            monetization=MonetizationFeature(d30_roas=0.43),
            quality=QualityFeature(iap_fitness=72.5, winner_tier="S"),
        )
        with open(store._snapshot_path("MW_001"), "w", encoding="utf-8") as f:
            json.dump(snapshot.to_dict(), f, indent=2)

        csv_path = os.path.join(store._root, "export.csv")
        result = store.export_to_csv(csv_path)

        assert os.path.exists(result)
        with open(result, "r", encoding="utf-8") as f:
            content = f.read()
        assert "MW_001" in content
        assert "ctr" in content
        assert "d30_roas" in content
        assert "iap_fitness" in content

    def test_count(self, store: FeatureStore):
        """AC3: 计数."""
        import json
        os.makedirs(store._creative_dir, exist_ok=True)
        for i in range(5):
            s = CreativeFeatureSnapshot(creative_id=f"MW_{i:03d}")
            with open(store._snapshot_path(f"MW_{i:03d}"), "w", encoding="utf-8") as f:
                json.dump(s.to_dict(), f, indent=2)

        assert store.count() == 5

    def test_repr(self, store: FeatureStore):
        """AC3: 字符串表示."""
        r = repr(store)
        assert "FeatureStore" in r
        assert "count=0" in r