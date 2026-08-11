"""E11 Phase 2 — Adjust Sync Engine。

编排完整的 Adjust 同步流程：
  1. fetch:     从 Adjust API 抓取数据
  2. parse:     解析为 AdjustRevenueEntity
  3. save:      保存 adjust.json
  4. load:      加载 CreativeEntity
  5. match:     匹配 Adjust → CreativeEntity
  6. merge:     合并收入数据
  7. calculate: 计算 ROAS/LTV
  8. save:      回写 entity.json
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .adjust_client import AdjustClient
from .adjust_fetcher import AdjustFetcher
from .matcher import AdjustCreativeMatcher, AdjustMatchReport
from .revenue_calculator import RevenueCalculator
from .storage import AdjustStorage

if TYPE_CHECKING:
    from market_ops.facebook_ingestion.storage import CreativeStorage


@dataclass
class AdjustSyncResult:
    """Adjust 同步结果。

    Usage:
        result = engine.sync(...)
        print(result.to_summary())
    """

    total_records: int = 0
    creative_entities_loaded: int = 0
    creative_entities_updated: int = 0
    match_report: AdjustMatchReport | None = None
    total_spend: float = 0.0
    total_revenue: float = 0.0
    overall_roas: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_summary(self) -> str:
        """生成 CLI 输出摘要。"""
        lines = [
            "",
            "=" * 60,
            "  Adjust Sync Completed",
            "=" * 60,
            "",
            f"  Records: {self.total_records}",
            f"  Creative Entities Loaded: {self.creative_entities_loaded}",
        ]

        if self.match_report:
            lines.append(
                f"  Matched: {self.match_report.matched}"
            )
            lines.append(
                f"  Match Rate: {self.match_report.match_rate:.1%}"
            )

        lines.append(
            f"  Entity Updated: {self.creative_entities_updated}"
        )
        lines.append(
            f"  Total Spend: ${self.total_spend:,.2f}"
        )
        lines.append(
            f"  Total Revenue: ${self.total_revenue:,.2f}"
        )
        lines.append(
            f"  Overall ROAS: {self.overall_roas:.2f}"
        )

        if self.errors:
            lines.append(f"\n  Errors: {len(self.errors)}")
            for err in self.errors[:5]:
                lines.append(f"    - {err}")

        lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_records": self.total_records,
            "creative_entities_loaded": self.creative_entities_loaded,
            "creative_entities_updated": self.creative_entities_updated,
            "match_report": self.match_report.to_dict() if self.match_report else None,
            "total_spend": self.total_spend,
            "total_revenue": self.total_revenue,
            "overall_roas": self.overall_roas,
            "errors": self.errors,
        }


class AdjustSyncEngine:
    """Adjust 同步引擎。

    编排完整的 Adjust 数据同步流程。

    Usage:
        client = AdjustClient(api_token="xxx", app_token="yyy")
        engine = AdjustSyncEngine(client, creative_storage)
        result = engine.sync(start_date="2026-07-01", end_date="2026-07-21")
        print(result.to_summary())
    """

    def __init__(
        self,
        client: AdjustClient,
        creative_storage: CreativeStorage,
    ) -> None:
        self._client = client
        self._creative_storage = creative_storage
        self._fetcher = AdjustFetcher(client)
        self._matcher = AdjustCreativeMatcher()
        self._calculator = RevenueCalculator()

    def sync(
        self,
        start_date: str,
        end_date: str,
    ) -> AdjustSyncResult:
        """执行完整同步流程。

        Steps:
          1. 从 Adjust API 抓取数据
          2. 解析为 AdjustRevenueEntity
          3. 保存 adjust.json
          4. 加载 CreativeEntity
          5. 匹配 Adjust → CreativeEntity
          6. 合并收入数据
          7. 计算 ROAS/LTV
          8. 回写 entity.json

        Args:
            start_date: 起始日期 (YYYY-MM-DD)
            end_date:   结束日期 (YYYY-MM-DD)

        Returns:
            AdjustSyncResult 同步结果
        """
        result = AdjustSyncResult()
        errors: list[str] = []

        # Step 1-2: Fetch & Parse
        try:
            adjust_entities = self._fetcher.fetch(start_date, end_date)
            result.total_records = len(adjust_entities)
        except Exception as e:
            errors.append(f"Fetch failed: {e}")
            result.errors = errors
            return result

        if not adjust_entities:
            return result

        # Step 3: Save adjust.json
        adjust_storage = AdjustStorage(self._creative_storage.root_dir)
        for entity in adjust_entities:
            if entity.creative_asset_id:
                try:
                    adjust_storage.save(entity)
                except Exception as e:
                    errors.append(f"Save adjust.json failed for {entity.creative_asset_id}: {e}")

        # Step 4: Load CreativeEntities
        creative_entities = self._creative_storage.list_all_creative_entities()
        result.creative_entities_loaded = len(creative_entities)

        if not creative_entities:
            return result

        # Step 5-6: Match & Merge
        match_report = self._matcher.match(creative_entities, adjust_entities)
        result.match_report = match_report

        # Step 7: Calculate ROAS / LTV
        updated_entities = [
            ce for ce in creative_entities
            if ce.has_revenue
        ]

        if updated_entities:
            summary = self._calculator.calculate_summary(updated_entities)
            result.total_spend = summary["total_spend"]
            result.total_revenue = summary["total_revenue"]
            result.overall_roas = summary["overall_roas"]

        # Step 8: Save entity.json (回写更新后的 CreativeEntity)
        updated_count = 0
        for ce in creative_entities:
            if "adjust" in ce.synced_sources:
                try:
                    self._creative_storage.save_existing_entity(ce)
                    updated_count += 1
                except Exception as e:
                    errors.append(f"Save entity.json failed for {ce.creative_asset_id}: {e}")

        result.creative_entities_updated = updated_count
        result.errors = errors

        return result

    @property
    def client(self) -> AdjustClient:
        return self._client

    @property
    def creative_storage(self) -> CreativeStorage:
        return self._creative_storage

    def __repr__(self) -> str:
        return f"AdjustSyncEngine(client={self._client!r})"