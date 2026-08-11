"""E15.0.8 Event Repository — 增长事件持久化.

替代: UnifiedGrowthEvent 内存列表 → Postgres
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, func, select

from ..database import DatabaseManager
from ..models import GrowthEventRecord


class EventRepository:
    """事件仓库 — UnifiedGrowthEvent 的持久化 CRUD.

    用法:
        repo = EventRepository(db)
        repo.save(event_dict)
        events = repo.find_by_game("P04", event_type="ad_spend")
    """

    def __init__(self, db: DatabaseManager):
        self._db = db

    # ── Create ───────────────────────────────────────────────

    def save(self, event: dict[str, Any]) -> GrowthEventRecord:
        """保存一条增长事件."""
        record = GrowthEventRecord(
            event_id=event.get("event_id", ""),
            game_id=event.get("game_id", ""),
            source=event.get("source", "internal"),
            event_type=event.get("event_type", ""),
            timestamp=event.get("timestamp", datetime.now(timezone.utc).isoformat()),
            metrics=event.get("metrics", {}),
            campaign_id=event.get("campaign_id", ""),
            creative_id=event.get("creative_id", ""),
            platform=event.get("platform", ""),
            metadata_=event.get("metadata", {}),
        )
        with self._db.session() as session:
            session.add(record)
        return record

    def save_batch(self, events: list[dict[str, Any]]) -> list[GrowthEventRecord]:
        """批量保存事件."""
        records = []
        with self._db.session() as session:
            for event in events:
                record = GrowthEventRecord(
                    event_id=event.get("event_id", ""),
                    game_id=event.get("game_id", ""),
                    source=event.get("source", "internal"),
                    event_type=event.get("event_type", ""),
                    timestamp=event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    metrics=event.get("metrics", {}),
                    campaign_id=event.get("campaign_id", ""),
                    creative_id=event.get("creative_id", ""),
                    platform=event.get("platform", ""),
                    metadata_=event.get("metadata", {}),
                )
                session.add(record)
                records.append(record)
        return records

    # ── Read ─────────────────────────────────────────────────

    def get_by_id(self, event_id: str) -> GrowthEventRecord | None:
        with self._db.session() as session:
            return session.get(GrowthEventRecord, event_id)

    def find_by_game(
        self, game_id: str, limit: int = 50, offset: int = 0,
    ) -> list[GrowthEventRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(GrowthEventRecord)
                    .where(GrowthEventRecord.game_id == game_id)
                    .order_by(desc(GrowthEventRecord.timestamp))
                    .limit(limit)
                    .offset(offset)
                )
                .scalars()
                .all()
            )

    def find_by_type(
        self, event_type: str, limit: int = 50,
    ) -> list[GrowthEventRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(GrowthEventRecord)
                    .where(GrowthEventRecord.event_type == event_type)
                    .order_by(desc(GrowthEventRecord.timestamp))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    def find_by_game_and_type(
        self, game_id: str, event_type: str, limit: int = 50,
    ) -> list[GrowthEventRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(GrowthEventRecord)
                    .where(
                        GrowthEventRecord.game_id == game_id,
                        GrowthEventRecord.event_type == event_type,
                    )
                    .order_by(desc(GrowthEventRecord.timestamp))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    def find_by_source(
        self, source: str, limit: int = 50,
    ) -> list[GrowthEventRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(GrowthEventRecord)
                    .where(GrowthEventRecord.source == source)
                    .order_by(desc(GrowthEventRecord.timestamp))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    def find_by_campaign(
        self, campaign_id: str, limit: int = 50,
    ) -> list[GrowthEventRecord]:
        with self._db.session() as session:
            return (
                session.execute(
                    select(GrowthEventRecord)
                    .where(GrowthEventRecord.campaign_id == campaign_id)
                    .order_by(desc(GrowthEventRecord.timestamp))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    def find_by_time_range(
        self, start: str, end: str | None = None, limit: int = 100,
    ) -> list[GrowthEventRecord]:
        end = end or datetime.now(timezone.utc).isoformat()
        with self._db.session() as session:
            return (
                session.execute(
                    select(GrowthEventRecord)
                    .where(
                        GrowthEventRecord.timestamp >= start,
                        GrowthEventRecord.timestamp <= end,
                    )
                    .order_by(desc(GrowthEventRecord.timestamp))
                    .limit(limit)
                )
                .scalars()
                .all()
            )

    # ── Aggregation ──────────────────────────────────────────

    def aggregate_by_game(self, game_id: str) -> dict[str, Any]:
        """聚合游戏级别的指标."""
        with self._db.session() as session:
            result = session.execute(
                select(
                    func.count().label("event_count"),
                    func.coalesce(
                        func.sum(
                            func.cast(
                                GrowthEventRecord.metrics["spend"].as_string,
                                Float,
                            )
                        ),
                        0,
                    ).label("total_spend"),
                    func.coalesce(
                        func.sum(
                            func.cast(
                                GrowthEventRecord.metrics["revenue"].as_string,
                                Float,
                            )
                        ),
                        0,
                    ).label("total_revenue"),
                )
                .where(GrowthEventRecord.game_id == game_id)
            ).one_or_none()

            if result is None or result.event_count == 0:
                return {"game_id": game_id, "event_count": 0}

            total_spend = float(result.total_spend)
            total_revenue = float(result.total_revenue)
            return {
                "game_id": game_id,
                "event_count": result.event_count,
                "total_spend": round(total_spend, 2),
                "total_revenue": round(total_revenue, 2),
                "roas": round(total_revenue / total_spend, 4) if total_spend > 0 else 0.0,
            }

    # ── Delete ───────────────────────────────────────────────

    def delete(self, event_id: str) -> bool:
        with self._db.session() as session:
            record = session.get(GrowthEventRecord, event_id)
            if record:
                session.delete(record)
                return True
            return False

    def delete_by_game(self, game_id: str) -> int:
        with self._db.session() as session:
            result = session.execute(
                select(GrowthEventRecord).where(GrowthEventRecord.game_id == game_id)
            ).scalars().all()
            count = len(result)
            for r in result:
                session.delete(r)
            return count

    def count(self) -> int:
        with self._db.session() as session:
            return session.execute(
                select(func.count()).select_from(GrowthEventRecord)
            ).scalar() or 0