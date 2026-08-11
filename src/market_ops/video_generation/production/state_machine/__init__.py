"""State Machine Module for Generation Task Tracking.

Provides state management:
- GenerationState: Task state enumeration
- StateTransition: Transition rules and execution
- StateStore: SQLite persistence
"""

from .generation_state import (
    GenerationState,
    TERMINAL_STATES,
    ACTIVE_STATES
)

from .state_transition import (
    TransitionRecord,
    ALLOWED_TRANSITIONS,
    StateTransition
)

from .state_store import (
    StateStore,
    SCHEMA_SQL
)

__all__ = [
    "GenerationState",
    "TERMINAL_STATES",
    "ACTIVE_STATES",
    "TransitionRecord",
    "ALLOWED_TRANSITIONS",
    "StateTransition",
    "StateStore",
    "SCHEMA_SQL"
]