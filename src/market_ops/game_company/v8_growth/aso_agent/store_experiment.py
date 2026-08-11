from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
import random


class ExperimentStatus(Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ExperimentType(Enum):
    A_B = "a_b"
    MULTIVARIATE = "multivariate"
    BEFORE_AFTER = "before_after"
    GEO_TARGETED = "geo_targeted"


class MetricType(Enum):
    INSTALLS = "installs"
    RATING = "rating"
    CONVERSION_RATE = "conversion_rate"
    RETENTION = "retention"
    ENGAGEMENT = "engagement"


@dataclass
class ExperimentVariant:
    variant_id: str
    name: str
    metadata_changes: Dict[str, Any] = field(default_factory=dict)
    traffic_allocation: float = 50.0
    impressions: int = 0
    installs: int = 0
    page_views: int = 0
    conversion_rate: float = 0.0
    rating_change: float = 0.0
    is_control: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "name": self.name,
            "metadata_changes": self.metadata_changes,
            "traffic_allocation": self.traffic_allocation,
            "impressions": self.impressions,
            "installs": self.installs,
            "page_views": self.page_views,
            "conversion_rate": self.conversion_rate,
            "rating_change": self.rating_change,
            "is_control": self.is_control,
        }


@dataclass
class ExperimentResult:
    experiment_id: str
    variant_id: str
    metric_type: MetricType
    value: float
    confidence: float
    lift_vs_control: float = 0.0
    is_winner: bool = False
    statistical_significance: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "variant_id": self.variant_id,
            "metric_type": self.metric_type.value,
            "value": self.value,
            "confidence": self.confidence,
            "lift_vs_control": self.lift_vs_control,
            "is_winner": self.is_winner,
            "statistical_significance": self.statistical_significance,
        }


@dataclass
class StoreExperiment:
    experiment_id: str
    name: str
    type: ExperimentType
    status: ExperimentStatus = ExperimentStatus.DRAFT
    variants: List[ExperimentVariant] = field(default_factory=list)
    primary_metric: MetricType = MetricType.INSTALLS
    secondary_metrics: List[MetricType] = field(default_factory=list)
    duration_days: int = 14
    min_sample_size: int = 5000
    confidence_level: float = 0.95
    results: List[ExperimentResult] = field(default_factory=list)
    winner: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "type": self.type.value,
            "status": self.status.value,
            "variants": [v.to_dict() for v in self.variants],
            "primary_metric": self.primary_metric.value,
            "secondary_metrics": [m.value for m in self.secondary_metrics],
            "duration_days": self.duration_days,
            "min_sample_size": self.min_sample_size,
            "confidence_level": self.confidence_level,
            "results": [r.to_dict() for r in self.results],
            "winner": self.winner,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "created_at": self.created_at.isoformat(),
        }


