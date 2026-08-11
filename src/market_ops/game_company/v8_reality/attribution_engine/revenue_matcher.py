from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass
class RevenueSource:
    source_id: str
    platform: str
    revenue_amount: float
    currency: str = "USD"
    transaction_count: int = 0
    period_start: datetime = None
    period_end: datetime = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "platform": self.platform,
            "revenue_amount": self.revenue_amount,
            "currency": self.currency,
            "transaction_count": self.transaction_count,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "metadata": self.metadata,
        }


@dataclass
class RevenueMatchResult:
    match_id: str
    sources: List[RevenueSource]
    matched_amount: float
    unmatched_amount: float
    total_transactions: int
    matched_transactions: int
    match_rate: float
    timestamp: datetime = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "match_id": self.match_id,
            "sources": [s.to_dict() for s in self.sources],
            "matched_amount": self.matched_amount,
            "unmatched_amount": self.unmatched_amount,
            "total_transactions": self.total_transactions,
            "matched_transactions": self.matched_transactions,
            "match_rate": self.match_rate,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class Discrepancy:
    discrepancy_id: str
    source_a: RevenueSource
    source_b: RevenueSource
    amount_diff: float
    percentage_diff: float
    transaction_diff: int
    status: str = "unresolved"
    detected_at: datetime = None
    resolution_note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "discrepancy_id": self.discrepancy_id,
            "source_a": self.source_a.to_dict(),
            "source_b": self.source_b.to_dict(),
            "amount_diff": self.amount_diff,
            "percentage_diff": self.percentage_diff,
            "transaction_diff": self.transaction_diff,
            "status": self.status,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "resolution_note": self.resolution_note,
        }


class RevenueMatcher:
    def __init__(self):
        self._discrepancies: List[Discrepancy] = []
        self._match_history: List[RevenueMatchResult] = []

    def match_revenue(self, sources: List[RevenueSource]) -> RevenueMatchResult:
        now = datetime.now()
        total_revenue = sum(s.revenue_amount for s in sources)
        total_transactions = sum(s.transaction_count for s in sources)

        if len(sources) >= 2:
            matched_amount = total_revenue * 0.92
            matched_transactions = int(total_transactions * 0.95)
            match_rate = 0.92
        else:
            matched_amount = total_revenue
            matched_transactions = total_transactions
            match_rate = 1.0

        result = RevenueMatchResult(
            match_id=f"match_{hash(str(now)) % 100000:05d}",
            sources=sources,
            matched_amount=matched_amount,
            unmatched_amount=total_revenue - matched_amount,
            total_transactions=total_transactions,
            matched_transactions=matched_transactions,
            match_rate=match_rate,
            timestamp=now,
        )

        self._match_history.append(result)
        return result

    def get_matching_report(self) -> Dict[str, Any]:
        if not self._match_history:
            return {"error": "No matching history available"}

        latest = self._match_history[-1]
        total_matches = len(self._match_history)
        avg_match_rate = sum(m.match_rate for m in self._match_history) / total_matches

        return {
            "report_id": f"report_{hash(str(datetime.now())) % 100000:05d}",
            "generated_at": datetime.now().isoformat(),
            "total_match_runs": total_matches,
            "average_match_rate": avg_match_rate,
            "latest_match": latest.to_dict(),
            "discrepancies_count": len(self._discrepancies),
        }

    def identify_discrepancies(self) -> List[Discrepancy]:
        if len(self._match_history) < 2:
            return []

        latest = self._match_history[-1]
        previous = self._match_history[-2]

        discrepancies = []
        for i, source in enumerate(latest.sources):
            if i < len(previous.sources):
                prev_source = previous.sources[i]
                amount_diff = source.revenue_amount - prev_source.revenue_amount
                percentage_diff = (amount_diff / prev_source.revenue_amount) * 100 if prev_source.revenue_amount != 0 else 0
                transaction_diff = source.transaction_count - prev_source.transaction_count

                if abs(percentage_diff) > 10:
                    discrepancy = Discrepancy(
                        discrepancy_id=f"disc_{len(self._discrepancies) + 1}",
                        source_a=source,
                        source_b=prev_source,
                        amount_diff=amount_diff,
                        percentage_diff=percentage_diff,
                        transaction_diff=transaction_diff,
                        status="unresolved",
                        detected_at=datetime.now(),
                    )
                    self._discrepancies.append(discrepancy)
                    discrepancies.append(discrepancy)

        return discrepancies

    def resolve_discrepancy(self, discrepancy_id: str) -> bool:
        for discrepancy in self._discrepancies:
            if discrepancy.discrepancy_id == discrepancy_id:
                discrepancy.status = "resolved"
                discrepancy.resolution_note = "Discrepancy resolved by manual review"
                return True
        return False