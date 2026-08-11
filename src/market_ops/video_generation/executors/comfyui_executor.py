"""ComfyUI Executor - Mock"""
import time
from typing import Dict, Any
from .base_executor import BaseExecutor, ExecutorResult


class ComfyUIExecutor(BaseExecutor):
    platform_name = "comfyui"

    def submit(self, prompt: Dict[str, Any], settings: Dict[str, Any] = None) -> ExecutorResult:
        job_id = self._generate_job_id()
        return ExecutorResult(
            job_id=job_id,
            status="submitted",
            metadata={
                "platform": "comfyui",
                "workflow": prompt,
                "settings": settings or {},
                "submitted_at": time.time(),
            }
        )

    def get_status(self, job_id: str) -> ExecutorResult:
        return ExecutorResult(
            job_id=job_id,
            status="completed",
            video_url=f"http://localhost:8188/output/{job_id}.png",
            metadata={
                "steps": 20,
                "cfg": 7.0,
                "sampler": "DPM++ 2M SDE Karras",
            }
        )
