"""V4.2 Online Feedback — ingest Facebook performance data.

Supports daily, weekly, monthly feedback ingestion.
Auto-updates Learning Loop with new performance data.

Usage:
    feedback = OnlineFeedback(learning_loop=learning_loop)
    feedback.ingest_daily(new_performance_data)
"""

from __future__ import annotations

from typing import Any

from .schemas import FeedbackRecord


class OnlineFeedback:
    """Ingest real Facebook performance data into the Learning Loop.

    Supports:
      - Daily feedback ingestion
      - Weekly aggregation
      - Monthly trend analysis
    """

    def __init__(self, learning_loop=None) -> None:
        self._learning_loop = learning_loop
        self._feedback_history: list[FeedbackRecord] = []
        self._daily_buffer: list[FeedbackRecord] = []
        self._weekly_buffer: list[FeedbackRecord] = []
        self._monthly_buffer: list[FeedbackRecord] = []

    def ingest_daily(self, feedback_data: list[dict[str, Any]]) -> list[FeedbackRecord]:
        """Ingest daily feedback data from Facebook.

        Args:
            feedback_data: List of dicts with creative_id, ctr, ipm, roas, etc.

        Returns:
            List of parsed FeedbackRecords.
        """
        records = []
        for item in feedback_data:
            record = FeedbackRecord(
                creative_id=item.get("creative_id", ""),
                date=item.get("date", ""),
                ctr=item.get("ctr", 0),
                ipm=item.get("ipm", 0),
                roas_d7=item.get("roas_d7", 0),
                roas_d30=item.get("roas_d30", 0),
                ltv=item.get("ltv", 0),
                spend=item.get("spend", 0),
                retention_d1=item.get("retention_d1", 0),
                retention_d7=item.get("retention_d7", 0),
                predicted_decision=item.get("predicted_decision", ""),
                actual_performance=item.get("roas_d7", 0),
            )
            records.append(record)

        self._daily_buffer.extend(records)
        self._feedback_history.extend(records)

        # Update learning loop
        if self._learning_loop:
            self._update_learning_loop(records)

        return records

    def ingest_weekly(self):
        """Aggregate daily feedback into weekly summary."""
        if not self._daily_buffer:
            return

        self._weekly_buffer.extend(self._daily_buffer)
        self._daily_buffer = []

    def ingest_monthly(self):
        """Aggregate weekly feedback into monthly summary."""
        if not self._weekly_buffer:
            return

        self._monthly_buffer.extend(self._weekly_buffer)
        self._weekly_buffer = []

    def get_feedback_since(self, since_date: str) -> list[FeedbackRecord]:
        """Get all feedback records since a given date."""
        return [r for r in self._feedback_history if r.date >= since_date]

    def get_performance_summary(self, creative_id: str) -> dict[str, Any]:
        """Get performance summary for a specific creative."""
        records = [r for r in self._feedback_history
                   if r.creative_id == creative_id]
        if not records:
            return {}

        n = len(records)
        return {
            "creative_id": creative_id,
            "days_active": n,
            "avg_ctr": sum(r.ctr for r in records) / n,
            "avg_ipm": sum(r.ipm for r in records) / n,
            "avg_roas_d7": sum(r.roas_d7 for r in records) / n,
            "avg_roas_d30": sum(r.roas_d30 for r in records) / n,
            "total_spend": sum(r.spend for r in records),
            "avg_ltv": sum(r.ltv for r in records) / n,
            "avg_retention_d1": sum(r.retention_d1 for r in records) / n,
            "avg_retention_d7": sum(r.retention_d7 for r in records) / n,
        }

    def _update_learning_loop(self, records: list[FeedbackRecord]) -> None:
        """Update the learning loop with new feedback."""
        try:
            for r in records:
                self._learning_loop.ingest(
                    creative_id=r.creative_id,
                    performance={"roas_d7": r.roas_d7, "ctr": r.ctr},
                    is_winner=r.roas_d7 >= 0.5,
                )
        except Exception:
            pass

    @property
    def history(self) -> list[FeedbackRecord]:
        return self._feedback_history

    @property
    def daily_count(self) -> int:
        return len(self._daily_buffer)

    @property
    def weekly_count(self) -> int:
        return len(self._weekly_buffer)

    @property
    def monthly_count(self) -> int:
        return len(self._monthly_buffer)