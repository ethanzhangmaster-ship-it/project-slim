from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import random


@dataclass
class BidRecommendation:
    recommendation_id: str
    campaign_id: str
    current_bid: float
    recommended_bid: float
    change_percent: float = 0.0
    reason: str = ""
    confidence: float = 0.0
    expected_impact: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "campaign_id": self.campaign_id,
            "current_bid": self.current_bid,
            "recommended_bid": self.recommended_bid,
            "change_percent": self.change_percent,
            "reason": self.reason,
            "confidence": self.confidence,
            "expected_impact": self.expected_impact,
        }


@dataclass
class BidTest:
    test_id: str
    campaign_id: str
    original_bid: float
    test_bid: float
    status: str = "pending"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    results: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "campaign_id": self.campaign_id,
            "original_bid": self.original_bid,
            "test_bid": self.test_bid,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "results": self.results,
        }


@dataclass
class BidResult:
    test_id: str
    campaign_id: str
    original_bid: float
    test_bid: float
    original_performance: Dict[str, float] = field(default_factory=dict)
    test_performance: Dict[str, float] = field(default_factory=dict)
    winner: str = "original"
    improvement: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "campaign_id": self.campaign_id,
            "original_bid": self.original_bid,
            "test_bid": self.test_bid,
            "original_performance": self.original_performance,
            "test_performance": self.test_performance,
            "winner": self.winner,
            "improvement": self.improvement,
        }


class BidOptimizer:
    def __init__(self):
        self._bids: Dict[str, float] = {}
        self._tests: Dict[str, BidTest] = {}
        self._results: List[BidResult] = []

    def set_bid(self, campaign_id: str, bid: float):
        self._bids[campaign_id] = bid

    def get_bid(self, campaign_id: str) -> Optional[float]:
        return self._bids.get(campaign_id)

    def optimize_bid(self, campaign_id: str) -> BidRecommendation:
        current_bid = self._bids.get(campaign_id, random.uniform(1.0, 10.0))
        change_percent = random.uniform(-0.3, 0.3)
        recommended_bid = current_bid * (1 + change_percent)

        rec_id = f"bid_rec_{campaign_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        return BidRecommendation(
            recommendation_id=rec_id,
            campaign_id=campaign_id,
            current_bid=current_bid,
            recommended_bid=recommended_bid,
            change_percent=change_percent * 100,
            reason="Performance-based optimization",
            confidence=random.uniform(0.6, 0.9),
            expected_impact=abs(change_percent) * 100,
        )

    def get_bid_recommendations(self, campaign_id: str = None) -> List[BidRecommendation]:
        if campaign_id:
            return [self.optimize_bid(campaign_id)]
        return [self.optimize_bid(cid) for cid in self._bids]

    def adjust_bid(self, campaign_id: str, new_bid: float) -> Dict[str, Any]:
        old_bid = self._bids.get(campaign_id, 0)
        self._bids[campaign_id] = new_bid
        return {
            "campaign_id": campaign_id,
            "old_bid": old_bid,
            "new_bid": new_bid,
            "change_percent": ((new_bid - old_bid) / old_bid * 100) if old_bid > 0 else 0,
            "timestamp": datetime.now().isoformat(),
        }

    def test_bid(self, campaign_id: str, test_bid: float) -> BidTest:
        test_id = f"test_{campaign_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        test = BidTest(
            test_id=test_id,
            campaign_id=campaign_id,
            original_bid=self._bids.get(campaign_id, 0),
            test_bid=test_bid,
            status="running",
            start_time=datetime.now(),
        )
        self._tests[test_id] = test
        return test

    def conclude_test(self, test_id: str) -> Optional[BidResult]:
        test = self._tests.get(test_id)
        if not test:
            return None

        test.status = "completed"
        test.end_time = datetime.now()

        original_perf = {"roas": random.uniform(0.8, 2.0), "ctr": random.uniform(0.01, 0.05)}
        test_perf = {"roas": random.uniform(0.8, 2.0), "ctr": random.uniform(0.01, 0.05)}

        winner = "test" if test_perf["roas"] > original_perf["roas"] else "original"
        improvement = (test_perf["roas"] - original_perf["roas"]) / original_perf["roas"] * 100

        result = BidResult(
            test_id=test_id,
            campaign_id=test.campaign_id,
            original_bid=test.original_bid,
            test_bid=test.test_bid,
            original_performance=original_perf,
            test_performance=test_perf,
            winner=winner,
            improvement=improvement,
        )
        self._results.append(result)
        return result

    def get_test(self, test_id: str) -> Optional[BidTest]:
        return self._tests.get(test_id)

    def get_tests(self, campaign_id: str = None) -> List[BidTest]:
        if campaign_id:
            return [t for t in self._tests.values() if t.campaign_id == campaign_id]
        return list(self._tests.values())

    def get_results(self, limit: int = 50) -> List[BidResult]:
        return self._results[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        total_tests = len(self._tests)
        completed = sum(1 for t in self._tests.values() if t.status == "completed")
        return {
            "total_campaigns": len(self._bids),
            "total_tests": total_tests,
            "completed_tests": completed,
            "total_results": len(self._results),
        }