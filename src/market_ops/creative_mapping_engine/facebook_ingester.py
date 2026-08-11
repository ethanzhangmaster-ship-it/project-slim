"""FacebookCreativeIngester — 从 Facebook API 拉取创意元数据并自动映射。

v1.4 新增模块。编排 FacebookClient（拉取创意 + 视频详情）与 CreativeMappingEngine
（6 维度匹配），实现从 Facebook API 到 Eagle 素材映射的完整闭环。

数据流::

    FacebookClient.get_ads()
        → 提取 creative{id, name, thumbnail_url, video_id}
        → FacebookClient.get_video(video_id)  # 补全 duration/resolution
        → 转换为 CME match() 输入格式
        → 增量过滤（跳过已 MATCHED/REVIEW_APPROVED）
        → CreativeMappingEngine.match()
        → IngestionResult

dry_run 模式：不调用真实 API，使用调用方提供的创意数据（ingest_creatives）。

Usage::

    # 生产模式
    ingester = FacebookCreativeIngester(engine=engine, facebook_client=client)
    result = ingester.ingest(ad_account_id="act_123", lookback_days=7)

    # dry_run 模式（测试）
    ingester = FacebookCreativeIngester(engine=engine, dry_run=True)
    result = ingester.ingest_creatives(creatives=[{...}, ...])
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .models import MappingStatus

if TYPE_CHECKING:
    from .engine import CreativeMappingEngine

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """拉取与映射结果汇总。"""

    total_fetched: int = 0
    total_mapped: int = 0
    total_skipped: int = 0
    total_errors: int = 0
    mappings: list[dict[str, Any]] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_fetched": self.total_fetched,
            "total_mapped": self.total_mapped,
            "total_skipped": self.total_skipped,
            "total_errors": self.total_errors,
            "mappings": self.mappings,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "dry_run": self.dry_run,
        }


class FacebookCreativeIngester:
    """从 Facebook API 拉取创意元数据并自动映射到 Eagle 素材。

    Args:
        engine: CreativeMappingEngine 实例
        facebook_client: FacebookClient 实例（dry_run 时可为 None）
        dry_run: 是否为 dry_run 模式（不调用真实 API）
    """

    def __init__(
        self,
        engine: CreativeMappingEngine,
        facebook_client: Any | None = None,
        dry_run: bool = False,
    ) -> None:
        self._engine = engine
        self._client = facebook_client
        self._dry_run = dry_run

    # ── Public API ───────────────────────────────────────

    def ingest(
        self,
        ad_account_id: str = "",
        lookback_days: int = 7,
        auto_map: bool = True,
    ) -> IngestionResult:
        """拉取 Facebook 创意并自动映射。

        Args:
            ad_account_id: 广告账户 ID（为空时使用 client 内置的 account_id）
            lookback_days: 回溯天数（未使用，预留）
            auto_map: 是否自动触发映射

        Returns:
            IngestionResult
        """
        started = time.time()
        result = IngestionResult(dry_run=self._dry_run)

        if self._client is None:
            logger.error("FacebookClient not available, cannot ingest")
            result.total_errors = 1
            result.elapsed_seconds = time.time() - started
            return result

        try:
            creatives = self._fetch_and_enrich(ad_account_id, lookback_days)
        except Exception as exc:
            logger.error("Failed to fetch creatives from Facebook: %s", exc)
            result.total_errors = 1
            result.elapsed_seconds = time.time() - started
            return result

        result.total_fetched = len(creatives)

        if auto_map:
            for creative in creatives:
                self._process_one(creative, result)

        result.elapsed_seconds = time.time() - started
        return result

    def ingest_creatives(
        self,
        creatives: list[dict[str, Any]],
        auto_map: bool = True,
    ) -> IngestionResult:
        """直接使用提供的创意数据（跳过 API 调用，用于测试/dry_run）。

        Args:
            creatives: 创意数据列表，每个元素是 dict
            auto_map: 是否自动触发映射

        Returns:
            IngestionResult
        """
        started = time.time()
        result = IngestionResult(dry_run=self._dry_run)
        result.total_fetched = len(creatives)

        if auto_map:
            for creative in creatives:
                self._process_one(creative, result)

        result.elapsed_seconds = time.time() - started
        return result

    # ── 内部方法 ─────────────────────────────────────────

    def _fetch_and_enrich(
        self,
        ad_account_id: str,
        lookback_days: int,
    ) -> list[dict[str, Any]]:
        """拉取创意并补全 duration/resolution。"""
        ads = self._client.get_ads()
        creatives: list[dict[str, Any]] = []

        for ad in ads:
            creative_data = ad.get("creative", {})
            if not creative_data or not creative_data.get("id"):
                continue

            creative = {
                "facebook_creative_id": creative_data.get("id", ""),
                "facebook_creative_name": creative_data.get("name", ad.get("name", "")),
                "facebook_account_id": ad_account_id or f"act_{self._client._account_id}",
                "thumbnail_url": creative_data.get("thumbnail_url", ""),
                "image_url": creative_data.get("image_url", ""),
                "video_id": creative_data.get("video_id", ""),
                "creation_time": ad.get("created_time", ""),
                "duration": 0.0,
                "resolution": "",
            }

            creative = self._enrich_video_metadata(creative)
            creatives.append(creative)

        return creatives

    def _enrich_video_metadata(
        self,
        creative: dict[str, Any],
    ) -> dict[str, Any]:
        """对视频类创意调用 get_video() 补全 duration/resolution。"""
        video_id = creative.get("video_id", "")
        if not video_id:
            return creative

        try:
            video = self._client.get_video(video_id)
            if video:
                length = video.get("length", 0)
                creative["duration"] = float(length) if length else 0.0

                width = video.get("width", 0)
                height = video.get("height", 0)
                if width and height:
                    creative["resolution"] = f"{width}x{height}"
        except Exception as exc:
            logger.warning(
                "Failed to enrich video metadata for video_id=%s: %s",
                video_id, exc,
            )

        return creative

    def _process_one(
        self,
        creative: dict[str, Any],
        result: IngestionResult,
    ) -> None:
        """处理单条创意：增量过滤 + 映射。"""
        fb_creative_id = creative.get("facebook_creative_id", "")
        if not fb_creative_id:
            result.total_errors += 1
            return

        # 增量过滤
        if self._should_skip(fb_creative_id):
            result.total_skipped += 1
            return

        # 转换为 match() 输入并执行映射
        match_input = self._to_match_input(creative)
        try:
            record = self._engine.match(match_input)
            result.mappings.append(record.to_dict())
            result.total_mapped += 1
        except Exception as exc:
            logger.error(
                "Failed to map creative %s: %s", fb_creative_id, exc,
            )
            result.total_errors += 1

    def _should_skip(self, fb_creative_id: str) -> bool:
        """检查是否应跳过（已有 MATCHED 或 REVIEW_APPROVED 记录）。"""
        existing = self._engine.get_by_facebook_id(fb_creative_id)
        if existing is None:
            return False
        return existing.status in (MappingStatus.MATCHED, MappingStatus.REVIEW_APPROVED)

    @staticmethod
    def _to_match_input(creative: dict[str, Any]) -> dict[str, Any]:
        """将创意数据转换为 CreativeMappingEngine.match() 的输入格式。"""
        return {
            "facebook_creative_id": creative.get("facebook_creative_id", ""),
            "facebook_creative_name": creative.get("facebook_creative_name", ""),
            "facebook_account_id": creative.get("facebook_account_id", ""),
            "thumbnail_url": creative.get("thumbnail_url", ""),
            "video_url": creative.get("image_url", ""),
            "duration": creative.get("duration", 0.0),
            "resolution": creative.get("resolution", ""),
            "creation_time": creative.get("creation_time", ""),
        }


__all__ = ["FacebookCreativeIngester", "IngestionResult"]
