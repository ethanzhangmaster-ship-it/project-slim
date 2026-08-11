"""
E13.4.2 — Monetization Experiment Engine
========================================

Turns E13.3.2 Strategy Candidates into structured A/B/n evidence (not guesses),
using the E13.2.9 Simulator as the traffic simulator. Feeds each treatment arm
into the E13.4.1 Decision Memory as a closed-loop sample.

Public API:
  * create_bid_floor_experiment / create_waterfall_experiment /
    create_frequency_experiment  — the 3 acceptance experiments
  * experiment_from_candidate      — build from a real E13.3.2 candidate
  * ExperimentManager              — run_experiment / run_and_record /
                                     run_pipeline_experiments
  * analyze / generate_experiment_report
"""

from monetization.experiments.models import (
    DEFAULT_BASELINE, Experiment, ExperimentResult, Variant, VariantMetric,
    new_id, synthetic_baseline,
)
from monetization.experiments.variant_allocator import (
    allocate, assign_impressions, bucket,
)
from monetization.experiments.experiment_manager import (
    ExperimentManager, create_bid_floor_experiment,
    create_waterfall_experiment, create_frequency_experiment,
    experiment_from_candidate,
)
from monetization.experiments.experiment_analyzer import (
    analyze, compare_variants, generate_experiment_report,
)

__all__ = [
    "Experiment", "ExperimentResult", "Variant", "VariantMetric",
    "DEFAULT_BASELINE", "synthetic_baseline", "new_id",
    "allocate", "assign_impressions", "bucket",
    "ExperimentManager", "create_bid_floor_experiment",
    "create_waterfall_experiment", "create_frequency_experiment",
    "experiment_from_candidate",
    "analyze", "compare_variants", "generate_experiment_report",
]
