"""Workflow Builder - 统一生产工作流

PRD 强调：不要直接输出模型。
而是输出 Production Workflow，统一协调各种执行器。

输出格式示例：
Shot01 → AI → Kling
Shot02 → Unity → Capture
Shot03 → Eagle → Winner

最后统一输出：
- workflow.json
- 各模型专属工作流 JSON
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowStep:
    """工作流步骤"""
    step_id: str
    shot_id: str
    order: int
    action: str                  # generate / capture / fetch / edit / mix
    executor: str                # ai / unity / capture / eagle / winner / manual / mix
    executor_detail: str         # 具体模型或路径
    params: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    estimated_duration_sec: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "shot_id": self.shot_id,
            "order": self.order,
            "action": self.action,
            "executor": self.executor,
            "executor_detail": self.executor_detail,
            "params": self.params,
            "depends_on": self.depends_on,
            "estimated_duration_sec": self.estimated_duration_sec,
            "metadata": self.metadata,
        }


@dataclass
class ProductionWorkflow:
    """生产工作流"""
    workflow_id: str
    variant_id: str
    steps: list[WorkflowStep] = field(default_factory=list)
    total_steps: int = 0
    total_estimated_duration_sec: float = 0.0
    executors_used: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "variant_id": self.variant_id,
            "steps": [s.to_dict() for s in self.steps],
            "total_steps": self.total_steps,
            "total_estimated_duration_sec": self.total_estimated_duration_sec,
            "executors_used": self.executors_used,
            "metadata": self.metadata,
        }


class WorkflowBuilder:
    """统一生产工作流构建器"""

    # 源 → 动作 / 执行器
    SOURCE_TO_ACTION: dict[str, tuple[str, str]] = {
        "ai":         ("generate", "ai"),
        "image_anim": ("animate",  "ai"),
        "unity":      ("capture",  "unity"),
        "capture":    ("capture",  "obs"),
        "winner":     ("fetch",    "eagle"),
        "eagle":      ("fetch",    "eagle"),
        "manual":     ("edit",     "human"),
    }

    def __init__(self):
        self._map = {k: tuple(v) for k, v in self.SOURCE_TO_ACTION.items()}

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------
    def build(
        self,
        shot_list: Any,           # ShotList
        plan: Any,                # ProductionPlan
        strategy: Any,            # CreativeStrategy
    ) -> ProductionWorkflow:
        """构造统一生产工作流

        Args:
            shot_list: 镜头列表
            plan: 生产计划
            strategy: 创意策略
        """
        steps: list[WorkflowStep] = []
        executor_counter: dict[str, int] = {}
        total_duration = 0.0
        order = 1

        # 索引
        assign_map = {a.shot_id: a for a in plan.assignments}

        for shot in shot_list.shots:
            assign = assign_map.get(shot.shot_id)
            if not assign:
                continue

            source = assign.source
            action, executor = self._map.get(source, ("edit", "human"))
            executor_counter[executor] = executor_counter.get(executor, 0) + 1

            params = self._build_params(shot, assign, action, executor)
            est_dur = assign.estimated_time_sec
            total_duration += est_dur

            # 依赖：上一步骤
            depends_on = [steps[-1].step_id] if steps else []

            step = WorkflowStep(
                step_id=f"step_{order:03d}_{shot.shot_id}",
                shot_id=shot.shot_id,
                order=order,
                action=action,
                executor=executor,
                executor_detail=assign.model or assign.source_path or "",
                params=params,
                depends_on=depends_on,
                estimated_duration_sec=est_dur,
                metadata={
                    "shot_name": shot.name,
                    "source": source,
                    "confidence": assign.confidence,
                    "fallback": assign.fallback,
                },
            )
            steps.append(step)
            order += 1

        # 最后一个步骤：mix/composite
        if steps:
            mix_step = WorkflowStep(
                step_id=f"step_{order:03d}_mix",
                shot_id="all",
                order=order,
                action="mix",
                executor="editor",
                executor_detail="auto_compose",
                params={"timeline": f"timeline_{shot_list.variant_id}"},
                depends_on=[s.step_id for s in steps],
                estimated_duration_sec=60.0,
                metadata={"type": "final_compose"},
            )
            steps.append(mix_step)
            total_duration += 60.0
            executor_counter["editor"] = executor_counter.get("editor", 0) + 1

        return ProductionWorkflow(
            workflow_id=f"workflow_{shot_list.variant_id}",
            variant_id=shot_list.variant_id,
            steps=steps,
            total_steps=len(steps),
            total_estimated_duration_sec=round(total_duration, 1),
            executors_used=executor_counter,
            metadata={
                "hook": strategy.hook,
                "platform": strategy.platform,
                "plan_id": plan.plan_id,
            },
        )

    # ------------------------------------------------------------------
    # 按模型分组导出
    # ------------------------------------------------------------------
    def split_by_executor(
        self,
        workflow: ProductionWorkflow,
    ) -> dict[str, list[WorkflowStep]]:
        """按执行器分组"""
        groups: dict[str, list[WorkflowStep]] = {}
        for step in workflow.steps:
            groups.setdefault(step.executor, []).append(step)
        return groups

    def export_per_model(
        self,
        workflow: ProductionWorkflow,
        output_dir: str,
    ) -> dict[str, str]:
        """按模型导出专属工作流

        Returns:
            字典 {executor_name: file_path}
        """
        os.makedirs(output_dir, exist_ok=True)
        groups = self.split_by_executor(workflow)
        results: dict[str, str] = {}

        for executor, steps in groups.items():
            out_path = os.path.join(output_dir, f"workflow_{executor}.json")
            payload = {
                "workflow_id": workflow.workflow_id,
                "executor": executor,
                "step_count": len(steps),
                "total_estimated_duration_sec": sum(s.estimated_duration_sec for s in steps),
                "steps": [s.to_dict() for s in steps],
            }
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            results[executor] = out_path

        return results

    def export_main(
        self,
        workflow: ProductionWorkflow,
        output_path: str,
    ) -> str:
        """导出主 workflow.json"""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(workflow.to_dict(), f, ensure_ascii=False, indent=2)
        return output_path

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _build_params(
        self,
        shot: Any,
        assign: Any,
        action: str,
        executor: str,
    ) -> dict[str, Any]:
        """构造步骤参数"""
        params: dict[str, Any] = {
            "shot_id": shot.shot_id,
            "duration": shot.duration,
        }

        if action == "generate":
            params.update({
                "prompt": shot.prompt,
                "negative_prompt": shot.negative_prompt,
                "model": assign.model,
                "aspect_ratio": shot.metadata.get("aspect_ratio", "9:16") if hasattr(shot, "metadata") else "9:16",
                "guidance_scale": 7.5,
                "steps": 30,
            })
        elif action == "animate":
            params.update({
                "image_source": "v4.3_image",
                "model": assign.model,
                "duration": shot.duration,
            })
        elif action == "capture":
            params.update({
                "unity_scene": assign.source_path,
                "duration": shot.duration,
                "resolution": "1080x1920",
            })
        elif action == "fetch":
            params.update({
                "source_path": assign.source_path,
                "duration": shot.duration,
            })
        elif action == "edit":
            params.update({
                "instructions": "manual review required",
                "shot_description": shot.prompt,
            })

        return params

    # ------------------------------------------------------------------
    # 格式化
    # ------------------------------------------------------------------
    def format_as_text(self, workflow: ProductionWorkflow) -> str:
        """可读工作流"""
        lines = [
            f"# {workflow.workflow_id}",
            f"步骤数: {workflow.total_steps}",
            f"估算耗时: {workflow.total_estimated_duration_sec/60:.1f} 分钟",
            "",
            "## 执行器分布",
        ]
        for ex, n in workflow.executors_used.items():
            lines.append(f"- {ex}: {n} 步")
        lines.append("")
        lines.append("## 步骤详情")
        for step in workflow.steps:
            lines.append(
                f"{step.order:02d}. [{step.action}] {step.executor} "
                f"({step.executor_detail}) - {step.shot_id} - "
                f"{step.estimated_duration_sec:.0f}s"
            )
        return "\n".join(lines)
