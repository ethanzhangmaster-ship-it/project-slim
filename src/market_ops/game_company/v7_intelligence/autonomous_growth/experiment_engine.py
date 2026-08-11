from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import random


@dataclass
class Experiment:
    experiment_id: str
    hypothesis: str
    status: str
    variants: List[str]
    metric: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    sample_size: int = 1000
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ExperimentResult:
    experiment_id: str
    variant_results: Dict[str, Any]
    winner: Optional[str] = None
    confidence_level: float = 0.95
    is_significant: bool = False
    concluded_at: Optional[datetime] = None


class ExperimentEngine:
    """实验引擎，负责创建、运行和总结 A/B 实验。"""

    def __init__(self):
        self.experiments: Dict[str, Experiment] = {}
        self.results: Dict[str, ExperimentResult] = {}
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"exp_{datetime.now().strftime('%Y%m%d')}_{self._counter:04d}"

    def create_experiment(self, hypothesis: str, variants: Optional[List[str]] = None, metric: str = "conversion") -> Experiment:
        """创建新实验。"""
        exp_id = self._next_id()
        experiment = Experiment(
            experiment_id=exp_id,
            hypothesis=hypothesis,
            status="created",
            variants=variants or ["control", "treatment"],
            metric=metric,
        )
        self.experiments[exp_id] = experiment
        return experiment

    def run_experiment(self, exp_id: str) -> Experiment:
        """启动实验并模拟运行。"""
        if exp_id not in self.experiments:
            raise ValueError(f"Experiment {exp_id} not found")
        exp = self.experiments[exp_id]
        exp.status = "running"
        exp.start_date = datetime.now()
        return exp

    def get_results(self, exp_id: str) -> ExperimentResult:
        """获取实验结果（模拟数据）。"""
        if exp_id not in self.experiments:
            raise ValueError(f"Experiment {exp_id} not found")

        exp = self.experiments[exp_id]
        variant_results = {}
        for variant in exp.variants:
            base = random.uniform(0.02, 0.08)
            variant_results[variant] = {
                "sample_size": exp.sample_size,
                "metric_value": round(base + random.uniform(-0.01, 0.02), 4),
                "conversion_rate": round(base, 4),
                "improvement_pct": round(random.uniform(-10, 20), 2),
            }

        winner = max(variant_results, key=lambda v: variant_results[v]["metric_value"])
        is_significant = variant_results[winner]["improvement_pct"] > 5.0

        result = ExperimentResult(
            experiment_id=exp_id,
            variant_results=variant_results,
            winner=winner if is_significant else None,
            confidence_level=0.95,
            is_significant=is_significant,
        )
        self.results[exp_id] = result
        return result

    def conclude_experiment(self, exp_id: str) -> ExperimentResult:
        """结束实验并返回最终结论。"""
        if exp_id not in self.experiments:
            raise ValueError(f"Experiment {exp_id} not found")

        exp = self.experiments[exp_id]
        exp.status = "concluded"
        exp.end_date = datetime.now()

        if exp_id not in self.results:
            self.get_results(exp_id)

        result = self.results[exp_id]
        result.concluded_at = datetime.now()
        return result
