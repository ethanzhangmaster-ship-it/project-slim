from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class TestStatus(Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TestType(Enum):
    A_B = "a_b"
    MULTIVARIATE = "multivariate"
    CHAMPION_CHALLENGER = "champion_challenger"
    SEQUENTIAL = "sequential"


@dataclass
class TestVariant:
    variant_id: str
    name: str
    creative_id: str
    traffic_allocation: float = 0.0
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    spend: float = 0.0
    revenue: float = 0.0
    is_control: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "name": self.name,
            "creative_id": self.creative_id,
            "traffic_allocation": self.traffic_allocation,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "conversions": self.conversions,
            "spend": self.spend,
            "revenue": self.revenue,
            "is_control": self.is_control,
        }


@dataclass
class TestConfig:
    test_type: TestType
    variants: List[TestVariant]
    duration_days: int = 7
    traffic_split: Dict[str, float] = field(default_factory=dict)
    success_metric: str = "roas"
    confidence_level: float = 0.95
    min_sample_size: int = 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_type": self.test_type.value,
            "variants": [v.to_dict() for v in self.variants],
            "duration_days": self.duration_days,
            "traffic_split": self.traffic_split,
            "success_metric": self.success_metric,
            "confidence_level": self.confidence_level,
            "min_sample_size": self.min_sample_size,
        }


@dataclass
class TestResult:
    test_id: str
    variant_id: str
    metric: str
    value: float
    confidence: float
    is_winner: bool = False
    lift_vs_control: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "variant_id": self.variant_id,
            "metric": self.metric,
            "value": self.value,
            "confidence": self.confidence,
            "is_winner": self.is_winner,
            "lift_vs_control": self.lift_vs_control,
        }


@dataclass
class CreativeTest:
    test_id: str
    name: str
    status: TestStatus = TestStatus.DRAFT
    config: Optional[TestConfig] = None
    results: List[TestResult] = field(default_factory=list)
    winner: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "name": self.name,
            "status": self.status.value,
            "config": self.config.to_dict() if self.config else None,
            "results": [r.to_dict() for r in self.results],
            "winner": self.winner,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "created_at": self.created_at.isoformat(),
        }


