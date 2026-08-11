"""E12.7.2 — Decision Adapter。

决策适配器 —— 将 AI 推理转换为可执行的 GrowthAction。

职责:
  1. 接收 GrowthHypothesis
  2. 转换为 AgentDecision
  3. 映射到 E12.6.1 Meta Decision Engine 兼容格式
  4. 生成 GrowthAction 参数
"""

from __future__ import annotations

from typing import Any

from .models import AgentDecision, GrowthHypothesis


# 假设类别 → 动作类型映射
_HYPOTHESIS_TO_ACTION: dict[str, dict[str, Any]] = {
    "creative_fatigue": {
        "action_type": "mutate_dna",
        "priority": 70,
    },
    "creative_diversity_low": {
        "action_type": "generate_creative",
        "priority": 60,
    },
    "winner_scarcity": {
        "action_type": "start_experiment",
        "priority": 65,
    },
    "roas_decline": {
        "action_type": "change_allocation",
        "priority": 75,
    },
    "roas_critical": {
        "action_type": "decrease_budget",
        "priority": 95,
    },
    "ctr_decline": {
        "action_type": "mutate_dna",
        "priority": 60,
    },
    "cpi_inflation": {
        "action_type": "change_allocation",
        "priority": 65,
    },
    "market_decline": {
        "action_type": "sunset_product",
        "priority": 50,
    },
    "high_competition": {
        "action_type": "generate_creative",
        "priority": 55,
    },
    "combined_fatigue_roas": {
        "action_type": "decrease_budget",
        "priority": 90,
    },
}


class DecisionAdapter:
    """决策适配器。

    将 AI 假设转换为可执行决策。
    """

    def __init__(self) -> None:
        self._action_map = dict(_HYPOTHESIS_TO_ACTION)
        self._decisions: list[AgentDecision] = []

    def adapt(
        self,
        hypothesis: GrowthHypothesis,
        observation_id: str = "",
    ) -> AgentDecision:
        """将假设适配为决策。

        Args:
            hypothesis:     增长假设
            observation_id: 关联观察 ID

        Returns:
            AgentDecision
        """
        mapping = self._action_map.get(
            hypothesis.root_cause_category,
            {"action_type": "custom", "priority": 50},
        )

        # 构建参数
        parameters: dict[str, Any] = {
            "hypothesis_id": hypothesis.hypothesis_id,
            "problem": hypothesis.problem,
            "root_cause": hypothesis.root_cause,
            "expected_impact": hypothesis.expected_impact,
            "recommended_actions": hypothesis.recommended_actions,
        }

        # 计算优先级（基于置信度和基础优先级）
        base_priority = mapping.get("priority", 50)
        confidence_boost = int(hypothesis.confidence * 10)
        priority = min(100, base_priority + confidence_boost)

        decision = AgentDecision(
            product_id=hypothesis.metadata.get("product_id", ""),
            action_type=mapping["action_type"],
            target_module=hypothesis.target_module,
            parameters=parameters,
            confidence=hypothesis.confidence,
            reasoning=hypothesis.rationale,
            hypothesis_id=hypothesis.hypothesis_id,
            observation_id=observation_id,
            priority=priority,
        )

        self._decisions.append(decision)
        return decision

    def adapt_batch(
        self,
        hypotheses: list[GrowthHypothesis],
        observation_id: str = "",
    ) -> list[AgentDecision]:
        """批量适配假设。

        Args:
            hypotheses:     假设列表
            observation_id: 关联观察 ID

        Returns:
            决策列表（按优先级降序）
        """
        decisions = [
            self.adapt(h, observation_id) for h in hypotheses
        ]
        decisions.sort(key=lambda d: d.priority, reverse=True)
        return decisions

    def add_mapping(
        self, category: str, mapping: dict[str, Any]
    ) -> None:
        """添加自定义映射。"""
        self._action_map[category] = mapping

    def get_history(self, limit: int = 100) -> list[AgentDecision]:
        """获取决策历史。"""
        return self._decisions[-limit:]

    def get_high_priority_decisions(self) -> list[AgentDecision]:
        """获取高优先级决策。"""
        return [d for d in self._decisions if d.is_high_priority]

    def clear_history(self) -> None:
        """清除历史。"""
        self._decisions.clear()

    @property
    def mapping_count(self) -> int:
        return len(self._action_map)

    def __repr__(self) -> str:
        return f"DecisionAdapter(mappings={self.mapping_count})"