class StoreExperimentManager:
    def __init__(self):
        self._experiments: Dict[str, StoreExperiment] = {}
        self._historical_results: List[ExperimentResult] = []

    def create_experiment(
        self,
        name: str,
        type: ExperimentType,
        variants: List[Dict[str, Any]],
        primary_metric: MetricType = MetricType.INSTALLS,
        duration_days: int = 14
    ) -> StoreExperiment:
        experiment_id = f"exp_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        exp_variants = []
        for i, v in enumerate(variants):
            variant = ExperimentVariant(
                variant_id=f"{experiment_id}_var_{i+1}",
                name=v.get("name", f"Variant {i+1}"),
                metadata_changes=v.get("metadata_changes", {}),
                traffic_allocation=v.get("traffic_allocation", 100.0 / len(variants)),
                is_control=v.get("is_control", i == 0),
            )
            exp_variants.append(variant)

        experiment = StoreExperiment(
            experiment_id=experiment_id,
            name=name,
            type=type,
            status=ExperimentStatus.DRAFT,
            variants=exp_variants,
            primary_metric=primary_metric,
            duration_days=duration_days,
        )
        self._experiments[experiment_id] = experiment
        return experiment

    def start_experiment(self, experiment_id: str) -> Optional[StoreExperiment]:
        experiment = self._experiments.get(experiment_id)
        if not experiment or experiment.status != ExperimentStatus.DRAFT:
            return None

        experiment.status = ExperimentStatus.RUNNING
        experiment.start_time = datetime.now()
        return experiment

    def pause_experiment(self, experiment_id: str) -> Optional[StoreExperiment]:
        experiment = self._experiments.get(experiment_id)
        if not experiment or experiment.status != ExperimentStatus.RUNNING:
            return None

        experiment.status = ExperimentStatus.PAUSED
        return experiment

    def complete_experiment(self, experiment_id: str) -> Optional[StoreExperiment]:
        experiment = self._experiments.get(experiment_id)
        if not experiment or experiment.status != ExperimentStatus.RUNNING:
            return None

        experiment.status = ExperimentStatus.COMPLETED
        experiment.end_time = datetime.now()

        results = self._calculate_results(experiment)
        experiment.results = results
        experiment.winner = self._determine_winner(results)

        self._historical_results.extend(results)
        return experiment

    def _calculate_results(self, experiment: StoreExperiment) -> List[ExperimentResult]:
        results = []
        control = next((v for v in experiment.variants if v.is_control), experiment.variants[0] if experiment.variants else None)
        control_value = random.uniform(0.02, 0.06) if control else 0.03

        for variant in experiment.variants:
            value = random.uniform(0.015, 0.08)
            confidence = random.uniform(0.85, 0.99)
            lift = ((value - control_value) / control_value * 100) if control_value > 0 else 0
            is_significant = confidence >= experiment.confidence_level

            result = ExperimentResult(
                experiment_id=experiment.experiment_id,
                variant_id=variant.variant_id,
                metric_type=experiment.primary_metric,
                value=value,
                confidence=confidence,
                lift_vs_control=lift,
                statistical_significance=is_significant,
            )
            results.append(result)

        return results

    def _determine_winner(self, results: List[ExperimentResult]) -> Optional[str]:
        significant_results = [r for r in results if r.statistical_significance]
        if not significant_results:
            return None

        control_result = next((r for r in results if r.lift_vs_control == 0), None)
        better_results = [r for r in significant_results if r.lift_vs_control > 0]

        if better_results:
            winner = max(better_results, key=lambda r: r.value)
            winner.is_winner = True
            return winner.variant_id
        return None

    def update_variant_data(
        self,
        experiment_id: str,
        variant_id: str,
        impressions: int,
        installs: int,
        page_views: int
    ) -> bool:
        experiment = self._experiments.get(experiment_id)
        if not experiment or experiment.status != ExperimentStatus.RUNNING:
            return False

        for variant in experiment.variants:
            if variant.variant_id == variant_id:
                variant.impressions += impressions
                variant.installs += installs
                variant.page_views += page_views
                variant.conversion_rate = variant.installs / max(1, variant.page_views)
                return True
        return False

    def get_experiment(self, experiment_id: str) -> Optional[StoreExperiment]:
        return self._experiments.get(experiment_id)

    def get_experiments(self, status: ExperimentStatus = None) -> List[StoreExperiment]:
        experiments = list(self._experiments.values())
        if status:
            experiments = [e for e in experiments if e.status == status]
        return experiments

    def get_running_experiments(self) -> List[StoreExperiment]:
        return [e for e in self._experiments.values() if e.status == ExperimentStatus.RUNNING]

    def get_historical_results(self) -> List[ExperimentResult]:
        return list(self._historical_results)

    def cancel_experiment(self, experiment_id: str) -> Optional[StoreExperiment]:
        experiment = self._experiments.get(experiment_id)
        if not experiment or experiment.status in [ExperimentStatus.COMPLETED, ExperimentStatus.CANCELLED]:
            return None

        experiment.status = ExperimentStatus.CANCELLED
        experiment.end_time = datetime.now()
        return experiment

    def get_stats(self) -> Dict[str, Any]:
        experiments = list(self._experiments.values())
        return {
            "total_experiments": len(experiments),
            "experiments_by_status": {
                status.value: sum(1 for e in experiments if e.status == status)
                for status in ExperimentStatus
            },
            "experiments_by_type": {
                type.value: sum(1 for e in experiments if e.type == type)
                for type in ExperimentType
            },
            "experiments_with_winner": sum(1 for e in experiments if e.winner),
            "average_duration_days": sum(e.duration_days for e in experiments) / len(experiments) if experiments else 0,
            "total_historical_results": len(self._historical_results),
        }