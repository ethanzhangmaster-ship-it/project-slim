"""Generation State - 任务状态定义"""
from enum import Enum


class GenerationStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    SUBMITTED = "submitted"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


TERMINAL_STATUSES = {
    GenerationStatus.COMPLETED,
    GenerationStatus.FAILED,
    GenerationStatus.APPROVED,
    GenerationStatus.REJECTED,
    GenerationStatus.CANCELLED,
}

ACTIVE_STATUSES = {
    GenerationStatus.QUEUED,
    GenerationStatus.SUBMITTED,
    GenerationStatus.GENERATING,
    GenerationStatus.RETRYING,
    GenerationStatus.REVIEWING,
}

STATUS_FLOW = [
    GenerationStatus.CREATED,
    GenerationStatus.QUEUED,
    GenerationStatus.SUBMITTED,
    GenerationStatus.GENERATING,
    GenerationStatus.COMPLETED,
    GenerationStatus.REVIEWING,
    GenerationStatus.APPROVED,
]


def can_transition(current: GenerationStatus, target: GenerationStatus) -> bool:
    if target in TERMINAL_STATUSES:
        return current not in TERMINAL_STATUSES
    if target == GenerationStatus.RETRYING:
        return current in {GenerationStatus.FAILED, GenerationStatus.GENERATING}
    if target == GenerationStatus.QUEUED:
        return current == GenerationStatus.CREATED
    if target == GenerationStatus.SUBMITTED:
        return current in {GenerationStatus.QUEUED, GenerationStatus.RETRYING}
    if target == GenerationStatus.GENERATING:
        return current == GenerationStatus.SUBMITTED
    if target == GenerationStatus.COMPLETED:
        return current == GenerationStatus.GENERATING
    if target == GenerationStatus.REVIEWING:
        return current == GenerationStatus.COMPLETED
    if target == GenerationStatus.APPROVED:
        return current == GenerationStatus.REVIEWING
    if target == GenerationStatus.REJECTED:
        return current == GenerationStatus.REVIEWING
    return False
