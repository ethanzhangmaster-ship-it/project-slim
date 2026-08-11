"""Phase 2.2A: Core production pipeline — business logic, zero observability dependency.

Contains:
  - generation_store.py  — SQLite persistence with strict state machine
  - lovart_queue.py      — Task queue (PENDING → CLAIM → PROCESSING → SUCCESS)
  - lovart_worker.py     — Worker that processes tasks, publishes events to EventBus
  - creative_generation_manager.py — Pipeline orchestrator

All core modules only depend on each other and the observability EventBus.
They have NO dependency on any specific Monitor or Observer.
"""

from .generation_store import GenerationStore, GenerationStatus
from .lovart_queue import LovartQueue
from .lovart_worker import LovartWorker, WorkerPool
from .creative_generation_manager import CreativeGenerationManager, BatchResult

__all__ = [
    "GenerationStore",
    "GenerationStatus",
    "LovartQueue",
    "LovartWorker",
    "WorkerPool",
    "CreativeGenerationManager",
    "BatchResult",
]