"""State Transition - 状态转换规则"""
from typing import Dict, Set, Tuple
from datetime import datetime
from dataclasses import dataclass, field

from .generation_state import GenerationState, TERMINAL_STATES


@dataclass
class TransitionRecord:
    """状态转换记录"""
    generation_id: str = ""
    from_state: str = ""
    to_state: str = ""
    timestamp: str = ""
    reason: str = ""
    metadata: Dict[str, any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


# 允许的转换
ALLOWED_TRANSITIONS: Dict[GenerationState, Set[GenerationState]] = {
    GenerationState.CREATED: {
        GenerationState.QUEUED,
        GenerationState.CANCELLED,
    },
    GenerationState.QUEUED: {
        GenerationState.PROCESSING,
        GenerationState.CANCELLED,
    },
    GenerationState.PROCESSING: {
        GenerationState.SUCCESS,
        GenerationState.FAILED,
    },
    GenerationState.FAILED: {
        GenerationState.RETRYING,
        GenerationState.CANCELLED,
    },
    GenerationState.RETRYING: {
        GenerationState.PROCESSING,
        GenerationState.CANCELLED,
    },
    GenerationState.SUCCESS: set(),
    GenerationState.CANCELLED: set(),
}


class StateTransition:
    """状态转换器"""

    @classmethod
    def can_transition(cls, from_state: GenerationState, to_state: GenerationState) -> bool:
        """检查是否允许转换"""
        if from_state in TERMINAL_STATES:
            return False
        allowed = ALLOWED_TRANSITIONS.get(from_state, set())
        return to_state in allowed

    @classmethod
    def transition(cls, generation_id: str, from_state: GenerationState,
                   to_state: GenerationState, reason: str = "") -> TransitionRecord:
        """执行状态转换"""
        if not cls.can_transition(from_state, to_state):
            raise ValueError(f"Invalid transition: {from_state} -> {to_state}")

        return TransitionRecord(
            generation_id=generation_id,
            from_state=from_state.value,
            to_state=to_state.value,
            reason=reason,
        )

    @classmethod
    def get_next_states(cls, current: GenerationState) -> Set[GenerationState]:
        """获取可能的下一状态"""
        return ALLOWED_TRANSITIONS.get(current, set())