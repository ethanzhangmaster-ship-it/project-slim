from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class TestStatus(Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TestType(Enum):
    A_B = "a_b"
    MULTIVARIATE = "multivariate"
    FACTORIAL = "factorial"
    SEQUENTIAL = "sequential"


@dataclass
class TestVariant:
    variant_id: str
    name: str
    config: Dict[str, Any] = field(default_factory=dict)
    traffic_allocation: float = 50.0
    sample_size: int = 0
    conversions: int = 0
    revenue: float = 0.0
    metrics: Dict[str, float] = field(default_factory=dict)
    is_control: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "name": self.name,
            "config": self.config,
            "traffic_allocation": self.traffic_allocation,
            "sample_size": self.sample_size,
            "conversions": self.conversions,
            "revenue": self.revenue,
            "metrics": self.metrics,
            "is_control": self.is_control,
        }


@dataclass
class TestConfig:
    test_type: TestType
    primary_metric: str = "conversion_rate"
    secondary_metrics: List[str] = field(default_factory=list)
    confidence_level: float = 0.95
    min_sample_size: int = 1000
    max_duration_days: int = 30
    early_stopping: bool = True
    segments: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_type": self.test_type.value,
            "primary_metric": self.primary_metric,
            "secondary_metrics": self.secondary_metrics,
            "confidence_level": self.confidence_level,
            "min_sample_size": self.min_sample_size,
            "max_duration_days": self.max_duration_days,
            "early_stopping": self.early_stopping,
            "segments": self.segments,
        }


@dataclass
class TestResult:
    test_id: str
    variant_id: str
    primary_metric_value: float = 0.0
    secondary_metrics: Dict[str, float] = field(default_factory=dict)
    confidence_interval: List[float] = field(default_factory=list)
    lift_vs_control: float = 0.0
    p_value: float = 0.0
    statistical_significance: bool = False
    is_winner: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "variant_id": self.variant_id,
            "primary_metric_value": self.primary_metric_value,
            "secondary_metrics": self.secondary_metrics,
            "confidence_interval": self.confidence_interval,
            "lift_vs_control": self.lift_vs_control,
            "p_value": self.p_value,
            "statistical_significance": self.statistical_significance,
            "is_winner": self.is_winner,
        }


@dataclass
class ABTest:
    test_id: str
    name: str
    description: str = ""
    status: TestStatus = TestStatus.DRAFT
    config: Optional[TestConfig] = None
    variants: List[TestVariant] = field(default_factory=list)
    results: List[TestResult] = field(default_factory=list)
    winner: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "config": self.config.to_dict() if self.config else None,
            "variants": [v.to_dict() for v in self.variants],
            "results": [r.to_dict() for r in self.results],
            "winner": self.winner,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "created_at": self.created_at.isoformat(),
        }


class ABTestManager:
    def __init__(self):
        self._tests: Dict[str, ABTest] = {}
        self._archived_results: List[TestResult] = []

    def create_test(
        self,
        name: str,
        test_type: TestType,
        variants: List[Dict[str, Any]],
        primary_metric: str = "conversion_rate",
        min_sample_size: int = 1000
    ) -> ABTest:
        test_id = f"ab_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        test_variants = []

        for i, v in enumerate(variants):
            variant = TestVariant(
                variant_id=f"{test_id}_var_{i+1}",
                name=v.get("name", f"Variant {i+1}"),
                config=v.get("config", {}),
                traffic_allocation=v.get("traffic_allocation", 100.0 / len(variants)),
                is_control=v.get("is_control", i == 0),
            )
            test_variants.append(variant)

        config = TestConfig(
            test_type=test_type,
            primary_metric=primary_metric,
            min_sample_size=min_sample_size,
        )

        test = ABTest(
            test_id=test_id,
            name=name,
            config=config,
            variants=test_variants,
        )
        self._tests[test_id] = test
        return test

    def start_test(self, test_id: str) -> Optional[ABTest]:
        test = self._tests.get(test_id)
        if not test or test.status != TestStatus.DRAFT:
            return None
        test.status = TestStatus.RUNNING
        test.start_time = datetime.now()
        return test

    def pause_test(self, test_id: str) -> Optional[ABTest]:
        test = self._tests.get(test_id)
        if not test or test.status != TestStatus.RUNNING:
            return None
        test.status = TestStatus.PAUSED
        return test

    def complete_test(self, test_id: str) -> Optional[ABTest]:
        test = self._tests.get(test_id)
        if not test or test.status not in [TestStatus.RUNNING, TestStatus.PAUSED]:
            return None

        test.status = TestStatus.COMPLETED
        test.end_time = datetime.now()

        results = self._calculate_results(test)
        test.results = results
        test.winner = self._determine_winner(results)

        self._archived_results.extend(results)
        return test

    def _calculate_results(self, test: ABTest) -> List[TestResult]:
        results = []
        control = next((v for v in test.variants if v.is_control), test.variants[0] if test.variants else None)
        control_value = random.uniform(0.02, 0.08) if control else 0.05

        for variant in test.variants:
            primary_value = random.uniform(0.015, 0.12)
            confidence = random.uniform(0.85, 0.99)
            lift = ((primary_value - control_value) / control_value * 100) if control_value > 0 else 0

            result = TestResult(
                test_id=test.test_id,
                variant_id=variant.variant_id,
                primary_metric_value=primary_value,
                secondary_metrics={"retention": random.uniform(0.1, 0.4), "engagement": random.uniform(0.2, 0.6)},
                confidence_interval=[primary_value * 0.9, primary_value * 1.1],
                lift_vs_control=lift,
                p_value=random.uniform(0.01, 0.1),
                statistical_significance=confidence >= (test.config.confidence_level if test.config else 0.95),
            )
            results.append(result)
        return results

    def _determine_winner(self, results: List[TestResult]) -> Optional[str]:
        significant_results = [r for r in results if r.statistical_significance and r.lift_vs_control > 0]
        if significant_results:
            winner = max(significant_results, key=lambda r: r.primary_metric_value)
            winner.is_winner = True
            return winner.variant_id
        return None

    def update_variant_metrics(
        self,
        test_id: str,
        variant_id: str,
        sample_size: int,
        conversions: int,
        revenue: float = 0.0
    ) -> bool:
        test = self._tests.get(test_id)
        if not test or test.status != TestStatus.RUNNING:
            return False

        for variant in test.variants:
            if variant.variant_id == variant_id:
                variant.sample_size = sample_size
                variant.conversions = conversions
                variant.revenue = revenue
                variant.metrics["conversion_rate"] = conversions / max(1, sample_size)
                return True
        return False

    def get_test(self, test_id: str) -> Optional[ABTest]:
        return self._tests.get(test_id)

    def get_tests(self, status: TestStatus = None) -> List[ABTest]:
        tests = list(self._tests.values())
        if status:
            tests = [t for t in tests if t.status == status]
        return tests

    def get_running_tests(self) -> List[ABTest]:
        return [t for t in self._tests.values() if t.status == TestStatus.RUNNING]

    def get_archived_results(self) -> List[TestResult]:
        return list(self._archived_results)

    def get_stats(self) -> Dict[str, Any]:
        tests = list(self._tests.values())
        return {
            "total_tests": len(tests),
            "tests_by_status": {
                status.value: sum(1 for t in tests if t.status == status)
                for status in TestStatus
            },
            "tests_by_type": {
                type.value: sum(1 for t in tests if t.config and t.config.test_type == type)
                for type in TestType
            },
            "tests_with_winner": sum(1 for t in tests if t.winner),
            "total_archived_results": len(self._archived_results),
        }