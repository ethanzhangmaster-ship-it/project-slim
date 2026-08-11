"""Runway Connector"""
import time
import random
from typing import Dict, Any
from .base_connector import BaseConnector, ConnectorResult


class RunwayConnector(BaseConnector):
    platform_name = "runway"

    def __init__(self, api_key: str = "", api_base: str = ""):
        super().__init__(api_key, api_base)
        self._jobs: Dict[str, Dict[str, Any]] = {}

    def submit(self, prompt: Dict[str, Any], settings: Dict[str, Any] = None) -> ConnectorResult:
        job_id = self._generate_job_id()
        duration = prompt.get("duration", 15)

        self._jobs[job_id] = {
            "status": "submitted",
            "prompt": prompt,
            "duration": duration,
            "submitted_at": time.time(),
            "estimated_completion": time.time() + duration * 3,
        }

        return ConnectorResult(
            job_id=job_id,
            status="submitted",
            metadata={
                "platform": "runway",
                "model": "gen-4",
                "duration": duration,
            }
        )

    def status(self, job_id: str) -> ConnectorResult:
        if job_id not in self._jobs:
            return ConnectorResult(job_id=job_id, status="not_found", error="Job not found")

        job = self._jobs[job_id]

        if time.time() < job["estimated_completion"]:
            progress = min(100, (time.time() - job["submitted_at"]) / (job["estimated_completion"] - job["submitted_at"]) * 100)
            return ConnectorResult(
                job_id=job_id,
                status="generating",
                metadata={"progress": round(progress, 1)}
            )

        if random.random() < 0.1:
            self._jobs[job_id]["status"] = "failed"
            return ConnectorResult(
                job_id=job_id,
                status="failed",
                error="Timeout"
            )

        self._jobs[job_id]["status"] = "completed"
        return ConnectorResult(
            job_id=job_id,
            status="completed",
            video_url=f"https://api.runwayml.com/v1/videos/{job_id}.mp4",
            metadata={
                "duration": job["duration"],
                "resolution": "1080p",
                "fps": 24,
            }
        )
