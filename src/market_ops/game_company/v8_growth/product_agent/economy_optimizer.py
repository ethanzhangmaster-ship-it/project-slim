from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class CurrencyType(Enum):
    HARD = "hard"
    SOFT = "soft"
    SOCIAL = "social"
    PREMIUM = "premium"


class EconomyStatus(Enum):
    BALANCED = "balanced"
    INFLATED = "inflated"
    DEFLATED = "deflated"
    CRITICAL = "critical"


@dataclass
class CurrencyBalance:
    currency_type: CurrencyType
    total_supply: float = 0.0
    total_demand: float = 0.0
    balance_ratio: float = 0.0
    circulation_rate: float = 0.0
    avg_player_balance: float = 0.0
    inflation_rate: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "currency_type": self.currency_type.value,
            "total_supply": self.total_supply,
            "total_demand": self.total_demand,
            "balance_ratio": self.balance_ratio,
            "circulation_rate": self.circulation_rate,
            "avg_player_balance": self.avg_player_balance,
            "inflation_rate": self.inflation_rate,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class EconomySource:
    source_id: str
    name: str
    currency_type: CurrencyType
    generation_rate: float = 0.0
    sink_rate: float = 0.0
    balance: float = 0.0
    player_count: int = 0
    category: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "currency_type": self.currency_type.value,
            "generation_rate": self.generation_rate,
            "sink_rate": self.sink_rate,
            "balance": self.balance,
            "player_count": self.player_count,
            "category": self.category,
        }


@dataclass
class EconomyAdjustment:
    adjustment_id: str
    currency_type: CurrencyType
    action: str
    magnitude: float = 0.0
    reason: str = ""
    expected_impact: float = 0.0
    risk_level: str = "low"
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "adjustment_id": self.adjustment_id,
            "currency_type": self.currency_type.value,
            "action": self.action,
            "magnitude": self.magnitude,
            "reason": self.reason,
            "expected_impact": self.expected_impact,
            "risk_level": self.risk_level,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class EconomyAnalysis:
    analysis_id: str
    overall_status: EconomyStatus = EconomyStatus.BALANCED
    currency_balances: Dict[CurrencyType, CurrencyBalance] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "overall_status": self.overall_status.value,
            "currency_balances": {k.value: v.to_dict() for k, v in self.currency_balances.items()},
            "issues": self.issues,
            "recommendations": self.recommendations,
            "created_at": self.created_at.isoformat(),
        }


