"""Generation State - 生产级状态定义"""
from enum import Enum


class GenerationState(str, Enum):
    """生成任务状态"""
    CREATED = "created"
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


TERMINAL_STATES = {
    GenerationState.SUCCESS,
    GenerationState.FAILED,
    GenerationState.CANCELLED,
}

ACTIVE_STATES = {
    GenerationState.QUEUED,
    GenerationState.PROCESSING,
    GenerationState.RETRYING,
}