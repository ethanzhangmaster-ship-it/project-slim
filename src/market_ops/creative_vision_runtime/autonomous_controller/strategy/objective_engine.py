"""E11.8.1 — Objective Engine。

将 feedback / knowledge / population 输入转换为 EvolutionObjective 列表。

核心职责：
  1. 分析当前性能指标（从 feedback 提取 CTR/ROI/CVR 等）
  2. 识别弱点（从 knowledge 分析 mutation 成功率）
  3. 检测种群问题（diversity 塌缩、avg_fitness 下降）
  4. 生成优先级排序的 EvolutionObjective
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    EvolutionObjective,
    Horizon,
    MutationFocus,
)

logger = logging.getLogger(__name__)

# 默认目标值
DEFAULT_TARGETS: dict[str, float] = {
    "CTR": 0.05,
    "ROI": 1.5,
    "Retention": 0.40,
    "Diversity": 0.3,
    "CVR": 0.10,
}

# 指标 → 对应的聚焦维度
METRIC_TO_FOCUS: dict[str, MutationFocus] = {
    "CTR": MutationFocus.HOOK,
    "ROI": MutationFocus.REWARD,
    "Retention": MutationFocus.GAMEPLAY,
    "CVR": MutationFocus.PACING,
    "Diversity": MutationFocus.FULL,
}


class ObjectiveEngine:
    """目标引擎。

    将多源输入转化为一组 EvolutionObjective。

    Attributes:
        targets: 自定义目标值（可选，默认使用 DEFAULT_TARGETS）
    """

    def __init__(self, targets: dict[str, float] | None = None) -> None:
        self._targets: dict[str, float] = {**DEFAULT_TARGETS, **(targets or {})}

    # ── 主入口 ──────────────────────────────────────────

    def build(
        self,
        feedback: dict[str, Any] | None = None,
        knowledge: dict[str, Any] | None = None,
        population: dict[str, Any] | None = None,
    ) -> list[EvolutionObjective]:
        """从多源输入构建 EvolutionObjective 列表。

        Args:
            feedback:   反馈数据，含 metrics 摘要
            knowledge:  知识图谱数据，含 mutation 成功率
            population: 种群状态，含 diversity 和 avg_fitness

        Returns:
            EvolutionObjective 列表（按 priority 降序）
        """
        objectives: list[EvolutionObjective] = []

        # 1. 从 feedback 提取性能目标
        if feedback:
            objectives.extend(self._build_from_feedback(feedback))

        # 2. 从 knowledge 提取弱点目标
        if knowledge:
            objectives.extend(self._build_from_knowledge(knowledge))

        # 3. 从 population 提取种群目标
        if population:
            objectives.extend(self._build_from_population(population))

        # 4. 按 priority 降序排序
        objectives.sort(key=lambda o: o.priority, reverse=True)

        return objectives

    def build_single(
        self,
        feedback: dict[str, Any] | None = None,
        knowledge: dict[str, Any] | None = None,
        population: dict[str, Any] | None = None,
    ) -> EvolutionObjective | None:
        """构建单一最高优先级目标。

        Returns:
            最高优先级目标，无目标时返回 None
        """
        objectives = self.build(feedback, knowledge, population)
        return objectives[0] if objectives else None

    # ── 内部构建方法 ────────────────────────────────────

    def _build_from_feedback(
        self, feedback: dict[str, Any]
    ) -> list[EvolutionObjective]:
        """从反馈数据构建性能目标。

        feedback 格式：
          {
            "metrics": {
                "CTR": 0.035,
                "ROI": 1.2,
                "CVR": 0.08,
            },
            "sample_count": 50,
          }
        """
        objectives: list[EvolutionObjective] = []
        metrics = feedback.get("metrics", {})
        sample_count = feedback.get("sample_count", 0)

        # 样本不足，降低置信度
        confidence_factor = min(1.0, sample_count / 100.0) if sample_count > 0 else 0.3

        for metric_name in ("CTR", "ROI", "CVR"):
            current = metrics.get(metric_name)
            if current is None:
                continue

            target = self._targets.get(metric_name, 0)
            if target == 0:
                continue

            gap = target - current
            if gap <= 0:
                continue  # 已达目标

            gap_pct = gap / target
            priority = min(1.0, gap_pct * confidence_factor * 1.5)

            if priority < 0.1:
                continue  # 差距太小，忽略

            horizon = self._infer_horizon(gap_pct)
            focus = METRIC_TO_FOCUS.get(metric_name, MutationFocus.FULL)

            objectives.append(
                EvolutionObjective(
                    metric=metric_name,
                    current_value=current,
                    target_value=target,
                    priority=round(priority, 3),
                    horizon=horizon,
                    reason=f"{metric_name} underperforms: {current:.3f} vs target {target:.3f} (gap={gap_pct:.1%})",
                    metadata={
                        "source": "feedback",
                        "gap_pct": round(gap_pct, 4),
                        "sample_count": sample_count,
                        "focus": focus.value,
                    },
                )
            )

        return objectives

    def _build_from_knowledge(
        self, knowledge: dict[str, Any]
    ) -> list[EvolutionObjective]:
        """从知识图谱数据构建弱点目标。

        knowledge 格式：
          {
            "mutation_performance": {
                "hook": {"success_rate": 0.8, "avg_gain": 15.0},
                "visual": {"success_rate": 0.3, "avg_gain": -5.0},
                "gameplay": {"success_rate": 0.6, "avg_gain": 8.0},
            },
            "overall_success_rate": 0.55,
          }
        """
        objectives: list[EvolutionObjective] = []
        perf = knowledge.get("mutation_performance", {})

        for mutation_type, data in perf.items():
            success_rate = data.get("success_rate", 0.5)
            avg_gain = data.get("avg_gain", 0.0)

            # 低成功率 → 高优先级修复目标
            if success_rate < 0.4:
                priority = (0.4 - success_rate) * 2.0
                priority = min(1.0, priority)

                objectives.append(
                    EvolutionObjective(
                        metric=f"mutation:{mutation_type}",
                        current_value=success_rate,
                        target_value=0.6,
                        priority=round(priority, 3),
                        horizon=Horizon.MEDIUM,
                        reason=f"Low mutation success rate for '{mutation_type}': {success_rate:.0%} (avg_gain={avg_gain:+.1f})",
                        metadata={
                            "source": "knowledge",
                            "mutation_type": mutation_type,
                            "success_rate": success_rate,
                            "avg_gain": avg_gain,
                            "focus": mutation_type,
                        },
                    )
                )

        return objectives

    def _build_from_population(
        self, population: dict[str, Any]
    ) -> list[EvolutionObjective]:
        """从种群状态构建种群目标。

        population 格式：
          {
            "diversity_score": 0.15,
            "avg_fitness": 45.0,
            "total_count": 8,
            "elite_count": 1,
          }
        """
        objectives: list[EvolutionObjective] = []

        diversity = population.get("diversity_score", 0.5)
        avg_fitness = population.get("avg_fitness", 50.0)
        total_count = population.get("total_count", 0)

        # 多样性塌缩
        if diversity < 0.2:
            priority = (0.2 - diversity) * 5.0
            priority = min(1.0, priority)

            objectives.append(
                EvolutionObjective(
                    metric="Diversity",
                    current_value=diversity,
                    target_value=self._targets.get("Diversity", 0.3),
                    priority=round(priority, 3),
                    horizon=Horizon.SHORT,
                    reason=f"Population diversity collapse: {diversity:.2f} (threshold=0.2)",
                    metadata={
                        "source": "population",
                        "diversity_score": diversity,
                        "total_count": total_count,
                        "focus": MutationFocus.FULL.value,
                    },
                )
            )

        # 平均适应度低
        if avg_fitness < 50.0 and total_count >= 3:
            priority = (50.0 - avg_fitness) / 100.0
            priority = min(1.0, priority)

            if priority >= 0.1:
                objectives.append(
                    EvolutionObjective(
                        metric="avg_fitness",
                        current_value=avg_fitness,
                        target_value=70.0,
                        priority=round(priority, 3),
                        horizon=Horizon.MEDIUM,
                        reason=f"Population average fitness low: {avg_fitness:.1f} (target=70.0)",
                        metadata={
                            "source": "population",
                            "avg_fitness": avg_fitness,
                            "elite_count": population.get("elite_count", 0),
                            "focus": MutationFocus.FULL.value,
                        },
                    )
                )

        return objectives

    # ── 辅助方法 ─────────────────────────────────────────

    @staticmethod
    def _infer_horizon(gap_pct: float) -> Horizon:
        """根据差距推断时间范围。"""
        if gap_pct > 0.5:
            return Horizon.LONG
        elif gap_pct > 0.2:
            return Horizon.MEDIUM
        else:
            return Horizon.SHORT

    def get_default_target(self, metric: str) -> float:
        """获取指标默认目标值。"""
        return self._targets.get(metric, 0.0)

    def set_target(self, metric: str, value: float) -> None:
        """设置自定义目标值。"""
        self._targets[metric] = value

    def __repr__(self) -> str:
        return f"ObjectiveEngine(targets={len(self._targets)})"