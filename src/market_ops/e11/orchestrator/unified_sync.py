"""E11.1 — Unified Sync Orchestrator。

职责：编排 Facebook + Adjust 两个 SyncEngine，统一写入 CreativeStorage。

不做：
  - 不直接调用 Facebook/Adjust API（由 SyncEngine 处理）
  - 不做 CSV merge（由 CreativeStorage 管理）
  - 不做 Entity merge（已在 SyncEngine 内部完成）

Usage:
    orchestrator = UnifiedSyncOrchestrator(
        creative_storage_root="data/creatives",
        facebook_accounts=[
            {"id": "123456", "name": "P04 And 1", "platform": "Android"},
        ],
        adjust_config={"api_token": "xxx", "app_token": "yyy"},
        fb_token="EAA...",
        fb_api_version="v19.0",
    )
    report = orchestrator.run_daily_sync()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from market_ops.facebook_ingestion import SyncEngine, CreativeFetcher, AdParser
from market_ops.facebook_ingestion.facebook_client import FacebookClient
from market_ops.facebook_ingestion.storage import CreativeStorage
from market_ops.adjust_ingestion.adjust_client import AdjustClient
from market_ops.adjust_ingestion.sync_engine import AdjustSyncEngine

logger = logging.getLogger(__name__)


@dataclass
class SyncReport:
    """统一同步报告。

    聚合 Facebook + Adjust 两个子引擎的结果。
    """

    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0

    # Facebook 结果
    fb_accounts_synced: int = 0
    fb_entities_created: int = 0
    fb_entities_updated: int = 0
    fb_errors: list[str] = field(default_factory=list)

    # Adjust 结果
    adjust_records: int = 0
    adjust_matched: int = 0
    adjust_entities_updated: int = 0
    adjust_total_spend: float = 0.0
    adjust_total_revenue: float = 0.0
    adjust_match_rate: float = 0.0
    adjust_errors: list[str] = field(default_factory=list)

    # Storage 统计
    creative_storage_count: int = 0
    storage_root: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": round(self.duration_seconds, 1),
            "facebook": {
                "accounts_synced": self.fb_accounts_synced,
                "entities_created": self.fb_entities_created,
                "entities_updated": self.fb_entities_updated,
                "errors": len(self.fb_errors),
            },
            "adjust": {
                "records": self.adjust_records,
                "matched": self.adjust_matched,
                "entities_updated": self.adjust_entities_updated,
                "total_spend": round(self.adjust_total_spend, 2),
                "total_revenue": round(self.adjust_total_revenue, 2),
                "match_rate": round(self.adjust_match_rate, 3),
                "errors": len(self.adjust_errors),
            },
            "storage": {
                "root": self.storage_root,
                "total_entities": self.creative_storage_count,
            },
        }

    def to_summary(self) -> str:
        lines = [
            "",
            "=" * 60,
            "  E11.1 Unified Sync Report",
            "=" * 60,
            "",
            f"  Started:   {self.started_at}",
            f"  Completed: {self.completed_at}",
            f"  Duration:  {round(self.duration_seconds)}s",
            "",
            "  ── Facebook ──",
            f"  Accounts:  {self.fb_accounts_synced}",
            f"  Created:   {self.fb_entities_created}",
            f"  Updated:   {self.fb_entities_updated}",
            f"  Errors:    {len(self.fb_errors)}",
            "",
            "  ── Adjust ──",
            f"  Records:   {self.adjust_records}",
            f"  Matched:   {self.adjust_matched}",
            f"  Match Rate:{self.adjust_match_rate:.1%}",
            f"  Updated:   {self.adjust_entities_updated}",
            f"  Revenue:   ${self.adjust_total_revenue:,.2f}",
            f"  Errors:    {len(self.adjust_errors)}",
            "",
            "  ── Storage ──",
            f"  Root:      {self.storage_root}",
            f"  Entities:  {self.creative_storage_count}",
            "",
            "=" * 60,
        ]
        return "\n".join(lines)


class UnifiedSyncOrchestrator:
    """统一同步编排器。

    编排 Facebook + Adjust 两个 SyncEngine，
    统一写入 CreativeStorage。

    不直接调用 API，不写 CSV merge 逻辑。
    """

    def __init__(
        self,
        creative_storage_root: str = "data/creatives",
        facebook_accounts: list[dict[str, str]] | None = None,
        adjust_config: dict[str, str] | None = None,
        fb_token: str = "",
        fb_api_version: str = "v19.0",
    ) -> None:
        """
        Args:
            creative_storage_root: CreativeStorage 根目录
            facebook_accounts: Facebook 广告账户列表
                [{"id": "123456", "name": "P04 And 1", "platform": "Android"}, ...]
            adjust_config: Adjust API 配置
                {"api_token": "xxx", "app_token": "yyy"}
            fb_token: Facebook Access Token
            fb_api_version: Facebook API 版本号
        """
        self._storage_root = creative_storage_root
        self._facebook_accounts = facebook_accounts or []
        self._adjust_config = adjust_config or {}
        self._fb_token = fb_token
        self._fb_api_version = fb_api_version

        # 共享的 CreativeStorage
        self._creative_storage = CreativeStorage(creative_storage_root)

    # ── Public API ─────────────────────────────────────────

    def run_daily_sync(
        self,
        fb_date: date | None = None,
        adjust_start: str | None = None,
        adjust_end: str | None = None,
    ) -> SyncReport:
        """执行每日同步。

        默认：
          - Facebook: 同步昨天
          - Adjust:   同步最近 30 天

        Args:
            fb_date: Facebook 同步日期 (默认昨天)
            adjust_start: Adjust 起始日期 (默认 30 天前)
            adjust_end: Adjust 结束日期 (默认今天)

        Returns:
            SyncReport 同步报告
        """
        started = datetime.now()
        report = SyncReport(
            started_at=started.isoformat(),
            storage_root=self._storage_root,
        )

        # 默认日期
        if fb_date is None:
            fb_date = date.today() - timedelta(days=1)
        if adjust_end is None:
            adjust_end = date.today().isoformat()
        if adjust_start is None:
            adjust_start = (date.today() - timedelta(days=30)).isoformat()

        # 1. Facebook 同步
        logger.info("Starting Facebook sync for %s...", fb_date)
        fb_report = self.sync_facebook(start_date=fb_date, end_date=fb_date)
        report.fb_accounts_synced = fb_report.get("accounts_synced", 0)
        report.fb_entities_created = fb_report.get("entities_created", 0)
        report.fb_entities_updated = fb_report.get("entities_updated", 0)
        report.fb_errors = fb_report.get("errors", [])

        # 2. Adjust 同步
        logger.info("Starting Adjust sync %s ~ %s...", adjust_start, adjust_end)
        adjust_report = self.sync_adjust(
            start_date=adjust_start, end_date=adjust_end,
        )
        report.adjust_records = adjust_report.get("records", 0)
        report.adjust_matched = adjust_report.get("matched", 0)
        report.adjust_entities_updated = adjust_report.get("entities_updated", 0)
        report.adjust_total_spend = adjust_report.get("total_spend", 0.0)
        report.adjust_total_revenue = adjust_report.get("total_revenue", 0.0)
        report.adjust_match_rate = adjust_report.get("match_rate", 0.0)
        report.adjust_errors = adjust_report.get("errors", [])

        # 3. Storage 统计
        report.creative_storage_count = self._creative_storage.count()

        completed = datetime.now()
        report.completed_at = completed.isoformat()
        report.duration_seconds = (completed - started).total_seconds()

        logger.info(report.to_summary())
        return report

    def sync_facebook(
        self,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """同步 Facebook 广告数据。

        遍历所有配置的广告账户，每个账户创建独立的 SyncEngine。

        Returns:
            {"accounts_synced": N, "entities_created": N, "entities_updated": N, "errors": [...]}
        """
        accounts_synced = 0
        entities_created = 0
        entities_updated = 0
        errors: list[str] = []

        for account in self._facebook_accounts:
            account_id = account.get("id", "")
            account_name = account.get("name", "unknown")

            if not account_id or not self._fb_token:
                errors.append(f"Skip account {account_name}: missing id or token")
                continue

            try:
                client = FacebookClient(
                    access_token=self._fb_token,
                    ad_account_id=account_id,
                    api_version=self._fb_api_version,
                )
                fetcher = CreativeFetcher(client)
                parser = AdParser()

                engine = SyncEngine(
                    client=client,
                    fetcher=fetcher,
                    parser=parser,
                    storage=self._creative_storage,
                )

                result = engine.sync(start_date, end_date)
                accounts_synced += 1
                entities_created += result.entities_created
                entities_updated += result.entities_updated

                if result.errors:
                    errors.extend(
                        [f"[{account_name}] {e}" for e in result.errors]
                    )

                logger.info(
                    "  FB %s: created=%d updated=%d",
                    account_name, result.entities_created, result.entities_updated,
                )

            except Exception as e:
                errors.append(f"[{account_name}] {e}")
                logger.exception("Facebook sync failed for %s", account_name)

        return {
            "accounts_synced": accounts_synced,
            "entities_created": entities_created,
            "entities_updated": entities_updated,
            "errors": errors,
        }

    def sync_adjust(
        self,
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """同步 Adjust 归因数据。

        创建 AdjustSyncEngine，执行：
          fetch → parse → save → load → match → merge → calculate → save

        Returns:
            {"records": N, "matched": N, "entities_updated": N,
             "total_spend": X, "total_revenue": X, "match_rate": X, "errors": [...]}
        """
        api_token = self._adjust_config.get("api_token", "")
        app_token = self._adjust_config.get("app_token", "")

        if not api_token:
            return {
                "records": 0, "matched": 0, "entities_updated": 0,
                "total_spend": 0.0, "total_revenue": 0.0,
                "match_rate": 0.0,
                "errors": ["Adjust API token not configured"],
            }

        try:
            client = AdjustClient(
                api_token=api_token,
                app_token=app_token,
            )
            engine = AdjustSyncEngine(
                client=client,
                creative_storage=self._creative_storage,
            )

            result = engine.sync(start_date, end_date)

            logger.info(
                "  Adjust: records=%d matched=%d updated=%d revenue=%.2f",
                result.total_records,
                result.match_report.matched if result.match_report else 0,
                result.creative_entities_updated,
                result.total_revenue,
            )

            return {
                "records": result.total_records,
                "matched": result.match_report.matched if result.match_report else 0,
                "entities_updated": result.creative_entities_updated,
                "total_spend": result.total_spend,
                "total_revenue": result.total_revenue,
                "match_rate": result.match_report.match_rate if result.match_report else 0.0,
                "errors": result.errors,
            }

        except Exception as e:
            logger.exception("Adjust sync failed")
            return {
                "records": 0, "matched": 0, "entities_updated": 0,
                "total_spend": 0.0, "total_revenue": 0.0,
                "match_rate": 0.0,
                "errors": [str(e)],
            }

    # ── Properties ─────────────────────────────────────────

    @property
    def creative_storage(self) -> CreativeStorage:
        return self._creative_storage

    @property
    def storage_root(self) -> str:
        return self._storage_root

    def __repr__(self) -> str:
        return (
            f"UnifiedSyncOrchestrator("
            f"storage={self._storage_root!r}, "
            f"fb_accounts={len(self._facebook_accounts)}, "
            f"adjust={'configured' if self._adjust_config.get('api_token') else 'not configured'})"
        )