class EconomyOptimizer:
    def __init__(self):
        self._balances: Dict[CurrencyType, CurrencyBalance] = {}
        self._sources: Dict[str, EconomySource] = {}
        self._adjustments: List[EconomyAdjustment] = []
        self._analyses: Dict[str, EconomyAnalysis] = {}
        self._targets: Dict[CurrencyType, Dict[str, float]] = {
            CurrencyType.HARD: {"balance_ratio": 1.0, "inflation_max": 0.05},
            CurrencyType.SOFT: {"balance_ratio": 0.9, "inflation_max": 0.1},
        }

    def register_source(
        self,
        source_id: str,
        name: str,
        currency_type: CurrencyType,
        generation_rate: float,
        sink_rate: float,
        category: str = ""
    ) -> EconomySource:
        source = EconomySource(
            source_id=source_id,
            name=name,
            currency_type=currency_type,
            generation_rate=generation_rate,
            sink_rate=sink_rate,
            balance=generation_rate - sink_rate,
            player_count=random.randint(1000, 50000),
            category=category,
        )
        self._sources[source_id] = source
        return source

    def update_balance(self, currency_type: CurrencyType) -> CurrencyBalance:
        type_sources = [s for s in self._sources.values() if s.currency_type == currency_type]
        total_gen = sum(s.generation_rate * s.player_count for s in type_sources)
        total_sink = sum(s.sink_rate * s.player_count for s in type_sources)
        balance_ratio = total_gen / max(1, total_sink)
        inflation = (total_gen - total_sink) / max(1, total_gen) * 0.1

        balance = CurrencyBalance(
            currency_type=currency_type,
            total_supply=total_gen,
            total_demand=total_sink,
            balance_ratio=balance_ratio,
            circulation_rate=random.uniform(0.5, 2.0),
            avg_player_balance=random.uniform(100, 10000),
            inflation_rate=inflation,
        )
        self._balances[currency_type] = balance
        return balance

    def analyze_economy(self) -> EconomyAnalysis:
        analysis_id = f"economy_analysis_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        issues = []
        recommendations = []
        overall_status = EconomyStatus.BALANCED

        for currency_type in CurrencyType:
            balance = self._balances.get(currency_type)
            if not balance:
                balance = self.update_balance(currency_type)

            target = self._targets.get(currency_type, {})

            if balance.balance_ratio > 1.2:
                issues.append(f"{currency_type.value} currency oversupplied (ratio: {balance.balance_ratio:.2f})")
                recommendations.append(f"Reduce {currency_type.value} generation or increase sinks")
                overall_status = EconomyStatus.INFLATED if overall_status != EconomyStatus.CRITICAL else overall_status
            elif balance.balance_ratio < 0.8:
                issues.append(f"{currency_type.value} currency undersupplied (ratio: {balance.balance_ratio:.2f})")
                recommendations.append(f"Increase {currency_type.value} generation or reduce sinks")
                overall_status = EconomyStatus.DEFLATED if overall_status != EconomyStatus.CRITICAL else overall_status

            if balance.inflation_rate > target.get("inflation_max", 0.1):
                issues.append(f"{currency_type.value} inflation rate too high ({balance.inflation_rate:.2%})")
                recommendations.append(f"Implement {currency_type.value} sink mechanisms")

        if len(issues) > 3:
            overall_status = EconomyStatus.CRITICAL

        analysis = EconomyAnalysis(
            analysis_id=analysis_id,
            overall_status=overall_status,
            currency_balances=dict(self._balances),
            issues=issues,
            recommendations=recommendations,
        )
        self._analyses[analysis_id] = analysis
        return analysis

    def suggest_adjustments(self) -> List[EconomyAdjustment]:
        adjustments = []
        analysis = self.analyze_economy()

        for issue in analysis.issues:
            if "oversupplied" in issue:
                for currency_type in CurrencyType:
                    if currency_type.value in issue:
                        adj = EconomyAdjustment(
                            adjustment_id=f"adj_reduce_{currency_type.value}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                            currency_type=currency_type,
                            action="reduce_generation",
                            magnitude=0.2,
                            reason=issue,
                            expected_impact=-0.15,
                            risk_level="medium",
                        )
                        adjustments.append(adj)

            elif "undersupplied" in issue:
                for currency_type in CurrencyType:
                    if currency_type.value in issue:
                        adj = EconomyAdjustment(
                            adjustment_id=f"adj_increase_{currency_type.value}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                            currency_type=currency_type,
                            action="increase_generation",
                            magnitude=0.2,
                            reason=issue,
                            expected_impact=0.15,
                            risk_level="medium",
                        )
                        adjustments.append(adj)

            elif "inflation" in issue:
                for currency_type in CurrencyType:
                    if currency_type.value in issue:
                        adj = EconomyAdjustment(
                            adjustment_id=f"adj_sink_{currency_type.value}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                            currency_type=currency_type,
                            action="add_sink",
                            magnitude=0.3,
                            reason=issue,
                            expected_impact=-0.1,
                            risk_level="low",
                        )
                        adjustments.append(adj)

        self._adjustments.extend(adjustments)
        return adjustments

    def get_balance(self, currency_type: CurrencyType) -> Optional[CurrencyBalance]:
        return self._balances.get(currency_type)

    def get_all_balances(self) -> List[CurrencyBalance]:
        return list(self._balances.values())

    def get_source(self, source_id: str) -> Optional[EconomySource]:
        return self._sources.get(source_id)

    def get_all_sources(self) -> List[EconomySource]:
        return list(self._sources.values())

    def get_adjustments(self) -> List[EconomyAdjustment]:
        return list(self._adjustments)

    def get_analysis(self, analysis_id: str) -> Optional[EconomyAnalysis]:
        return self._analyses.get(analysis_id)

    def get_all_analyses(self) -> List[EconomyAnalysis]:
        return list(self._analyses.values())

    def set_target(self, currency_type: CurrencyType, metric: str, target: float):
        if currency_type not in self._targets:
            self._targets[currency_type] = {}
        self._targets[currency_type][metric] = target

    def get_targets(self) -> Dict[str, Dict[str, float]]:
        return {k.value: v for k, v in self._targets.items()}

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_currency_types": len(self._balances),
            "total_sources": len(self._sources),
            "total_adjustments": len(self._adjustments),
            "total_analyses": len(self._analyses),
            "current_targets": self.get_targets(),
        }