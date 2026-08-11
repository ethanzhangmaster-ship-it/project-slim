"""V4.1 Task Executor — executes planner output."""

from __future__ import annotations

from typing import Any


class TaskExecutor:
    """Executes planner output tasks."""

    def execute(self, plan: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "planned",
            "plan": plan,
            "message": "Task ready for generation",
        }

    def execute_image(self, plan: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "image_plan_ready",
            "prompt": plan.get("prompt", {}),
            "composition": plan.get("composition", {}),
        }

    def execute_video(self, plan: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "video_plan_ready",
            "prompt": plan.get("prompt", {}),
            "camera": plan.get("camera", {}),
            "motion": plan.get("motion", {}),
            "subtitle": plan.get("subtitle", {}),
            "music": plan.get("music", {}),
        }