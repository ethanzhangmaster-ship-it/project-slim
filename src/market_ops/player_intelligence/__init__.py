"""E9.4 + E9.5: Player Intelligence Suite.

E9.4 — Player Value Attribution Engine:
  Maps Creative DNA to real player behavior and revenue,
  forming the IAP Creative Genome Fitness loop.

E9.5 — Player Archetype Intelligence Engine:
  Classifies players into 5 archetypes (Collector, Progression,
  Power, Explorer, Casual) and builds Creative-Archetype Matrix.

Modules:
  - models: PlayerEvent, PlayerDNA, PlayerCohort, IAPGenomeFitness
  - player_dna_engine: PlayerEventCollector, PlayerDNAEngine
  - creative_player_attribution: CreativePlayerAttribution
  - iap_genome_fitness: IAPGenomeFitnessCalculator
  - player_genome: PlayerGenome, BehaviorFeatures, ArchetypeStats, etc.
  - behavior_feature_engine: BehaviorFeatureEngine
  - archetype_classifier: ArchetypeClassifier, run_e95_pipeline
"""

from market_ops.player_intelligence.models import (
    PlayerEvent, PlayerDNA, PlayerCohort, IAPGenomeFitness,
    ProgressionDNA, CollectionDNA, PaymentDNA, RetentionDNA,
)
from market_ops.player_intelligence.player_dna_engine import PlayerEventCollector, PlayerDNAEngine
from market_ops.player_intelligence.creative_player_attribution import CreativePlayerAttribution
from market_ops.player_intelligence.iap_genome_fitness import IAPGenomeFitnessCalculator

# E9.5
from market_ops.player_intelligence.player_genome import (
    PlayerArchetype, ValueSegment,
    BehaviorFeatures, PaymentProfile, PlayerGenome,
    ArchetypeStats, CreativeArchetypeEntry,
)
from market_ops.player_intelligence.behavior_feature_engine import BehaviorFeatureEngine
from market_ops.player_intelligence.archetype_classifier import (
    ArchetypeClassifier, run_e95_pipeline,
)