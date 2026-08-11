from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class StrategyStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"
    ARCHIVED = "archived"


class UpdateType(Enum):
    PARAMETER = "parameter"
    RULE = "rule"
    MODEL = "model"
    CONFIG = "config"
    ROLLBACK = "rollback"


@dataclass
class StrategyEvaluation:
    strategy_id: str
    evaluation_id: str
    performance_score: float
    roi: float
    risk_score: float
    compliance_status: bool
    metrics: Dict[str, float] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "evaluation_id": self.evaluation_id,
            "performance_score": self.performance_score,
            "roi": self.roi,
            "risk_score": self.risk_score,
            "compliance_status": self.compliance_status,
            "metrics": self.metrics,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class StrategyUpdateRecord:
    update_id: str
    strategy_id: str
    version: str
    update_type: UpdateType
    changes: Dict[str, Any] = field(default_factory=dict)
    author: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    status: str = "applied"
    rollback_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "update_id": self.update_id,
            "strategy_id": self.strategy_id,
            "version": self.version,
            "update_type": self.update_type.value,
            "changes": self.changes,
            "author": self.author,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status,
            "rollback_id": self.rollback_id,
        }


class StrategyUpdate:
    def __init__(self):
        self._strategies: Dict[str, Dict[str, Any]] = {}
        self._evaluations: Dict[str, List[StrategyEvaluation]] = {}
        self._update_history: Dict[str, List[StrategyUpdateRecord]] = {}

    def evaluate_strategy(self, strategy_id: str) -> StrategyEvaluation:
        evaluation_id = f"eval_{hash(strategy_id + str(datetime.now())) % 100000:05d}"

        performance_score = 75.0 + (hash(strategy_id) % 30) - 15
        roi = 0.15 + (hash(strategy_id) % 40) / 100 - 0.2
        risk_score = 30.0 + (hash(strategy_id) % 40)

        metrics = {
            "conversion_rate": 0.02 + (hash(strategy_id) % 30) / 1000,
            "cost_per_acquisition": 50.0 + (hash(strategy_id) % 100) - 50,
            "retention_rate": 0.35 + (hash(strategy_id) % 30) / 100,
            "revenue_per_user": 12.0 + (hash(strategy_id) % 20) - 10,
        }

        recommendations = []
        if performance_score < 70:
            recommendations.append("Consider optimizing targeting parameters")
        if risk_score > 60:
            recommendations.append("Review risk management rules")
        if roi < 0.05:
            recommendations.append("Evaluate budget allocation strategy")

        evaluation = StrategyEvaluation(
            strategy_id=strategy_id,
            evaluation_id=evaluation_id,
            performance_score=performance_score,
            roi=roi,
            risk_score=risk_score,
            compliance_status=True,
            metrics=metrics,
            recommendations=recommendations,
        )

        if strategy_id not in self._evaluations:
            self._evaluations[strategy_id] = []
        self._evaluations[strategy_id].append(evaluation)

        return evaluation

    def update_strategy(self, strategy_id: str, updates: Dict[str, Any]) -> StrategyUpdateRecord:
        update_id = f"upd_{hash(strategy_id + str(datetime.now())) % 100000:05d}"

        if strategy_id not in self._strategies:
            self._strategies[strategy_id] = {
                "status": StrategyStatus.ACTIVE.value,
                "version": "1.0",
                "config": {},
            }

        current_version = self._strategies[strategy_id]["version"]
        new_version = f"{float(current_version) + 0.1:.1f}"

        update_type = UpdateType.PARAMETER
        if "model_id" in updates:
            update_type = UpdateType.MODEL
        elif "rules" in updates:
            update_type = UpdateType.RULE
        elif "config" in updates:
            update_type = UpdateType.CONFIG

        self._strategies[strategy_id]["version"] = new_version
        self._strategies[strategy_id]["config"].update(updates)

        record = StrategyUpdateRecord(
            update_id=update_id,
            strategy_id=strategy_id,
            version=new_version,
            update_type=update_type,
            changes=updates,
            author="system",
        )

        if strategy_id not in self._update_history:
            self._update_history[strategy_id] = []
        self._update_history[strategy_id].append(record)

        return record

    def create_strategy_version(self, strategy_id: str) -> StrategyUpdateRecord:
        if strategy_id not in self._strategies:
            self._strategies[strategy_id] = {
                "status": StrategyStatus.DRAFT.value,
                "version": "1.0",
                "config": {},
            }

        current_version = self._strategies[strategy_id]["version"]
        new_version = f"{int(float(current_version)) + 1}.0"

        self._strategies[strategy_id]["version"] = new_version
        self._strategies[strategy_id]["status"] = StrategyStatus.DRAFT.value

        record = StrategyUpdateRecord(
            update_id=f"ver_{hash(strategy_id + new_version) % 100000:05d}",
            strategy_id=strategy_id,
            version=new_version,
            update_type=UpdateType.CONFIG,
            changes={"version_bump": f"{current_version} -> {new_version}"},
            author="system",
            status="draft",
        )

        if strategy_id not in self._update_history:
            self._update_history[strategy_id] = []
        self._update_history[strategy_id].append(record)

        return record

    def get_strategy_history(self, strategy_id: str) -> Dict[str, Any]:
        if strategy_id not in self._strategies:
            return {"error": f"No strategy found with id {strategy_id}"}

        updates = self._update_history.get(strategy_id, [])
        evaluations = self._evaluations.get(strategy_id, [])

        return {
            "strategy_id": strategy_id,
            "current_version": self._strategies[strategy_id]["version"],
            "status": self._strategies[strategy_id]["status"],
            "total_updates": len(updates),
            "total_evaluations": len(evaluations),
            "recent_updates": [u.to_dict() for u in updates[-5:]],
            "recent_evaluations": [e.to_dict() for e in evaluations[-5:]],
            "history_timestamp": datetime.now().isoformat(),
        }