"""
E13.4.3 — Strategy Intelligence Layer
=======================================

The first layer that *judges* using the system's own operating history.

    Rules (E13.3.2)
        |
        v
    Simulator Prediction (E13.2.9)
        |
        v
    Experiment Evidence (E13.4.2)   <-- Ground-Truth generator
        |
        v
    Decision Memory (E13.4.1)
        |
        v
    Strategy Prior (Bayesian Beta)  <-- THIS LAYER
        |
        v
    Final Ranking  =  0.4*Sim + 0.3*Safety + 0.2*Conf + 0.1*Prior
        |
        v
    Executor (E13.3.3)

Design (per E13.4.3 scope):
  * NOT a deep model in v1. NOT an AI Agent. NOT connected to any external
    model/API. Pure-Python, Lean, stdlib-only.
  * Intelligence Layer = Rules + Simulator + Experiment Prior + Lightweight
    Model. The lightweight model is a transparent bucketed Laplace estimator
    (Logistic/XGBoost are named as *future* upgrades, not used here).
  * This layer only *ranks*; it never executes any mutation (the Executor is
    the only place a decision is applied).
"""
from monetization.intelligence.models import (
    StrategyFeature, StrategyProbability, IntelligenceResult, CalibrationFactor,
)
from monetization.intelligence.strategy_prior import StrategyPriorEngine
from monetization.intelligence.calibration import SimulatorCalibrator
from monetization.intelligence.strategy_ranker import (
    StrategyRanker, V1_WEIGHTS, EVOLVED_WEIGHTS,
)
from monetization.intelligence.lightweight_model import LightweightModel
from monetization.intelligence.feature_builder import build_feature

__all__ = [
    "StrategyFeature", "StrategyProbability", "IntelligenceResult",
    "CalibrationFactor", "StrategyPriorEngine", "SimulatorCalibrator",
    "StrategyRanker", "V1_WEIGHTS", "EVOLVED_WEIGHTS", "LightweightModel",
    "build_feature",
]
