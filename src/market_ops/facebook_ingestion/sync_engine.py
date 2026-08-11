"""E11 Phase 1 — Facebook Sync Engine。

编排完整同步流程：
  Facebook Ads 数据 → 标准化 Creative Entity → 存储到 Repository。

流程：
  fetch campaigns → fetch ads → fetch creatives → fetch insights
    → parse creative_asset_id → save CreativeEntity

支持：
  - 手动执行: python sync_facebook.py --date 2026-07-20 --account xxx
  - 定时同步: 后续支持 cron

Usage:
    engine = SyncEngine(client, storage, parser, fetcher)
    result = engine.sync(start_date, end_date)
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from .facebook_client import FacebookClient
from .creative_fetcher import CreativeFetcher
from .ad_parser import AdParser
from .storage import CreativeStorage
from .models import FacebookCreativeEntity

logger = logging.getLogger(__name__)


class SyncResult:
    """同步结果。"""

    def __init__(self) -> None:
        self.account_id: str = ""
        self.start_date: date | None = None
        self.end_date: date | None = None
        self.total_ads: int = 0
        self.entities_created: int = 0
        self.entities_updated: int = 0
        self.entities_failed: int = 0
        self.errors: list[str] = []
        self.duration_seconds: float = 0.0
        self.started_at: str = ""
        self.completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "date_range": f"{self.start_date} → {self.end_date}",
            "total_ads": self.total_ads,
            "created": self.entities_created,
            "updated": self.entities_updated,
            "failed": self.entities_failed,
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds, 1),
        }

    def to_log(self) -> str:
        return (
            f"\nFacebook Sync Completed\n"
            f"  Account: {self.account_id}\n"
            f"  Date: {self.start_date} → {self.end_date}\n"
            f"  Ads: {self.total_ads}\n"
            f"  New Creative: {self.entities_created}\n"
            f"  Updated: {self.entities_updated}\n"
            f"  Failed: {self.entities_failed}\n"
            f"  Duration: {round(self.duration_seconds)}s\n"
        )


class SyncEngine:
    """Facebook 广告同步引擎。

    编排从 Facebook API 到 Creative Repository 的完整数据管道。

    Usage:
        client = FacebookClient(token, account_id)
        fetcher = CreativeFetcher(client)
        parser = AdParser()
        storage = CreativeStorage("data/creatives")

        engine = SyncEngine(client, fetcher=fetcher, parser=parser, storage=storage)
        result = engine.sync(start_date, end_date)
    """

    def __init__(
        self,
        client: FacebookClient,
        fetcher: CreativeFetcher | None = None,
        parser: AdParser | None = None,
        storage: CreativeStorage | None = None,
    ) -> None:
        self._client = client
        self._fetcher = fetcher or CreativeFetcher(client)
        self._parser = parser or AdParser()
        self._storage = storage or CreativeStorage()

    def sync(
        self,
        start_date: date,
        end_date: date,
    ) -> SyncResult:
        """执行完整同步。

        Args:
            start_date: 开始日期
            end_date:   结束日期

        Returns:
            SyncResult
        """
        result = SyncResult()
        result.account_id = self._client.account_id
        result.start_date = start_date
        result.end_date = end_date
        result.started_at = datetime.now().isoformat()

        started = datetime.now()

        try:
            # 1. 拉取 Facebook 数据
            logger.info("Fetching Facebook ads...")
            entities = self._fetcher.fetch_all(start_date, end_date)
            result.total_ads = len(entities)
            logger.info(f"Fetched {len(entities)} ads")

            # 2. 解析 creative_asset_id
            logger.info("Parsing creative asset IDs...")
            entities = self._parser.parse_batch(entities)

            # 3. 过滤无 asset_id 的
            valid_entities = [e for e in entities if e.has_asset_id]
            skipped = len(entities) - len(valid_entities)
            if skipped > 0:
                logger.warning(f"Skipped {skipped} entities without asset_id")

            # 4. 保存
            logger.info(f"Saving {len(valid_entities)} entities...")
            stats = self._storage.save_batch(valid_entities)
            result.entities_created = stats["created"]
            result.entities_updated = stats["updated"]
            result.entities_failed = 0

            logger.info(
                f"Created {stats['created']}, "
                f"Updated {stats['updated']}"
            )

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            result.errors.append(str(e))
            result.entities_failed = result.total_ads

        result.duration_seconds = (datetime.now() - started).total_seconds()
        result.completed_at = datetime.now().isoformat()

        logger.info(result.to_log())
        return result

    def sync_yesterday(self) -> SyncResult:
        """同步昨天的数据。"""
        today = date.today()
        yesterday = today - timedelta(days=1)
        return self.sync(yesterday, today)

    def sync_last_7_days(self) -> SyncResult:
        """同步最近 7 天。"""
        today = date.today()
        return self.sync(today - timedelta(days=7), today)

    def sync_last_30_days(self) -> SyncResult:
        """同步最近 30 天。"""
        today = date.today()
        return self.sync(today - timedelta(days=30), today)

    def merge_all_entities(self) -> list[FacebookCreativeEntity]:
        """返回所有已存储的 Entity（去重）。"""
        return self._storage.list_all()

    @property
    def client(self) -> FacebookClient:
        return self._client

    @property
    def storage(self) -> CreativeStorage:
        return self._storage

    def __repr__(self) -> str:
        return f"SyncEngine(account={self._client.account_id})"