"""E12.7.3 — Objective Engine。

目标引擎 —— 确定当前最重要的增长目标。

职责:
  1. 分析 GrowthObservation
  2. 生成候选目标
  3. 按优先级排序
  4. 输出最优 StrategyObjective

优先级公式:
  composite_score = priority × 0.40 + urgency × 0.35 + impact × 0.25
"""

from __future__ import annotations

from typing import Any

from ..agent.models import GrowthObservation, ObservationSeverity
from .models import StrategyObjective


# 目标模板
# 格式: (metric, 触发条件, 基础优先级, 基础紧急度, 基础影响, 描述)
_OBJECTIVE_TEMPLATES: list[dict[str, Any]] = [
    {
        "metric": "roas",
        "condition": lambda o: o.metrics.roas < 0.50,
        "base_priority": 0.95,
        "base_urgency": 0.90,
        "base_impact": 0.85,
        "description_template": "Recover ROAS from {current} to 0.80",
        "target_calc": lambda o: max(0.80, o.metrics.roas * 1.6),
    },
    {
        "metric": "roas",
        "condition": lambda o: o.metrics.roas < 0.80,
        "base_priority": 0.80,
        "base_urgency": 0.70,
        "base_impact": 0.70,
        "description_template": "Improve ROAS from {current} to 1.00",
        "target_calc": lambda o: max(1.0, o.metrics.roas * 1.3),
    },
    {
        "metric": "ctr",
        "condition": lambda o: o.metrics.ctr < 0.01,
        "base_priority": 0.75,
        "base_urgency": 0.65,
        "base_impact": 0.60,
        "description_template": "Improve CTR from {current} to 0.02",
        "target_calc": lambda o: max(0.02, o.metrics.ctr * 2.0),
    },
    {
        "metric": "cpi",
        "condition": lambda o: o.metrics.cpi > 5.0,
        "base_priority": 0.70,
        "base_urgency": 0.60,
        "base_impact": 0.55,
        "description_template": "Reduce CPI from {current} to 3.00",
        "target_calc": lambda o: min(3.0, o.metrics.cpi * 0.6),
    },
    {
        "metric": "fatigue",
        "condition": lambda o: o.creative_state.is_fatigued,
        "base_priority": 0.78,
        "base_urgency": 0.72,
        "base_impact": 0.65,
        "description_template": "Reduce creative fatigue from {current} to 0.30",
        "target_calc": lambda o: 0.30,
    },
    {
        "metric": "diversity",
        "condition": lambda o: o.creative_state.diversity_score < 0.30,
        "base_priority": 0.65,
        "base_urgency": 0.55,
        "base_impact": 0.50,
        "description_template": "Increase creative diversity from {current} to 0.60",
        "target_calc": lambda o: 0.60,
    },
    {
        "metric": "retention",
        "condition": lambda o: o.metrics.retention_d7 < 0.15,
        "base_priority": 0.60,
        "base_urgency": 0.50,
        "base_impact": 0.55,
        "description_template": "Improve D7 retention from {current} to 0.20",
        "target_calc": lambda o: 0.20,
    },
    {
        "metric": "scale",
        "condition": lambda o: o.metrics.roas >= 1.0 and not o.creative_state.is_fatigued,
        "base_priority": 0.55,
        "base_urgency": 0.40,
        "base_impact": 0.60,
        "description_template": "Scale spending while maintaining ROAS >= 1.0",
        "target_calc": lambda o: o.metrics.spend * 1.5,
    },
]


class ObjectiveEngine:
    """目标引擎。

    确定当前最重要的增长目标。
    """

    def __init__(self) -> None:
        self._templates = list(_OBJECTIVE_TEMPLATES)

    def analyze(
        self, observation: GrowthObservation
    ) -> list[StrategyObjective]:
        """分析观察，生成候选目标。

        Args:
            observation: 增长观察

        Returns:
            目标列表（按 composite_score 降序）
        """
        objectives: list[StrategyObjective] = []

        for template in self._templates:
            try:
                if template["condition"](observation):
                    current_value = self._get_current_value(observation, template["metric"])
                    target_value = template["target_calc"](observation)

                    # 调整优先级和紧急度（基于严重程度）
                    severity_boost = self._severity_boost(observation.severity)
                    priority = min(1.0, template["base_priority"] + severity_boost)
                    urgency = min(1.0, template["base_urgency"] + severity_boost)

                    description = template["description_template"].format(
                        current=round(current_value, 4),
                    )

                    objective = StrategyObjective(
                        product_id=observation.product_id,
                        metric=template["metric"],
                        current_value=round(current_value, 4),
                        target_value=round(target_value, 4),
                        priority=round(priority, 4),
                        urgency=round(urgency, 4),
                        impact=round(template["base_impact"], 4),
                        description=description,
                    )
                    objectives.append(objective)
            except Exception:
                continue

        # 按 composite_score 降序排序
        objectives.sort(key=lambda o: o.composite_score, reverse=True)
        return objectives

    def get_top_objective(
        self, observation: GrowthObservation
    ) -> StrategyObjective | None:
        """获取最优目标。"""
        objectives = self.analyze(observation)
        return objectives[0] if objectives else None

    def get_objectives_by_metric(
        self, observation: GrowthObservation
    ) -> dict[str, list[StrategyObjective]]:
        """按指标分组目标。"""
        objectives = self.analyze(observation)
        result: dict[str, list[StrategyObjective]] = {}
        for o in objectives:
            result.setdefault(o.metric, []).append(o)
        return result

    def _get_current_value(
        self, observation: GrowthObservation, metric: str
    ) -> float:
        """获取指标的当前值。"""
        metric_map: dict[str, float] = {
            "roas": observation.metrics.roas,
            "ctr": observation.metrics.ctr,
            "cpi": observation.metrics.cpi,
            "fatigue": observation.creative_state.fatigue_score,
            "diversity": observation.creative_state.diversity_score,
            "retention": observation.metrics.retention_d7,
            "scale": observation.metrics.spend,
        }
        return metric_map.get(metric, 0.0)

    def _severity_boost(self, severity: ObservationSeverity) -> float:
        """严重程度加成。"""
        boosts = {
            ObservationSeverity.NORMAL: 0.0,
            ObservationSeverity.WARNING: 0.05,
            ObservationSeverity.CRITICAL: 0.10,
            ObservationSeverity.FATAL: 0.15,
        }
        return boosts.get(severity, 0.0)

    def add_template(self, template: dict[str, Any]) -> None:
        """添加自定义目标模板。"""
        self._templates.append(template)

    @property
    def template_count(self) -> int:
        return len(self._templates)

    def __repr__(self) -> str:
        return f"ObjectiveEngine(templates={self.template_count})"