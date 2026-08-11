"""
E15.1.2 — Autonomous Game Factory Brain
========================================

Closes the loop: Growth OS -> Publishing Factory -> Revenue OS -> next game.

Modules:
    models                    core dataclasses / enums
    opportunity_intake        Growth OS drop-in + fleet-derived signals
    opportunity_predictor     opportunity -> CPI / D30 / D90 ROAS forecast
    spec_generator            opportunity -> ProductSpec -> GameProduct
    blueprint_generator       ProductSpec -> GameBlueprint (Unity-ready)
    portfolio_manager         lifecycle state machine + daily ROAS ladder
    decision_engine           retention/economics KEEP / SCALE / KILL
                              + IAA mode (real no-UA fleet, rev/eCPM)
    fleet_bridge              REAL MAX fleet -> IAA verdict card
    pattern_miner             fleet outcomes -> SuccessPattern weights
    aso_bandit                listing variant explore-then-commit
    store_experiment_planner  PPO / Play listing experiment plans
    factory_brain             daily orchestrator (run_daily)

Deterministic. No LLM. real_api_called locked False.
"""
from .aso_bandit import AsoBandit
from .blueprint_generator import BlueprintGenerator
from .decision_engine import GameDecisionEngine, payback_days
from .factory_brain import FactoryBrain
from .fleet_bridge import (
    FleetGame, FleetVerdictReport, NORTH_STAR_RPD, RealFleetBridge,
)
from .models import (
    AsoVariant, BrainReport, GameBlueprint, GameDecision, LifecycleStage,
    MarketOpportunity, PortfolioAction, PortfolioDecision, ProductSpec,
    RoasPrediction, StoreExperimentPlan, SuccessPattern, Verdict,
)
from .opportunity_intake import OpportunityIntake
from .opportunity_predictor import OpportunityPredictor
from .pattern_miner import PatternMiner
from .portfolio_manager import PortfolioManager
from .spec_generator import SpecGenerator
from .store_experiment_planner import StoreExperimentPlanner

__all__ = [
    "AsoBandit", "BlueprintGenerator", "GameDecisionEngine", "payback_days",
    "FactoryBrain", "OpportunityIntake", "OpportunityPredictor",
    "PatternMiner", "PortfolioManager", "SpecGenerator",
    "StoreExperimentPlanner",
    "FleetGame", "FleetVerdictReport", "NORTH_STAR_RPD", "RealFleetBridge",
    "AsoVariant", "BrainReport", "GameBlueprint", "GameDecision",
    "LifecycleStage", "MarketOpportunity", "PortfolioAction",
    "PortfolioDecision", "ProductSpec", "RoasPrediction",
    "StoreExperimentPlan", "SuccessPattern", "Verdict",
]
