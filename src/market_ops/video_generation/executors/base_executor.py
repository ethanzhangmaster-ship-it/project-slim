"""Base Executor Interface"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ExecutorResult:
    job_id: str = ""
    status: str = "submitted"
    video_url: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseExecutor(ABC):
    """平台执行器基类"""

    platform_name: str = "base"

    def __init__(self, api_key: str = "", api_base: str = ""):
        self.api_key = api_key
        self.api_base = api_base

    @abstractmethod
    def submit(self, prompt: Dict[str, Any], settings: Dict[str, Any] = None) -> ExecutorResult:
        pass

    @abstractmethod
    def get_status(self, job_id: str) -> ExecutorResult:
        pass

    def cancel(self, job_id: str) -> bool:
        return False

    def _generate_job_id(self) -> str:
        import uuid
        return f"{self.platform_name}_{uuid.uuid4().hex[:12]}"
