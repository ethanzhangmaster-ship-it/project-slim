"""Production Dashboard - 生产概览

提供：
- 总览统计
- 各 variant 生产状态
- 素材来源分布
- AI 模型任务分布
- 性能反馈
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from .production_memory import ProductionMemory
from .production_api import CreativeProductionAPI


@dataclass
class DashboardSummary:
    """Dashboard 摘要"""
    total_variants: int = 0
    total_shots: int = 0
    total_duration_sec: float = 0.0
    total_estimated_cost: float = 0.0
    source_distribution: dict[str, int] = field(default_factory=dict)
    executor_distribution: dict[str, int] = field(default_factory=dict)
    model_distribution: dict[str, int] = field(default_factory=dict)
    platform_distribution: dict[str, int] = field(default_factory=dict)
    hook_distribution: dict[str, int] = field(default_factory=dict)
    priority_distribution: dict[str, int] = field(default_factory=dict)
    review_required: int = 0
    avg_confidence: float = 0.0
    performance_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_variants": self.total_variants,
            "total_shots": self.total_shots,
            "total_duration_sec": self.total_duration_sec,
            "total_estimated_cost": self.total_estimated_cost,
            "source_distribution": self.source_distribution,
            "executor_distribution": self.executor_distribution,
            "model_distribution": self.model_distribution,
            "platform_distribution": self.platform_distribution,
            "hook_distribution": self.hook_distribution,
            "priority_distribution": self.priority_distribution,
            "review_required": self.review_required,
            "avg_confidence": self.avg_confidence,
            "performance_summary": self.performance_summary,
        }


class ProductionDashboard:
    """生产概览 Dashboard"""

    def __init__(self, api: CreativeProductionAPI | None = None):
        self.api = api or CreativeProductionAPI()
        self._summary: DashboardSummary | None = None
        self._records: list[dict[str, Any]] = []

    def record(self, output: Any) -> None:
        """记录一次生产输出"""
        rec = {
            "variant_id": output.variant_id,
            "hook": output.strategy.hook,
            "platform": output.strategy.platform,
            "priority": output.strategy.priority,
            "total_shots": output.shot_list.total_shots,
            "total_duration": output.shot_list.total_duration,
            "estimated_cost": output.plan.total_estimated_cost,
            "review_required": output.plan.requires_human_review_count,
            "avg_confidence": self._avg_confidence(output.plan),
            "sources": dict(output.plan.source_summary),
            "executors": dict(output.workflow.executors_used),
            "models": {m: len(tasks) for m, tasks in output.model_tasks.items()},
        }
        self._records.append(rec)

    def summary(self) -> DashboardSummary:
        """汇总所有记录"""
        if not self._records:
            return DashboardSummary()

        total_variants = len(self._records)
        total_shots = sum(r["total_shots"] for r in self._records)
        total_duration = sum(r["total_duration"] for r in self._records)
        total_cost = sum(r["estimated_cost"] for r in self._records)
        review_required = sum(r["review_required"] for r in self._records)
        avg_conf = sum(r["avg_confidence"] for r in self._records) / total_variants

        # 来源分布
        source_dist: dict[str, int] = {}
        for r in self._records:
            for k, v in r["sources"].items():
                source_dist[k] = source_dist.get(k, 0) + v

        # 执行器分布
        executor_dist: dict[str, int] = {}
        for r in self._records:
            for k, v in r["executors"].items():
                executor_dist[k] = executor_dist.get(k, 0) + v

        # 模型分布
        model_dist: dict[str, int] = {}
        for r in self._records:
            for k, v in r["models"].items():
                model_dist[k] = model_dist.get(k, 0) + v

        # 平台
        platform_dist: dict[str, int] = {}
        for r in self._records:
            platform_dist[r["platform"]] = platform_dist.get(r["platform"], 0) + 1

        # Hook
        hook_dist: dict[str, int] = {}
        for r in self._records:
            hook_dist[r["hook"]] = hook_dist.get(r["hook"], 0) + 1

        # 优先级
        prio_dist: dict[str, int] = {}
        for r in self._records:
            p = f"P{r['priority']}"
            prio_dist[p] = prio_dist.get(p, 0) + 1

        # 性能
        perf = self.api.get_stats()

        return DashboardSummary(
            total_variants=total_variants,
            total_shots=total_shots,
            total_duration_sec=round(total_duration, 1),
            total_estimated_cost=round(total_cost, 2),
            source_distribution=source_dist,
            executor_distribution=executor_dist,
            model_distribution=model_dist,
            platform_distribution=platform_dist,
            hook_distribution=hook_dist,
            priority_distribution=prio_dist,
            review_required=review_required,
            avg_confidence=round(avg_conf, 3),
            performance_summary=perf,
        )

    def render(self) -> str:
        """渲染为文本 Dashboard"""
        s = self.summary()
        if s.total_variants == 0:
            return "Dashboard: 暂无数据"

        lines = [
            "=" * 60,
            f"  Facebook Creative Production Dashboard (V4.3.1)",
            "=" * 60,
            "",
            f"## 总体概览",
            f"- 创意变体: {s.total_variants}",
            f"- 总镜头数: {s.total_shots}",
            f"- 总时长: {s.total_duration_sec/60:.1f} 分钟",
            f"- 估算成本: ${s.total_estimated_cost:.2f}",
            f"- 平均置信度: {s.avg_confidence:.2f}",
            f"- 需人工审核: {s.review_required} 镜头",
            "",
            f"## 素材来源分布",
        ]
        for src, n in s.source_distribution.items():
            pct = 100 * n / max(1, s.total_shots)
            lines.append(f"  {src:15s} : {n:4d} 镜头 ({pct:5.1f}%)")
        lines.append("")

        lines.append(f"## 执行器分布")
        for ex, n in s.executor_distribution.items():
            lines.append(f"  {ex:15s} : {n:4d} 步骤")
        lines.append("")

        if s.model_distribution:
            lines.append(f"## AI 模型分布")
            for m, n in s.model_distribution.items():
                lines.append(f"  {m:15s} : {n:4d} 任务")
            lines.append("")

        lines.append(f"## 平台分布")
        for p, n in s.platform_distribution.items():
            lines.append(f"  {p:15s} : {n:4d} 创意")
        lines.append("")

        lines.append(f"## Hook 类型分布")
        for h, n in s.hook_distribution.items():
            lines.append(f"  {h:15s} : {n:4d} 创意")
        lines.append("")

        lines.append(f"## 优先级分布")
        for p, n in sorted(s.priority_distribution.items()):
            lines.append(f"  {p:15s} : {n:4d} 创意")
        lines.append("")

        if s.performance_summary:
            lines.append(f"## 历史表现")
            for k, v in s.performance_summary.items():
                lines.append(f"  {k:20s} : {v}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    def _avg_confidence(self, plan: Any) -> float:
        if not plan.assignments:
            return 0.0
        return sum(a.confidence for a in plan.assignments) / len(plan.assignments)
