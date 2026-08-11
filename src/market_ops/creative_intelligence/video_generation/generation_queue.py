"""Generation Queue - 批量生成队列

支持批量生成广告素材，参数变化：
- seed 变化
- camera 变化
- action 变化
"""
from __future__ import annotations

import copy
import random
from typing import Any

from ..video_director.models import VideoCreativePlan
from .models import BatchConfig


class GenerationQueue:
    """批量生成队列"""

    def __init__(self):
        self.plans: list[dict[str, Any]] = []

    def enqueue(
        self,
        base_plan: VideoCreativePlan,
        batch_config: BatchConfig | None = None,
    ) -> list[dict[str, Any]]:
        """将单个 Plan 扩展为批量任务队列

        Args:
            base_plan: 基础创意方案
            batch_config: 批量配置（seed/camera/action 变化）

        Returns:
            任务列表，每个任务包含 plan + seed + variation info
        """
        if batch_config is None:
            batch_config = BatchConfig(count=1)

        tasks: list[dict[str, Any]] = []

        # 确定种子列表
        seeds = batch_config.seeds if batch_config.seeds else [
            random.randint(10000, 99999) for _ in range(batch_config.count)
        ]

        # 确定 camera 变化
        cameras = batch_config.camera_variations if batch_config.camera_variations else [""]

        # 确定 action 变化
        actions = batch_config.action_variations if batch_config.action_variations else [""]

        idx = 0
        for seed in seeds:
            for cam in cameras:
                for act in actions:
                    idx += 1
                    task = self._create_task(base_plan, seed, cam, act, idx)
                    tasks.append(task)

        return tasks

    def _create_task(
        self,
        base_plan: VideoCreativePlan,
        seed: int,
        camera_var: str,
        action_var: str,
        index: int,
    ) -> dict[str, Any]:
        """创建单个任务"""
        plan = copy.deepcopy(base_plan)
        plan.video_id = f"{base_plan.video_id}_v{index:03d}"

        # 应用 camera 变化
        if camera_var and plan.camera_plan:
            plan.camera_plan[0]["camera"] = camera_var
            plan.camera_plan[0]["purpose"] = f"variation: {camera_var}"

        # 应用 action 变化
        if action_var and plan.action_plan:
            plan.action_plan[0]["action"] = action_var

        # 更新 metadata
        plan.metadata["variation_index"] = index
        plan.metadata["seed"] = seed
        plan.metadata["camera_variation"] = camera_var
        plan.metadata["action_variation"] = action_var

        return {
            "plan": plan,
            "seed": seed,
            "video_id": plan.video_id,
            "index": index,
        }

    def estimate_time(self, task_count: int, avg_time_per_video: int = 300) -> dict[str, Any]:
        """估算生成时间

        Args:
            task_count: 任务数量
            avg_time_per_video: 单个视频平均生成时间（秒）

        Returns:
            {"total_seconds": int, "human_readable": str}
        """
        total = task_count * avg_time_per_video
        hours = total // 3600
        minutes = (total % 3600) // 60
        secs = total % 60

        parts: list[str] = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs}s")

        return {
            "total_seconds": total,
            "human_readable": " ".join(parts),
            "task_count": task_count,
            "avg_time_per_video": avg_time_per_video,
        }