class CreativeTestManager:
    def __init__(self):
        self._tests: Dict[str, CreativeTest] = {}
        self._variant_results: Dict[str, Dict[str, Any]] = {}

    def create_test(
        self,
        name: str,
        test_type: TestType,
        variants: List[Dict[str, Any]],
        duration_days: int = 7,
        success_metric: str = "roas"
    ) -> CreativeTest:
        test_id = f"test_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"

        test_variants = []
        for i, v in enumerate(variants):
            variant = TestVariant(
                variant_id=f"{test_id}_var_{i+1}",
                name=v.get("name", f"Variant {i+1}"),
                creative_id=v.get("creative_id", ""),
                traffic_allocation=v.get("traffic_allocation", 1.0 / len(variants)),
                is_control=v.get("is_control", i == 0),
            )
            test_variants.append(variant)

        traffic_split = {v.variant_id: v.traffic_allocation for v in test_variants}

        config = TestConfig(
            test_type=test_type,
            variants=test_variants,
            duration_days=duration_days,
            traffic_split=traffic_split,
            success_metric=success_metric,
        )

        test = CreativeTest(
            test_id=test_id,
            name=name,
            status=TestStatus.DRAFT,
            config=config,
        )
        self._tests[test_id] = test
        return test

    def start_test(self, test_id: str) -> Optional[CreativeTest]:
        test = self._tests.get(test_id)
        if not test or test.status not in [TestStatus.DRAFT, TestStatus.PAUSED, TestStatus.SCHEDULED]:
            return None

        test.status = TestStatus.RUNNING
        test.start_time = datetime.now()
        return test

    def pause_test(self, test_id: str) -> Optional[CreativeTest]:
        test = self._tests.get(test_id)
        if not test or test.status != TestStatus.RUNNING:
            return None

        test.status = TestStatus.PAUSED
        return test

    def complete_test(self, test_id: str) -> Optional[CreativeTest]:
        test = self._tests.get(test_id)
        if not test or test.status != TestStatus.RUNNING:
            return None

        test.status = TestStatus.COMPLETED
        test.end_time = datetime.now()
        results = self._calculate_results(test)
        test.results = results
        test.winner = self._determine_winner(results)
        return test

    def _calculate_results(self, test: CreativeTest) -> List[TestResult]:
        results = []
        if not test.config:
            return results

        control = next((v for v in test.config.variants if v.is_control), test.config.variants[0] if test.config.variants else None)
        control_value = random.uniform(1.0, 2.0) if control else 1.0

        for variant in test.config.variants:
            value = random.uniform(0.8, 2.5)
            confidence = random.uniform(0.85, 0.99)
            lift = ((value - control_value) / control_value * 100) if control_value > 0 else 0

            result = TestResult(
                test_id=test.test_id,
                variant_id=variant.variant_id,
                metric=test.config.success_metric,
                value=value,
                confidence=confidence,
                lift_vs_control=lift,
            )
            results.append(result)

        return results

    def _determine_winner(self, results: List[TestResult]) -> Optional[str]:
        if not results:
            return None

        valid_results = [r for r in results if r.confidence >= 0.95]
        if not valid_results:
            return None

        winner = max(valid_results, key=lambda r: r.value)
        winner.is_winner = True
        return winner.variant_id

    def get_test_results(self, test_id: str) -> Optional[Dict[str, Any]]:
        test = self._tests.get(test_id)
        if not test:
            return None

        return {
            "test": test.to_dict(),
            "summary": self._generate_summary(test),
        }

    def _generate_summary(self, test: CreativeTest) -> Dict[str, Any]:
        if not test.results:
            return {
                "status": test.status.value,
                "message": "No results available yet",
            }

        control_result = next((r for r in test.results if r.lift_vs_control == 0), None)
        winner_result = next((r for r in test.results if r.is_winner), None)

        return {
            "status": test.status.value,
            "winner": winner_result.variant_id if winner_result else None,
            "winner_metric_value": winner_result.value if winner_result else None,
            "winner_confidence": winner_result.confidence if winner_result else None,
            "total_variants": len(test.results),
            "test_duration_days": test.config.duration_days if test.config else 7,
        }

    def update_variant_performance(
        self,
        test_id: str,
        variant_id: str,
        impressions: int,
        clicks: int,
        conversions: int,
        spend: float,
        revenue: float
    ) -> bool:
        test = self._tests.get(test_id)
        if not test or test.status != TestStatus.RUNNING:
            return False

        if test.config:
            for variant in test.config.variants:
                if variant.variant_id == variant_id:
                    variant.impressions += impressions
                    variant.clicks += clicks
                    variant.conversions += conversions
                    variant.spend += spend
                    variant.revenue += revenue
                    return True
        return False

    def get_test(self, test_id: str) -> Optional[CreativeTest]:
        return self._tests.get(test_id)

    def get_all_tests(self, status: TestStatus = None) -> List[CreativeTest]:
        tests = list(self._tests.values())
        if status:
            tests = [t for t in tests if t.status == status]
        return tests

    def get_running_tests(self) -> List[CreativeTest]:
        return [t for t in self._tests.values() if t.status == TestStatus.RUNNING]

    def cancel_test(self, test_id: str) -> Optional[CreativeTest]:
        test = self._tests.get(test_id)
        if not test or test.status in [TestStatus.COMPLETED, TestStatus.CANCELLED]:
            return None

        test.status = TestStatus.CANCELLED
        test.end_time = datetime.now()
        return test

    def get_stats(self) -> Dict[str, Any]:
        tests = list(self._tests.values())
        return {
            "total_tests": len(tests),
            "tests_by_status": {
                status.value: sum(1 for t in tests if t.status == status)
                for status in TestStatus
            },
            "tests_with_winner": sum(1 for t in tests if t.winner),
            "average_test_duration": sum(
                (t.end_time - t.start_time).days
                for t in tests
                if t.start_time and t.end_time
            ) / max(1, sum(1 for t in tests if t.start_time and t.end_time)),
        }