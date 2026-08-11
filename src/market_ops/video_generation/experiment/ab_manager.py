"""AB Manager"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class Experiment:
    experiment_id: str = ""
    blueprint_id: str = ""
    variants: List[str] = field(default_factory=list)
    status: str = "running"
    winner: Optional[str] = None
    metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    created_at: str = ""
    completed_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ABManager:
    """A/B 测试管理器"""

    def __init__(self, experiment_dir: str = None):
        if experiment_dir is None:
            experiment_dir = Path(__file__).resolve().parent / "experiments"
        self.experiment_dir = Path(experiment_dir)
        self.experiment_dir.mkdir(parents=True, exist_ok=True)
        self._experiments: Dict[str, Experiment] = {}
        self._load_experiments()

    def _load_experiments(self):
        for exp_file in self.experiment_dir.glob("*.json"):
            with open(exp_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            exp = Experiment(**data)
            self._experiments[exp.experiment_id] = exp

    def _save_experiment(self, experiment: Experiment):
        exp_path = self.experiment_dir / f"{experiment.experiment_id}.json"
        with open(exp_path, "w", encoding="utf-8") as f:
            json.dump(experiment.to_dict(), f, indent=2, ensure_ascii=False)

    def create_experiment(self, blueprint_id: str, variants: List[str]) -> Experiment:
        experiment_id = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        experiment = Experiment(
            experiment_id=experiment_id,
            blueprint_id=blueprint_id,
            variants=variants,
        )
        self._experiments[experiment_id] = experiment
        self._save_experiment(experiment)
        return experiment

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        return self._experiments.get(experiment_id)

    def record_metrics(self, experiment_id: str, variant_id: str, metrics: Dict[str, Any]):
        if experiment_id not in self._experiments:
            return
        experiment = self._experiments[experiment_id]
        if variant_id not in experiment.metrics:
            experiment.metrics[variant_id] = {}
        experiment.metrics[variant_id].update(metrics)

    def determine_winner(self, experiment_id: str) -> Optional[str]:
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            return None

        best_variant = None
        best_ctr = 0.0
        for variant_id, metrics in experiment.metrics.items():
            ctr = metrics.get("ctr", 0.0)
            if ctr > best_ctr:
                best_ctr = ctr
                best_variant = variant_id

        if best_variant:
            experiment.winner = best_variant
            experiment.status = "completed"
            experiment.completed_at = datetime.now().isoformat()
            self._save_experiment(experiment)

        return best_variant

    def get_experiment_stats(self, experiment_id: str) -> Dict[str, Any]:
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            return {}

        stats = {"experiment_id": experiment_id, "variants": {}}
        for variant_id, metrics in experiment.metrics.items():
            stats["variants"][variant_id] = {
                "ctr": metrics.get("ctr", 0.0),
                "views": metrics.get("views", 0),
                "conversions": metrics.get("conversions", 0),
                "is_winner": variant_id == experiment.winner,
            }
        return stats

    def list_experiments(self, status: str = None) -> List[Experiment]:
        experiments = list(self._experiments.values())
        if status:
            experiments = [e for e in experiments if e.status == status]
        return experiments

    def get_stats(self) -> Dict[str, Any]:
        experiments = list(self._experiments.values())
        return {
            "total_experiments": len(experiments),
            "running": sum(1 for e in experiments if e.status == "running"),
            "completed": sum(1 for e in experiments if e.status == "completed"),
        }
