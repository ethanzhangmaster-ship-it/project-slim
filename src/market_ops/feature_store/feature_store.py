"""E11.1 — Feature Store。

Entity → Feature 转换层。

职责：
  - 从 CreativeStorage 加载 CreativeEntity
  - 提取 Acquisition / Monetization / Quality 三层特征
  - 保存为 CreativeFeatureSnapshot JSON
  - 供 V5 Evolution Engine 直接读取

不做：
  - 不存原始数据（由 CreativeStorage 管理）
  - 不做分析计算（由 Analyzer 处理）
  - 不做 CSV 导出（由 sync_pipeline 处理）

目录结构：
  data/feature_store/
    creative_features/
      {creative_id}.json
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

from market_ops.facebook_ingestion.storage import CreativeStorage
from market_ops.creative_repository.models.creative_entity import CreativeEntity
from .schemas import (
    CreativeFeatureSnapshot,
    AcquisitionFeature,
    MonetizationFeature,
    QualityFeature,
)

logger = logging.getLogger(__name__)


class FeatureStore:
    """特征存储层。

    从 CreativeEntity 提取特征快照，供下游消费。
    """

    def __init__(self, root_path: str = "data/feature_store") -> None:
        """
        Args:
            root_path: 特征存储根目录
        """
        self._root = root_path
        self._creative_dir = os.path.join(root_path, "creative_features")

    # ── Public API ─────────────────────────────────────────

    def update_from_storage(self, storage: CreativeStorage) -> int:
        """从 CreativeStorage 全量更新特征。

        遍历所有 CreativeEntity，提取特征并保存。

        Returns:
            更新的特征数量
        """
        os.makedirs(self._creative_dir, exist_ok=True)

        creative_entities = storage.list_all_creative_entities()
        count = 0

        for ce in creative_entities:
            try:
                snapshot = self._extract_features(ce)
                self._save_snapshot(snapshot)
                count += 1
            except Exception as e:
                logger.warning("Feature extraction failed for %s: %s", ce.creative_id, e)

        logger.info("FeatureStore updated: %d snapshots", count)
        return count

    def get(self, creative_id: str) -> CreativeFeatureSnapshot | None:
        """获取单个 Creative 的特征快照."""
        filepath = self._snapshot_path(creative_id)
        if not os.path.exists(filepath):
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return CreativeFeatureSnapshot.from_dict(data)

    def get_all(self) -> list[CreativeFeatureSnapshot]:
        """获取所有特征快照."""
        snapshots = []
        if not os.path.exists(self._creative_dir):
            return snapshots

        for filename in os.listdir(self._creative_dir):
            if filename.endswith(".json"):
                creative_id = filename.replace(".json", "")
                snapshot = self.get(creative_id)
                if snapshot:
                    snapshots.append(snapshot)

        return snapshots

    def get_by_platform(self, platform: str) -> list[CreativeFeatureSnapshot]:
        """按平台筛选."""
        return [s for s in self.get_all() if s.platform == platform]

    def get_winners(self) -> list[CreativeFeatureSnapshot]:
        """获取 Winner 创意."""
        return [s for s in self.get_all() if s.quality.is_winner]

    def get_by_winner_tier(self, tier: str) -> list[CreativeFeatureSnapshot]:
        """按 Winner 层级筛选."""
        return [s for s in self.get_all() if s.quality.winner_tier == tier]

    def export_to_csv(self, output_path: str) -> str:
        """导出特征快照为 CSV.

        兼容旧 sync_pipeline 的输出格式，保证 Phase 4.1/4.2 不回归。

        Returns:
            输出文件路径
        """
        import csv

        snapshots = self.get_all()
        if not snapshots:
            logger.warning("No snapshots to export")
            return output_path

        fieldnames = [
            "creative_id", "ad_id", "platform", "status",
            "ctr", "cpi", "cpm", "spend", "impressions", "clicks", "installs",
            "d1_roas", "d7_roas", "d30_roas",
            "d1_revenue", "d7_revenue", "d30_revenue",
            "payer_rate", "d30_ltv",
            "adjust_cost", "adjust_roas_d1", "adjust_roas_d7", "adjust_roas_d30",
            "iap_fitness", "winner_tier", "recommendation",
        ]

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for s in snapshots:
                writer.writerow({
                    "creative_id": s.creative_id,
                    "ad_id": s.ad_id,
                    "platform": s.platform,
                    "status": s.status,
                    "ctr": s.acquisition.ctr,
                    "cpi": s.acquisition.cpi,
                    "cpm": s.acquisition.cpm,
                    "spend": s.acquisition.spend,
                    "impressions": s.acquisition.impression_count,
                    "clicks": s.acquisition.click_count,
                    "installs": s.acquisition.install_count,
                    "d1_roas": s.monetization.d1_roas,
                    "d7_roas": s.monetization.d7_roas,
                    "d30_roas": s.monetization.d30_roas,
                    "d1_revenue": s.monetization.d1_revenue,
                    "d7_revenue": s.monetization.d7_revenue,
                    "d30_revenue": s.monetization.d30_revenue,
                    "payer_rate": s.monetization.payer_rate,
                    "d30_ltv": s.monetization.d30_ltv,
                    "adjust_cost": s.monetization.adjust_cost,
                    "adjust_roas_d1": s.monetization.adjust_roas_d1,
                    "adjust_roas_d7": s.monetization.adjust_roas_d7,
                    "adjust_roas_d30": s.monetization.adjust_roas_d30,
                    "iap_fitness": s.quality.iap_fitness,
                    "winner_tier": s.quality.winner_tier,
                    "recommendation": s.quality.recommendation,
                })

        logger.info("Exported %d snapshots to %s", len(snapshots), output_path)
        return output_path

    def count(self) -> int:
        """特征快照数量."""
        if not os.path.exists(self._creative_dir):
            return 0
        return len([f for f in os.listdir(self._creative_dir) if f.endswith(".json")])

    # ── Internal ───────────────────────────────────────────

    def _extract_features(self, ce: CreativeEntity) -> CreativeFeatureSnapshot:
        """从 CreativeEntity 提取特征.

        Source of Truth:
          - Acquisition: Facebook (ce.performance.acquisition)
          - Monetization: Adjust (ce.performance.revenue)
          - Quality: 从 CreativeIntelligence 补充（暂时按默认值）
        """
        perf = ce.performance
        acq = perf.acquisition
        rev = perf.revenue

        return CreativeFeatureSnapshot(
            creative_id=ce.creative_id,
            ad_id=ce.identity.get("facebook_ad_id", ""),
            platform=ce.identity.get("platform", "android"),
            status=ce.identity.get("status", "ACTIVE"),
            updated_at=datetime.now().isoformat(),

            acquisition=AcquisitionFeature(
                ctr=acq.ctr,
                cpi=acq.cpi,
                cpm=acq.cpm,
                cpc=getattr(acq, "cpc", 0.0),
                impression_count=acq.impressions,
                click_count=acq.clicks,
                install_count=acq.installs,
                spend=acq.spend,
                frequency=getattr(acq, "frequency", 0.0),
                video_play_rate=getattr(acq, "video_play_rate", 0.0),
            ),

            monetization=MonetizationFeature(
                d1_roas=perf.roas_d1,
                d7_roas=perf.roas_d7,
                d30_roas=perf.roas_d30,
                d1_revenue=rev.iap_d1 + rev.ad_d1,
                d7_revenue=rev.iap_d7 + rev.ad_d7,
                d30_revenue=rev.iap_d30 + rev.ad_d30,
                d1_iap_revenue=rev.iap_d1,
                d7_iap_revenue=rev.iap_d7,
                d30_iap_revenue=rev.iap_d30,
                d1_ad_revenue=rev.ad_d1,
                d7_ad_revenue=rev.ad_d7,
                d30_ad_revenue=rev.ad_d30,
                payer_count=rev.payer_count,
                payer_rate=rev.payer_rate,
                d30_ltv=perf.ltv_d30,
                adjust_cost=rev.adjust_cost,
                adjust_roas_d1=rev.adjust_roas_d1,
                adjust_roas_d7=rev.adjust_roas_d7,
                adjust_roas_d30=rev.adjust_roas_d30,
            ),

            quality=QualityFeature(),
        )

    def _save_snapshot(self, snapshot: CreativeFeatureSnapshot) -> None:
        filepath = self._snapshot_path(snapshot.creative_id)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(snapshot.to_dict(), f, indent=2, ensure_ascii=False)

    def _snapshot_path(self, creative_id: str) -> str:
        return os.path.join(self._creative_dir, f"{creative_id}.json")

    # ── Properties ─────────────────────────────────────────

    @property
    def root_path(self) -> str:
        return self._root

    def __repr__(self) -> str:
        return f"FeatureStore(root={self._root!r}, count={self.count()})"