"""Generation Scheduler - 生成调度器"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from .cost_controller import CostController
from .retry_manager import RetryManager


@dataclass
class GenerationTask:
    """生成任务"""
    shot_id: str
    platform: str
    prompt: str
    duration: float
    status: str = "pending"
    attempt: int = 0
    error: str = ""


@dataclass
class GenerationPlan:
    """生成计划"""
    variant_id: str
    tasks: List[GenerationTask] = field(default_factory=list)
    mode: str = "sequential"
    parallel_count: int = 4


class GenerationScheduler:
    """生成调度器"""

    def __init__(self, mode: str = "sequential", parallel_count: int = 4):
        self.mode = mode
        self.parallel_count = parallel_count
        self.retry_manager = RetryManager(max_retries=3)
        self.cost_controller = CostController()

    def create_plan(self, variant_id: str, platform_prompts: Dict[str, Any]) -> GenerationPlan:
        """创建生成计划"""
        plan = GenerationPlan(variant_id=variant_id, mode=self.mode)

        for shot_id, prompts in platform_prompts.items():
            for platform, prompt_data in prompts.items():
                task = GenerationTask(
                    shot_id=shot_id,
                    platform=platform,
                    prompt=prompt_data.get("prompt", ""),
                    duration=prompt_data.get("duration", 10),
                )
                plan.tasks.append(task)

        return plan

    def execute(self, plan: GenerationPlan, generate_func: Callable) -> Dict[str, Any]:
        """执行生成计划"""
        results = {"success": [], "failed": [], "logs": []}

        if self.mode == "sequential":
            for task in plan.tasks:
                result = self._execute_task(task, generate_func)
                if result["success"]:
                    results["success"].append(result)
                else:
                    results["failed"].append(result)
                results["logs"].append(result["log"])
        else:
            chunk_size = self.parallel_count
            for i in range(0, len(plan.tasks), chunk_size):
                chunk = plan.tasks[i:i + chunk_size]
                chunk_results = []
                for task in chunk:
                    result = self._execute_task(task, generate_func)
                    chunk_results.append(result)
                    results["logs"].append(result["log"])
                results["success"].extend([r for r in chunk_results if r["success"]])
                results["failed"].extend([r for r in chunk_results if not r["success"]])

        return results

    def _execute_task(self, task: GenerationTask, generate_func: Callable) -> Dict[str, Any]:
        """执行单个任务"""
        log = []

        def wrapped_func():
            log.append(f"Generating {task.shot_id} on {task.platform}")
            return generate_func(task.platform, task.shot_id, task.prompt, task.duration)

        result = self.retry_manager.execute(wrapped_func)

        if result.success:
            task.status = "success"
            self.cost_controller.add_record(task.platform, task.shot_id, task.duration, "1080p")
            log.append(f"Success: {task.shot_id}")
            return {"shot_id": task.shot_id, "platform": task.platform, "success": True, "log": "\n".join(log)}
        else:
            task.status = "failed"
            task.error = result.last_error
            log.append(f"Failed: {task.shot_id} - {result.last_error}")
            return {"shot_id": task.shot_id, "platform": task.platform, "success": False, "error": result.last_error, "log": "\n".join(log)}

    def save_plan(self, plan: GenerationPlan, path: str) -> None:
        """保存生成计划"""
        data = {
            "variant_id": plan.variant_id,
            "mode": plan.mode,
            "parallel_count": self.parallel_count,
            "tasks": [
                {
                    "shot_id": t.shot_id,
                    "platform": t.platform,
                    "duration": t.duration,
                    "status": t.status,
                }
                for t in plan.tasks
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def save_logs(self, logs: List[str], path: str) -> None:
        """保存生成日志"""
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(logs))