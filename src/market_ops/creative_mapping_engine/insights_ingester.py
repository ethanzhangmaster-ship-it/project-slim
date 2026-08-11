"""FacebookInsightsIngester — 拉取 Facebook insights 并回写成效数据 (v1.7).

投递完成后（v1.5/v1.6），通过 FacebookClient.get_creative_insights() 拉取成效数据，
回写到 CreativeMappingRecord.performance，形成真正的双向闭环。

核心流程:
  1. 查询所有 delivery_status=PUBLISHED 且有 ad_id 的记录
  2. 调用 FacebookClient.get_creative_insights(start, end)
  3. 按 creative_id 匹配映射记录
  4. 解析 actions 数组提取 installs (app_install / mobile_app_install)
  5. 更新 CreativeMappingRecord.performance
  6. 持久化到 records.jsonl

dry_run 模式：不调用真实 API，使用调用方提供的 insights 数据（ingest_insights_batch）。

Usage::

    # 生产模式
    ingester = FacebookInsightsIngester(engine=engine, facebook_client=client)
    result = ingester.ingest_insights(start_date="2026-08-01", end_date="2026-08-10")

    # dry_run 模式（测试）
    ingester = FacebookInsightsIngester(engine=engine, dry_run=True)
    result = ingester.ingest_insights_batch(insights=[{...}, ...])
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional

from .models import MappingDeliveryStatus, now_iso

if TYPE_CHECKING:
    from .engine import CreativeMappingEngine

logger = logging.getLogger(__name__)


# ── 数据模型 ──────────────────────────────────────────────────


@dataclass
class CreativePerformance:
    """创意投放成效数据 (v1.7)."""

    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    cpc: float = 0.0
    cpm: float = 0.0
    installs: int = 0
    last_synced_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "spend": round(self.spend, 4),
            "impressions": self.impressions,
            "clicks": self.clicks,
            "ctr": round(self.ctr, 6),
            "cpc": round(self.cpc, 4),
            "cpm": round(self.cpm, 4),
            "installs": self.installs,
            "last_synced_at": self.last_synced_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativePerformance:
        return cls(
            spend=float(data.get("spend", 0.0)),
            impressions=int(data.get("impressions", 0)),
            clicks=int(data.get("clicks", 0)),
            ctr=float(data.get("ctr", 0.0)),
            cpc=float(data.get("cpc", 0.0)),
            cpm=float(data.get("cpm", 0.0)),
            installs=int(data.get("installs", 0)),
            last_synced_at=data.get("last_synced_at", ""),
        )


@dataclass
class InsightsIngestionResult:
    """insights 拉取与回写结果汇总。"""

    total_fetched: int = 0
    total_matched: int = 0
    total_updated: int = 0
    total_skipped: int = 0
    total_errors: int = 0
    updates: list[dict[str, Any]] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    dry_run: bool = False
    start_date: str = ""
    end_date: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_fetched": self.total_fetched,
            "total_matched": self.total_matched,
            "total_updated": self.total_updated,
            "total_skipped": self.total_skipped,
            "total_errors": self.total_errors,
            "updates": self.updates,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "dry_run": self.dry_run,
            "start_date": self.start_date,
            "end_date": self.end_date,
        }


# ── FacebookInsightsIngester ──────────────────────────────────


class FacebookInsightsIngester:
    """拉取 Facebook insights 并回写到 CreativeMappingRecord (v1.7)。

    Args:
        engine: CreativeMappingEngine 实例
        facebook_client: FacebookClient 实例（dry_run 时可为 None）
        data_dir: 数据目录（默认 engine 的 data_dir）
        dry_run: 是否为 dry_run 模式（不调用真实 API）
    """

    # actions 数组中 install action 的识别 key
    INSTALL_ACTION_KEYS = ("app_install", "mobile_app_install", "omobile_app_install")

    def __init__(
        self,
        engine: CreativeMappingEngine,
        facebook_client: Any | None = None,
        data_dir: Optional[str] = None,
        dry_run: bool = False,
    ) -> None:
        self._engine = engine
        self._client = facebook_client
        self._dry_run = dry_run
        if data_dir:
            from pathlib import Path
            self._data_dir = Path(data_dir)
        else:
            store = engine.store
            self._data_dir = store._dir  # type: ignore[attr-defined]
        self._audit_path = self._data_dir / "insights_audit.jsonl"

    # ── 属性 ──────────────────────────────────────────────

    @property
    def engine(self) -> CreativeMappingEngine:
        return self._engine

    @property
    def facebook_client(self) -> Any | None:
        return self._client

    # ── 公共 API ──────────────────────────────────────────

    def ingest_insights(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        lookback_days: int = 7,
        dry_run: Optional[bool] = None,
    ) -> InsightsIngestionResult:
        """拉取 Facebook insights 并回写 (生产模式)。

        Args:
            start_date: 开始日期 (YYYY-MM-DD)，默认 lookback_days 天前
            end_date: 结束日期 (YYYY-MM-DD)，默认今天
            lookback_days: 回溯天数 (start_date 为空时使用)
            dry_run: 覆盖实例 dry_run 设置

        Returns:
            InsightsIngestionResult
        """
        is_dry = self._dry_run if dry_run is None else dry_run
        result = InsightsIngestionResult(dry_run=is_dry)

        # 1. 解析日期范围
        end_dt = self._parse_date(end_date) if end_date else date.today()
        if start_date:
            start_dt = self._parse_date(start_date)
        else:
            start_dt = end_dt - timedelta(days=lookback_days)

        result.start_date = start_dt.isoformat()
        result.end_date = end_dt.isoformat()

        t0 = time.time()

        # 2. dry_run: 不调用 API
        if is_dry:
            result.elapsed_seconds = time.time() - t0
            logger.info(
                "InsightsIngester dry_run: skip API call (range=%s~%s)",
                result.start_date, result.end_date,
            )
            return result

        # 3. 真实模式：调用 FacebookClient
        if self._client is None:
            result.total_errors = 1
            result.elapsed_seconds = time.time() - t0
            logger.error("InsightsIngester: no facebook_client configured")
            return result

        try:
            raw_insights = self._client.get_creative_insights(
                start_date=start_dt,
                end_date=end_dt,
            )
        except Exception as exc:
            result.total_errors = 1
            result.elapsed_seconds = time.time() - t0
            logger.exception("InsightsIngester: get_creative_insights failed: %s", exc)
            return result

        result.total_fetched = len(raw_insights)

        # 4. 回写
        self._match_and_update(raw_insights, result)
        result.elapsed_seconds = time.time() - t0
        return result

    def ingest_insights_batch(
        self,
        insights: list[dict[str, Any]],
        dry_run: Optional[bool] = None,
    ) -> InsightsIngestionResult:
        """使用调用方提供的 insights 数据回写 (测试/dry_run 模式)。

        Args:
            insights: Facebook insights 数据列表
            dry_run: 覆盖实例 dry_run 设置

        Returns:
            InsightsIngestionResult
        """
        is_dry = self._dry_run if dry_run is None else dry_run
        result = InsightsIngestionResult(dry_run=is_dry)
        result.total_fetched = len(insights)
        t0 = time.time()

        self._match_and_update(insights, result, skip_audit=is_dry)
        result.elapsed_seconds = time.time() - t0
        return result

    def get_performance(self, mapping_id: str) -> dict[str, Any]:
        """查询单条记录的成效数据。"""
        record = self._engine.get_record(mapping_id)
        if record is None:
            return {
                "success": False,
                "error": "mapping not found",
                "mapping_id": mapping_id,
            }

        perf = record.performance
        return {
            "success": True,
            "mapping_id": mapping_id,
            "facebook_creative_id": record.facebook_creative_id,
            "ad_id": record.ad_id,
            "delivery_status": record.delivery_status.value,
            "performance": perf.to_dict() if perf is not None else None,
        }

    def get_top_performers(self, limit: int = 20) -> list[dict[str, Any]]:
        """批量查询成效 (按 spend 降序 top N)。"""
        records = self._list_published_records()
        performers: list[tuple[float, CreativeMappingRecord, CreativePerformance]] = []
        for r in records:
            if r.performance is not None:
                performers.append((r.performance.spend, r, r.performance))

        performers.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "mapping_id": r.mapping_id,
                "facebook_creative_id": r.facebook_creative_id,
                "ad_id": r.ad_id,
                "performance": p.to_dict(),
            }
            for _, r, p in performers[:limit]
        ]

    # ── 内部方法 ──────────────────────────────────────────

    def _parse_date(self, date_str: str) -> date:
        """解析 YYYY-MM-DD 日期字符串。"""
        return datetime.strptime(date_str, "%Y-%m-%d").date()

    def _list_published_records(self) -> list[Any]:
        """查询所有 PUBLISHED 且有 ad_id 的记录。"""
        all_records = self._engine.store.list_records(limit=10000)
        return [
            r for r in all_records
            if r.delivery_status == MappingDeliveryStatus.PUBLISHED and r.ad_id
        ]

    def _match_and_update(
        self,
        insights: list[dict[str, Any]],
        result: InsightsIngestionResult,
        skip_audit: bool = False,
    ) -> None:
        """将 insights 按 creative_id 匹配并回写。"""
        # 构造 creative_id → insight 索引
        insight_by_creative: dict[str, dict[str, Any]] = {}
        for ins in insights:
            creative_id = self._extract_creative_id(ins)
            if creative_id:
                insight_by_creative[creative_id] = ins

        # 查询所有 PUBLISHED 记录
        published = self._list_published_records()

        for record in published:
            creative_id = record.facebook_creative_id
            if not creative_id or creative_id not in insight_by_creative:
                result.total_skipped += 1
                continue

            result.total_matched += 1
            ins = insight_by_creative[creative_id]

            # 解析成效数据
            perf = self._parse_insight(ins)
            if perf is None:
                result.total_errors += 1
                continue

            # 回写
            ok = self._engine.store.update_performance(
                mapping_id=record.mapping_id,
                performance=perf,
            )
            if ok:
                result.total_updated += 1
                result.updates.append({
                    "mapping_id": record.mapping_id,
                    "facebook_creative_id": creative_id,
                    "ad_id": record.ad_id,
                    "spend": perf.spend,
                    "impressions": perf.impressions,
                    "clicks": perf.clicks,
                    "installs": perf.installs,
                    "ctr": perf.ctr,
                })
                if not skip_audit:
                    self._write_audit(record.mapping_id, creative_id, perf)
            else:
                result.total_errors += 1

    def _extract_creative_id(self, insight: dict[str, Any]) -> str:
        """从 insight 数据中提取 creative_id。"""
        # Facebook insights 中 creative 是嵌套对象: {"id": "123", ...}
        creative_obj = insight.get("creative")
        if isinstance(creative_obj, dict):
            return str(creative_obj.get("id", ""))
        if isinstance(creative_obj, str) and creative_obj:
            return creative_obj
        # 退化：用 ad_id 作为 key (精确度较低)
        return ""

    def _parse_insight(self, insight: dict[str, Any]) -> Optional[CreativePerformance]:
        """解析单条 insight 数据为 CreativePerformance。"""
        try:
            spend = float(insight.get("spend", "0") or 0)
            impressions = int(insight.get("impressions", "0") or 0)
            clicks = int(insight.get("clicks", "0") or 0)
            ctr = float(insight.get("ctr", "0") or 0)
            cpc = float(insight.get("cpc", "0") or 0)
            cpm = float(insight.get("cpm", "0") or 0)
            installs = self._extract_installs(insight)

            return CreativePerformance(
                spend=spend,
                impressions=impressions,
                clicks=clicks,
                ctr=ctr,
                cpc=cpc,
                cpm=cpm,
                installs=installs,
                last_synced_at=now_iso(),
            )
        except (ValueError, TypeError) as exc:
            logger.warning("InsightsIngester: parse insight failed: %s", exc)
            return None

    def _extract_installs(self, insight: dict[str, Any]) -> int:
        """从 actions 数组提取 install 数量。

        Facebook insights 的 actions 字段格式:
            "actions": [
                {"action_type": "app_install", "value": "42"},
                {"action_type": "link_click", "value": "100"},
                ...
            ]
        """
        actions = insight.get("actions", [])
        if not isinstance(actions, list):
            return 0

        total = 0
        for action in actions:
            if not isinstance(action, dict):
                continue
            action_type = action.get("action_type", "")
            if action_type in self.INSTALL_ACTION_KEYS:
                try:
                    total += int(action.get("value", "0") or 0)
                except (ValueError, TypeError):
                    pass
        return total

    def _write_audit(
        self,
        mapping_id: str,
        creative_id: str,
        perf: CreativePerformance,
    ) -> None:
        """写入审计日志。"""
        import json
        entry = {
            "timestamp": now_iso(),
            "mapping_id": mapping_id,
            "creative_id": creative_id,
            "spend": perf.spend,
            "impressions": perf.impressions,
            "clicks": perf.clicks,
            "installs": perf.installs,
        }
        with open(self._audit_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


__all__ = [
    "CreativePerformance",
    "InsightsIngestionResult",
    "FacebookInsightsIngester",
]
