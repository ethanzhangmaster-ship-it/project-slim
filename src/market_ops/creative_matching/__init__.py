"""E9.6: Creative → Archetype Matching Engine.

Predicts which player archetypes a Creative DNA will attract,
and the expected LTV / D30 / payer_rate.

Modules:
  - schemas: DNAFeatureVector, ArchetypeAffinity, CreativePrediction, etc.
  - dna_feature_encoder: Creative DNA → numeric feature vector
  - creative_archetype_profile: Historical archetype distribution DB
  - archetype_predictor: Rule + Bayesian archetype prediction
  - matching_engine: Orchestrator + Ranking + Export
"""

from market_ops.creative_matching.schemas import (
    DNAFeatureVector, ArchetypeAffinity, CreativePrediction, CreativeArchetypeRank,
)
from market_ops.creative_matching.dna_feature_encoder import DNAFeatureEncoder
from market_ops.creative_matching.creative_archetype_profile import CreativeArchetypeProfileDB
from market_ops.creative_matching.archetype_predictor import ArchetypePredictor
from market_ops.creative_matching.matching_engine import MatchingEngine, run_e96_pipeline