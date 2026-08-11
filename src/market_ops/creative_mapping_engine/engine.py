"""Creative Mapping Engine — 核心编排层。

编排 6 维度评分器、持久化层和审核队列，提供统一的创意映射入口。
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from .models import (
    CreativeMappingRecord,
    MappingDeliveryStatus,
    MappingScores,
    MappingStatus,
    now_iso,
)
from .review_queue import ReviewQueue
from .scorers import MappingScorer
from .store import MappingStore

logger = logging.getLogger(__name__)


class CreativeMappingEngine:
    """创意映射引擎 — 统一多维度匹配入口。

    Usage::

        engine = CreativeMappingEngine(
            data_dir="data/creative_mapping",
            eagle_index_path="data/eagle_scan_index.json",
        )
        record = engine.match({
            "facebook_creative_id": "536123456789",
            "facebook_creative_name": "MW_VIDEO_260721_000123",
            "duration": 32.5,
            "resolution": "1080x1920",
        })
    """

    def __init__(
        self,
        data_dir: str = "data/creative_mapping",
        eagle_index_path: str = "data/eagle_scan_index.json",
        confidence_threshold: float = 0.85,
        review_threshold: float = 0.50,
        scorer: MappingScorer | None = None,
        eagle_assets: list[dict[str, Any]] | None = None,
    ):
        self._store = MappingStore(data_dir=data_dir)
        self._review_queue = ReviewQueue(self._store)
        self._scorer = scorer or MappingScorer()
        self._confidence_threshold = confidence_threshold
        self._review_threshold = review_threshold
        self._eagle_index_path = eagle_index_path
        self._eagle_assets: list[dict[str, Any]] | None = eagle_assets

    # ── 属性 ──────────────────────────────────────────────────

    @property
    def store(self) -> MappingStore:
        return self._store

    @property
    def review_queue(self) -> ReviewQueue:
        return self._review_queue

    @property
    def scorer(self) -> MappingScorer:
        return self._scorer

    @property
    def confidence_threshold(self) -> float:
        return self._confidence_threshold

    @property
    def review_threshold(self) -> float:
        return self._review_threshold

    # ── Eagle 素材索引 ────────────────────────────────────────

    def _load_eagle_assets(self) -> list[dict[str, Any]]:
        """加载 Eagle 素材索引。"""
        if self._eagle_assets is not None:
            return self._eagle_assets
        path = Path(self._eagle_index_path)
        if not path.exists():
            logger.warning("Eagle index not found: %s", path)
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            assets = data.get("assets", data) if isinstance(data, dict) else data
            if isinstance(assets, list):
                self._eagle_assets = assets
                return assets
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load eagle index: %s", exc)
        return []

    def set_eagle_assets(self, assets: list[dict[str, Any]]) -> None:
        """直接设置 Eagle 素材列表 (跳过文件加载)。"""
        self._eagle_assets = list(assets)

    # ── 核心匹配 ──────────────────────────────────────────────

    def match(self, facebook_creative: dict[str, Any]) -> CreativeMappingRecord:
        """执行单条创意映射。"""
        fb_id = facebook_creative.get("facebook_creative_id", "")
        if not fb_id:
            raise ValueError("facebook_creative_id is required")

        # 幂等检查: 已有 MATCHED 或 REVIEW_APPROVED 记录不覆盖
        existing = self._store.get_by_facebook_id(fb_id)
        if existing and existing.status in (MappingStatus.MATCHED, MappingStatus.REVIEW_APPROVED):
            return existing

        # 生成 mapping_id
        mapping_id = self._gen_mapping_id(fb_id)

        # 加载 Eagle 素材并评分
        eagle_assets = self._load_eagle_assets()
        if not eagle_assets:
            record = self._build_no_match_record(facebook_creative, mapping_id)
            self._store.save_record(record)
            return record

        # 对每个候选评分
        candidates: list[dict[str, Any]] = []
        best_record: CreativeMappingRecord | None = None
        best_confidence: float = -1.0

        for asset in eagle_assets:
            scores = self._scorer.score_all(
                fb_name=facebook_creative.get("facebook_creative_name", ""),
                eagle_filename=asset.get("filename", ""),
                fb_duration=float(facebook_creative.get("duration", 0.0)),
                eagle_duration=float(asset.get("duration", 0.0)),
                fb_resolution=facebook_creative.get("resolution", ""),
                eagle_resolution=asset.get("resolution", ""),
                fb_creation_time=facebook_creative.get("creation_time", ""),
                eagle_creation_time=asset.get("created_at", ""),
                fb_thumbnail=facebook_creative.get("thumbnail_url", ""),
                eagle_path=asset.get("path", ""),
                fb_hash=facebook_creative.get("file_hash", ""),
                eagle_hash=asset.get("file_hash", ""),
            )
            confidence = self._scorer.weighted_total(scores)
            match_method = self._scorer.dominant_dimension(scores)

            candidate = {
                "eagle_filename": asset.get("filename", ""),
                "eagle_path": asset.get("path", ""),
                "scores": scores.to_dict(),
                "confidence": confidence,
                "match_method": match_method,
            }
            candidates.append(candidate)

            if confidence > best_confidence:
                best_confidence = confidence
                best_record = CreativeMappingRecord(
                    mapping_id=mapping_id,
                    facebook_creative_id=fb_id,
                    facebook_creative_name=facebook_creative.get("facebook_creative_name", ""),
                    facebook_account_id=facebook_creative.get("facebook_account_id", ""),
                    eagle_filename=asset.get("filename", ""),
                    eagle_path=asset.get("path", ""),
                    scores=scores,
                    confidence=confidence,
                    match_method=match_method,
                    status=MappingStatus.PENDING,
                    created_at=now_iso(),
                    updated_at=now_iso(),
                )

        if best_record is None or best_confidence < 0:
            record = self._build_no_match_record(facebook_creative, mapping_id)
            self._store.save_record(record)
            return record

        # 置信度门禁判定
        if best_confidence >= self._confidence_threshold:
            best_record.status = MappingStatus.MATCHED
        elif best_confidence >= self._review_threshold:
            best_record.status = MappingStatus.NEEDS_REVIEW
        else:
            best_record.status = MappingStatus.NO_MATCH
            best_record.eagle_filename = ""
            best_record.eagle_path = ""

        self._store.save_record(best_record)

        # 低置信度 → 入审核队列
        if best_record.status == MappingStatus.NEEDS_REVIEW:
            # 只保留 top 5 候选
            top_candidates = sorted(
                candidates, key=lambda c: c["confidence"], reverse=True
            )[:5]
            self._review_queue.enqueue(
                mapping_id=mapping_id,
                facebook_creative_id=fb_id,
                candidates=top_candidates,
            )

        return best_record

    def batch_match(
        self, creatives: list[dict[str, Any]]
    ) -> list[CreativeMappingRecord]:
        """批量映射。"""
        return [self.match(c) for c in creatives]

    # ── 查询 ──────────────────────────────────────────────────

    def get_record(self, mapping_id: str) -> CreativeMappingRecord | None:
        return self._store.get_record(mapping_id)

    def get_by_facebook_id(self, fb_creative_id: str) -> CreativeMappingRecord | None:
        return self._store.get_by_facebook_id(fb_creative_id)

    def list_records(
        self, status: str = "", limit: int = 50
    ) -> list[CreativeMappingRecord]:
        return self._store.list_records(status=status, limit=limit)

    def get_stats(self) -> dict[str, Any]:
        return self._store.get_stats()

    # ── v1.5 Delivery Bridge 支持 ────────────────────────────

    def get_dispatchable_records(
        self,
        limit: int = 50,
        filter_status: list[MappingStatus] | None = None,
    ) -> list[CreativeMappingRecord]:
        """v1.5: 查询可投递记录。

        筛选条件:
          - status ∈ {MATCHED, REVIEW_APPROVED} (或自定义 filter_status)
          - delivery_status ∈ {UNDISPATCHED, FAILED}
          - eagle_path 非空

        排序: 按 confidence 降序
        """
        valid_statuses = filter_status or [
            MappingStatus.MATCHED,
            MappingStatus.REVIEW_APPROVED,
        ]
        valid_delivery = {
            MappingDeliveryStatus.UNDISPATCHED,
            MappingDeliveryStatus.FAILED,
        }
        all_records = self._store.list_all_records(limit=10000)
        dispatchable = [
            r
            for r in all_records
            if r.status in valid_statuses
            and r.delivery_status in valid_delivery
            and r.eagle_path
        ]
        # 按 confidence 降序
        dispatchable.sort(key=lambda r: r.confidence, reverse=True)
        return dispatchable[:limit]

    def update_delivery_status(
        self,
        mapping_id: str,
        delivery_status: MappingDeliveryStatus,
        publish_id: str = "",
        ad_id: str = "",
        ad_creative_id: str = "",
        delivery_error: str = "",
        increment_attempts: bool = False,
    ) -> bool:
        """v1.5: 代理 store.update_delivery_status()。"""
        return self._store.update_delivery_status(
            mapping_id=mapping_id,
            delivery_status=delivery_status,
            publish_id=publish_id,
            ad_id=ad_id,
            ad_creative_id=ad_creative_id,
            delivery_error=delivery_error,
            increment_attempts=increment_attempts,
        )

    def update_auto_structure(
        self,
        mapping_id: str,
        auto_campaign_id: str = "",
        auto_adset_id: str = "",
        auto_strategy: str = "",
    ) -> bool:
        """v1.6: 代理 store.update_auto_structure()，回写自动投放结构字段。"""
        return self._store.update_auto_structure(
            mapping_id=mapping_id,
            auto_campaign_id=auto_campaign_id,
            auto_adset_id=auto_adset_id,
            auto_strategy=auto_strategy,
        )

    def update_performance(
        self,
        mapping_id: str,
        performance: Any,
    ) -> bool:
        """v1.7: 代理 store.update_performance()，回写成效数据。"""
        return self._store.update_performance(
            mapping_id=mapping_id,
            performance=performance,
        )

    def update_strategy_fields(
        self,
        mapping_id: str,
        performance_score: float | None = None,
        delivery_priority: float | None = None,
        auto_archived: bool | None = None,
        auto_archived_reason: str = "",
    ) -> bool:
        """v1.8: 代理 store.update_strategy_fields()，回写策略字段。"""
        return self._store.update_strategy_fields(
            mapping_id=mapping_id,
            performance_score=performance_score,
            delivery_priority=delivery_priority,
            auto_archived=auto_archived,
            auto_archived_reason=auto_archived_reason,
        )

    # ── 审核代理 ──────────────────────────────────────────────

    def list_review_queue(self, limit: int = 50) -> list[dict[str, Any]]:
        return [t.to_dict() for t in self._review_queue.list_open(limit=limit)]

    def approve_review(
        self,
        task_id: str,
        eagle_filename: str,
        eagle_path: str = "",
        reviewer: str = "",
        note: str = "",
    ) -> dict[str, Any]:
        task = self._review_queue.approve(
            task_id=task_id,
            eagle_filename=eagle_filename,
            eagle_path=eagle_path,
            reviewer=reviewer,
            note=note,
        )
        return task.to_dict()

    def reject_review(
        self, task_id: str, reason: str, reviewer: str = ""
    ) -> dict[str, Any]:
        task = self._review_queue.reject(
            task_id=task_id, reason=reason, reviewer=reviewer
        )
        return task.to_dict()

    # ── 内部方法 ──────────────────────────────────────────────

    @staticmethod
    def _gen_mapping_id(fb_creative_id: str) -> str:
        """生成 mapping_id (facebook_creative_id 的短 hash)。"""
        h = hashlib.sha256(f"fb:{fb_creative_id}".encode("utf-8")).hexdigest()[:12]
        return f"map_{h}"

    def _build_no_match_record(
        self, facebook_creative: dict[str, Any], mapping_id: str
    ) -> CreativeMappingRecord:
        return CreativeMappingRecord(
            mapping_id=mapping_id,
            facebook_creative_id=facebook_creative.get("facebook_creative_id", ""),
            facebook_creative_name=facebook_creative.get("facebook_creative_name", ""),
            facebook_account_id=facebook_creative.get("facebook_account_id", ""),
            status=MappingStatus.NO_MATCH,
            created_at=now_iso(),
            updated_at=now_iso(),
        )


__all__ = ["CreativeMappingEngine"]
