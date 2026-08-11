"""Veo Executor - Mock"""
import time
from typing import Dict, Any
from .base_executor import BaseExecutor, ExecutorResult


class VeoExecutor(BaseExecutor):
    platform_name = "veo"

    def submit(self, prompt: Dict[str, Any], settings: Dict[str, Any] = None) -> ExecutorResult:
        job_id = self._generate_job_id()
        return ExecutorResult(
            job_id=job_id,
            status="submitted",
            metadata={
                "platform": "veo",
                "prompt": prompt,
                "settings": settings or {},
                "submitted_at": time.time(),
            }
        )

    def get_status(self, job_id: str) -> ExecutorResult:
        return ExecutorResult(
            job_id=job_id,
            status="completed",
            video_url=f"https://veo.example.com/videos/{job_id}.mp4",
            metadata={
                "duration": 8,
                "resolution": "1080p",
                "fps": 24,
            }
        )
