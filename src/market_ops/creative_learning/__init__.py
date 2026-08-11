"""E9.7: Creative Prediction Feedback Learning Engine.

Closes the prediction→feedback→learning loop:
  1. Records E9.6 predictions
  2. Collects real campaign performance
  3. Reconstructs actual archetypes via E9.5 pipeline
  4. Computes prediction errors
  5. Learns optimal DNA feature weights
  6. Re-predicts with improved weights
  7. Exports all 5 output files

Modules:
  - schemas: PredictionRecord, CreativeActualPerformance, etc.
  - prediction_tracker: PredictionTracker
  - performance_collector: PerformanceCollector, MockPerformanceGenerator
  - archetype_reconstruction: ArchetypeReconstructionEngine
  - prediction_error_analyzer: PredictionErrorAnalyzer
  - dna_weight_optimizer: DNAWeightOptimizer
  - learning_engine: LearningEngine, run_e97_pipeline
  - export: LearningExporter

Outputs:
  - prediction_history.json
  - actual_performance.json
  - prediction_error_report.json
  - dna_weight_config.json
  - learning_report.json
"""

from market_ops.creative_learning.schemas import (
    PredictionRecord, CreativeActualPerformance,
    ArchetypeError, MetricError, PredictionError,
    DNAWeightUpdate, DNAWeightConfig, LearningReport,
)
from market_ops.creative_learning.prediction_tracker import PredictionTracker
from market_ops.creative_learning.performance_collector import (
    PerformanceCollector, MockPerformanceGenerator,
)
from market_ops.creative_learning.archetype_reconstruction import ArchetypeReconstructionEngine
from market_ops.creative_learning.prediction_error_analyzer import PredictionErrorAnalyzer
from market_ops.creative_learning.dna_weight_optimizer import DNAWeightOptimizer
from market_ops.creative_learning.learning_engine import LearningEngine, run_e97_pipeline
from market_ops.creative_learning.export import LearningExporter