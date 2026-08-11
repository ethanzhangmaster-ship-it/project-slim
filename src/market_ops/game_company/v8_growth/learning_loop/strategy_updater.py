from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class StrategyStatus(Enum):
    ACTIVE = "active"
    UPDATED = "updated"
    DEPRECATED = "deprecated"
    TESTING = "testing"


class StrategyType(Enum):
    ACQUISITION = "acquisition"
    RETENTION = "retention"
    MONETIZATION = "monetization"
    ENGAGEMENT = "engagement"
    GROWTH = "growth"


@dataclass
class StrategyParameter:
    name: str
    value: Any
    min_value: Any = None
    max_value: Any = None
    updateable: bool = True
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "updateable": self.updateable,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class Strategy:
    strategy_id: str
    name: str
    type: StrategyType
    status: StrategyStatus = StrategyStatus.ACTIVE
    parameters: Dict[str, StrategyParameter] = field(default_factory=dict)
    performance_score: float = 0.0
    confidence: float = 0.0
    version: int = 1
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "type": self.type.value,
            "status": self.status.value,
            "parameters": {k: v.to_dict() for k, v in self.parameters.items()},
            "performance_score": self.performance_score,
            "confidence": self.confidence,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class StrategyUpdate:
    update_id: str
    strategy_id: str
    parameter_changes: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    expected_improvement: float = 0.0
    confidence: float = 0.0
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "update_id": self.update_id,
            "strategy_id": self.strategy_id,
            "parameter_changes": self.parameter_changes,
            "reason": self.reason,
            "expected_improvement": self.expected_improvement,
            "confidence": self.confidence,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


class StrategyUpdater:
    def __init__(self):
        self._strategies: Dict[str, Strategy] = {}
        self._updates: List[StrategyUpdate] = []
        self._update_history: List[Dict[str, Any]] = []
        self._learning_thresholds = {
            "min_confidence": 0.7,
            "min_improvement": 0.05,
            "min_samples": 10,
        }

    def create_strategy(
        self,
        name: str,
        type: StrategyType,
        parameters: Dict[str, Any] = None
    ) -> Strategy:
        strategy_id = f"str_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        strategy_params = {}

        if parameters:
            for key, value in parameters.items():
                strategy_params[key] = StrategyParameter(name=key, value=value)

        strategy = Strategy(
            strategy_id=strategy_id,
            name=name,
            type=type,
            parameters=strategy_params,
            performance_score=random.uniform(0.5, 0.9),
            confidence=random.uniform(0.5, 0.9),
        )
        self._strategies[strategy_id] = strategy
        return strategy

    def propose_update(
        self,
        strategy_id: str,
        parameter_changes: Dict[str, Any],
        reason: str,
        expected_improvement: float = 0.1,
        confidence: float = 0.8
    ) -> StrategyUpdate:
        update_id = f"upd_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        update = StrategyUpdate(
            update_id=update_id,
            strategy_id=strategy_id,
            parameter_changes=parameter_changes,
            reason=reason,
            expected_improvement=expected_improvement,
            confidence=confidence,
        )
        self._updates.append(update)
        return update

    def apply_update(self, update_id: str) -> Optional[Strategy]:
        update = self._find_update(update_id)
        if not update:
            return None

        strategy = self._strategies.get(update.strategy_id)
        if not strategy:
            return None

        for param_name, new_value in update.parameter_changes.items():
            if param_name in strategy.parameters:
                strategy.parameters[param_name].value = new_value
                strategy.parameters[param_name].last_updated = datetime.now()
            else:
                strategy.parameters[param_name] = StrategyParameter(
                    name=param_name,
                    value=new_value,
                )

        strategy.version += 1
        strategy.updated_at = datetime.now()
        strategy.status = StrategyStatus.UPDATED

        update.status = "applied"
        self._update_history.append({
            "update_id": update_id,
            "strategy_id": strategy.strategy_id,
            "changes": update.parameter_changes,
            "timestamp": datetime.now().isoformat(),
        })

        return strategy

    def _find_update(self, update_id: str) -> Optional[StrategyUpdate]:
        for update in self._updates:
            if update.update_id == update_id:
                return update
        return None

    def learn_from_outcomes(self, outcomes: List[Dict[str, Any]]) -> List[StrategyUpdate]:
        updates = []

        for outcome in outcomes:
            if outcome.get("outcome_type") == "success":
                strategy_id = outcome.get("strategy_id")
                if strategy_id and strategy_id in self._strategies:
                    strategy = self._strategies[strategy_id]
                    strategy.performance_score = min(1.0, strategy.performance_score + 0.05)
                    strategy.confidence = min(1.0, strategy.confidence + 0.02)

            elif outcome.get("outcome_type") == "failure":
                strategy_id = outcome.get("strategy_id")
                if strategy_id and strategy_id in self._strategies:
                    strategy = self._strategies[strategy_id]
                    strategy.performance_score = max(0, strategy.performance_score - 0.1)

                    params_to_adjust = self._identify_adjustments(strategy, outcome)
                    if params_to_adjust:
                        update = self.propose_update(
                            strategy_id=strategy_id,
                            parameter_changes=params_to_adjust,
                            reason=f"Adjusting based on failure outcome: {outcome.get('action_id')}",
                            expected_improvement=0.1,
                            confidence=0.7,
                        )
                        updates.append(update)

        return updates

    def _identify_adjustments(self, strategy: Strategy, outcome: Dict[str, Any]) -> Dict[str, Any]:
        adjustments = {}
        for param_name, param in strategy.parameters.items():
            if param.updateable:
                current = param.value
                if isinstance(current, (int, float)):
                    adjustments[param_name] = current * random.uniform(0.9, 1.1)
        return adjustments

    def get_strategy(self, strategy_id: str) -> Optional[Strategy]:
        return self._strategies.get(strategy_id)

    def get_strategies(self, type: StrategyType = None) -> List[Strategy]:
        strategies = list(self._strategies.values())
        if type:
            strategies = [s for s in strategies if s.type == type]
        return strategies

    def get_update(self, update_id: str) -> Optional[StrategyUpdate]:
        return self._find_update(update_id)

    def get_all_updates(self) -> List[StrategyUpdate]:
        return list(self._updates)

    def get_update_history(self) -> List[Dict[str, Any]]:
        return list(self._update_history)

    def get_stats(self) -> Dict[str, Any]:
        strategies = list(self._strategies.values())
        return {
            "total_strategies": len(strategies),
            "strategies_by_type": {
                t.value: sum(1 for s in strategies if s.type == t)
                for t in StrategyType
            },
            "strategies_by_status": {
                s.value: sum(1 for st in strategies if st.status == s)
                for s in StrategyStatus
            },
            "total_updates": len(self._updates),
            "history_count": len(self._update_history),
        }