"""
E15.1.1 — Autonomous Publishing Factory
=======================================

One operator, 10–50 overseas casual games, AI-automated:
prepare -> generate -> check -> submit -> monitor -> fix -> resubmit.

Public surface:
  catalog.*            fleet registry + AI scheduler
  asset_pipeline.*     screenshot / icon / video factory + validator
  metadata_engine.*    ASO + localization + keyword optimization
  compliance.*         policy (4.3) + privacy + store risk predictor
  publishing_factory    per-game PublishingPlan builder (three-tier gate)
  batch_orchestrator   daily fleet run + rejection feedback loop
  memory               JSONL learning store
"""
from operation.publishing_factory.catalog import (
    GameProduct, GameRegistry, FleetManager, FleetTask, FleetScanReport,
)
from operation.publishing_factory.publishing_factory import (
    PublishingFactory, PublishingPlan, ApprovalStatus,
)
from operation.publishing_factory.batch_orchestrator import (
    BatchOrchestrator, BatchReport, RejectClass,
)
from operation.publishing_factory.memory import (
    PublishingMemory, PublishingMemoryEntry,
)

__all__ = [
    "GameProduct", "GameRegistry", "FleetManager", "FleetTask", "FleetScanReport",
    "PublishingFactory", "PublishingPlan", "ApprovalStatus",
    "BatchOrchestrator", "BatchReport", "RejectClass",
    "PublishingMemory", "PublishingMemoryEntry",
]
