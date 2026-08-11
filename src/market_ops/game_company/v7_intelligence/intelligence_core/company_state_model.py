from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum


@dataclass
class FinanceState:
    cash: float = 0.0
    revenue: float = 0.0
    monthly_burn: float = 0.0
    runway_months: float = 0.0
    total_investment: float = 0.0
    profit_margin: float = 0.0
    roas: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cash": self.cash,
            "revenue": self.revenue,
            "monthly_burn": self.monthly_burn,
            "runway_months": self.runway_months,
            "total_investment": self.total_investment,
            "profit_margin": self.profit_margin,
            "roas": self.roas,
        }


@dataclass
class ProductState:
    active_games: int = 0
    games_in_development: int = 0
    top_game_revenue: float = 0.0
    avg_dau: int = 0
    avg_retention_d1: float = 0.0
    avg_retention_d7: float = 0.0
    avg_retention_d30: float = 0.0
    avg_arpu: float = 0.0
    projects: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_games": self.active_games,
            "games_in_development": self.games_in_development,
            "top_game_revenue": self.top_game_revenue,
            "avg_dau": self.avg_dau,
            "avg_retention_d1": self.avg_retention_d1,
            "avg_retention_d7": self.avg_retention_d7,
            "avg_retention_d30": self.avg_retention_d30,
            "avg_arpu": self.avg_arpu,
            "projects": self.projects,
        }


@dataclass
class MarketState:
    target_market: str = ""
    market_size: float = 0.0
    market_growth_rate: float = 0.0
    competition_level: str = "medium"
    top_genres: List[str] = field(default_factory=list)
    cpi_trend: float = 0.0
    opportunities: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_market": self.target_market,
            "market_size": self.market_size,
            "market_growth_rate": self.market_growth_rate,
            "competition_level": self.competition_level,
            "top_genres": self.top_genres,
            "cpi_trend": self.cpi_trend,
            "opportunities": self.opportunities,
        }


@dataclass
class GrowthState:
    daily_spend: float = 0.0
    daily_installs: int = 0
    daily_revenue: float = 0.0
    ua_channels: Dict[str, float] = field(default_factory=dict)
    creative_count: int = 0
    ab_tests_running: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "daily_spend": self.daily_spend,
            "daily_installs": self.daily_installs,
            "daily_revenue": self.daily_revenue,
            "ua_channels": self.ua_channels,
            "creative_count": self.creative_count,
            "ab_tests_running": self.ab_tests_running,
        }


@dataclass
class RiskState:
    overall_risk_score: float = 0.0
    budget_risk: float = 0.0
    market_risk: float = 0.0
    operational_risk: float = 0.0
    active_alerts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_risk_score": self.overall_risk_score,
            "budget_risk": self.budget_risk,
            "market_risk": self.market_risk,
            "operational_risk": self.operational_risk,
            "active_alerts": self.active_alerts,
        }


@dataclass
class CompanyStateModel:
    finance: FinanceState = field(default_factory=FinanceState)
    products: ProductState = field(default_factory=ProductState)
    market: MarketState = field(default_factory=MarketState)
    growth: GrowthState = field(default_factory=GrowthState)
    risk: RiskState = field(default_factory=RiskState)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finance": self.finance.to_dict(),
            "products": self.products.to_dict(),
            "market": self.market.to_dict(),
            "growth": self.growth.to_dict(),
            "risk": self.risk.to_dict(),
            "timestamp": self.timestamp.isoformat(),
        }

    def health_score(self) -> float:
        score = 50.0
        if self.finance.roas > 1.5:
            score += 20
        if self.finance.runway_months > 12:
            score += 10
        if self.products.avg_retention_d1 > 0.4:
            score += 10
        if self.market.market_growth_rate > 0.1:
            score += 5
        if self.risk.overall_risk_score < 0.3:
            score += 5
        return min(score, 100.0)

    def is_healthy(self) -> bool:
        return self.health_score() > 60
