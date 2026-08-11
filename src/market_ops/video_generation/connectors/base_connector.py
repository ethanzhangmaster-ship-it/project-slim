"""Base Connector - 真实平台 API 连接层"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ConnectorResult:
    job_id: str = ""
    status: str = "pending"
    video_url: str = ""
    video_path: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseConnector(ABC):
    """平台连接器基类 - 处理真实 API 调用"""

    platform_name: str = "base"

    def __init__(self, api_key: str = "", api_base: str = "", timeout: int = 300):
        self.api_key = api_key
        self.api_base = api_base
        self.timeout = timeout

    @abstractmethod
    def submit(self, prompt: Dict[str, Any], settings: Dict[str, Any] = None) -> ConnectorResult:
        pass

    @abstractmethod
    def status(self, job_id: str) -> ConnectorResult:
        pass

    def download(self, job_id: str, output_path: str = "") -> ConnectorResult:
        return ConnectorResult(job_id=job_id, status="downloaded")

    def cancel(self, job_id: str) -> bool:
        return False

    def _generate_job_id(self) -> str:
        import uuid
        return f"{self.platform_name}_{uuid.uuid4().hex[:12]}"

    def _build_result(self, status: str, **kwargs) -> ConnectorResult:
        return ConnectorResult(
            status=status,
            **kwargs
        )
