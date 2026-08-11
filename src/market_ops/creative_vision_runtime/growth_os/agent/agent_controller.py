"""E12.7.2 — Autonomous Growth Agent Controller。

自主增长 Agent 控制器 —— E12.7.2 核心入口。

职责:
  1. 整合 Perception → Reasoning → Hypothesis → Decision 全流程
  2. 提供单步和自动运行模式
  3. 连接 Growth Kernel（通过 RuntimeManager）
  4. 输出 AgentDecision 给 Growth Kernel 执行

完整闭环:
  OBSERVE → ANALYZE → UNDERSTAND → HYPOTHESIZE → DECIDE → ACTION
"""

from __future__ import annotations

from typing import Any

from ..kernel.models import ActionType, EventPriority, GrowthAction
from ..kernel.runtime import RuntimeManager
from .decision_adapter import DecisionAdapter
from .hypothesis_generator import HypothesisGenerator
from .models import (
    AgentDecision,
    GrowthHypothesis,
    GrowthObservation,
    RootCause,
)
from .perception import PerceptionLayer
from .reasoning_engine import ReasoningEngine


class AutonomousGrowthAgent:
    """自主增长 Agent。

    整合感知、推理、假设、决策全流程。
    """

    def __init__(
        self,
        runtime: RuntimeManager | None = None,
        perception: PerceptionLayer | None = None,
        reasoning: ReasoningEngine | None = None,
        hypothesis_generator: HypothesisGenerator | None = None,
        decision_adapter: DecisionAdapter | None = None,
    ) -> None:
        self._runtime = runtime or RuntimeManager()
        self._perception = perception or PerceptionLayer()
        self._reasoning = reasoning or ReasoningEngine()
        self._hypothesis_generator = hypothesis_generator or HypothesisGenerator()
        self._decision_adapter = decision_adapter or DecisionAdapter()

        self._last_observation: GrowthObservation | None = None
        self._last_causes: list[RootCause] = []
        self._last_hypotheses: list[GrowthHypothesis] = []
        self._last_decisions: list[AgentDecision] = []

    # ── Core Pipeline ──────────────────────────────────────

    def observe(
        self,
        product_id: str,
        metrics: dict[str, Any] | None = None,
        creative_data: dict[str, Any] | None = None,
        market_data: dict[str, Any] | None = None,
        signals: list[str] | None = None,
    ) -> GrowthObservation:
        """Step 1: 感知产品状态。

        Args:
            product_id:    产品 ID
            metrics:       核心指标
            creative_data: 创意数据
            market_data:   市场数据
            signals:       已知信号

        Returns:
            GrowthObservation
        """
        observation = self._perception.perceive(
            product_id=product_id,
            metrics=metrics,
            creative_data=creative_data,
            market_data=market_data,
            signals=signals,
        )
        self._last_observation = observation
        return observation

    def analyze(
        self, observation: GrowthObservation | None = None
    ) -> list[RootCause]:
        """Step 2: 分析根因。

        Args:
            observation: 观察（默认使用上次观察）

        Returns:
            根因列表
        """
        obs = observation or self._last_observation
        if not obs:
            return []
        causes = self._reasoning.analyze(obs)
        self._last_causes = causes
        return causes

    def generate_hypotheses(
        self,
        causes: list[RootCause] | None = None,
        product_id: str = "",
    ) -> list[GrowthHypothesis]:
        """Step 3: 生成假设。

        Args:
            causes:     根因列表（默认使用上次分析结果）
            product_id: 产品 ID

        Returns:
            假设列表
        """
        causes = causes or self._last_causes
        if not causes:
            return []
        hypotheses = self._hypothesis_generator.generate_from_causes(
            causes, product_id
        )
        self._last_hypotheses = hypotheses
        return hypotheses

    def decide(
        self,
        hypotheses: list[GrowthHypothesis] | None = None,
        observation_id: str = "",
    ) -> list[AgentDecision]:
        """Step 4: 生成决策。

        Args:
            hypotheses:     假设列表（默认使用上次生成结果）
            observation_id: 关联观察 ID

        Returns:
            决策列表
        """
        hypotheses = hypotheses or self._last_hypotheses
        if not hypotheses:
            return []
        decisions = self._decision_adapter.adapt_batch(
            hypotheses, observation_id
        )
        self._last_decisions = decisions
        return decisions

    def act(
        self,
        decisions: list[AgentDecision] | None = None,
    ) -> list[GrowthAction]:
        """Step 5: 执行动作。

        将决策转换为 GrowthAction 并提交到 Runtime。

        Args:
            decisions: 决策列表（默认使用上次决策结果）

        Returns:
            GrowthAction 列表
        """
        decisions = decisions or self._last_decisions
        if not decisions:
            return []

        actions: list[GrowthAction] = []
        for d in decisions:
            if not d.is_actionable:
                continue

            # 映射动作类型
            try:
                action_type = ActionType(d.action_type)
            except ValueError:
                action_type = ActionType.CUSTOM

            action = self._runtime.create_action(
                action_type=action_type,
                product_id=d.product_id,
                target=d.target_module,
                params=d.parameters,
                priority=EventPriority.HIGH if d.is_high_priority else EventPriority.MEDIUM,
            )
            actions.append(action)

        return actions

    # ── Full Pipeline ──────────────────────────────────────

    def run(
        self,
        product_id: str,
        metrics: dict[str, Any] | None = None,
        creative_data: dict[str, Any] | None = None,
        market_data: dict[str, Any] | None = None,
        signals: list[str] | None = None,
        auto_act: bool = False,
    ) -> dict[str, Any]:
        """完整运行流程：Observe → Analyze → Hypothesize → Decide → (Act)。

        Args:
            product_id:    产品 ID
            metrics:       核心指标
            creative_data: 创意数据
            market_data:   市场数据
            signals:       已知信号
            auto_act:      是否自动执行动作

        Returns:
            运行结果字典 {
                observation, causes, hypotheses, decisions, actions
            }
        """
        # Step 1: Observe
        observation = self.observe(product_id, metrics, creative_data, market_data, signals)

        # Step 2: Analyze
        causes = self.analyze(observation)

        # Step 3: Hypothesize
        hypotheses = self.generate_hypotheses(causes, product_id)

        # Step 4: Decide
        decisions = self.decide(hypotheses, observation.observation_id)

        # Step 5: Act (optional)
        actions = []
        if auto_act:
            actions = self.act(decisions)

        return {
            "observation": observation,
            "causes": causes,
            "hypotheses": hypotheses,
            "decisions": decisions,
            "actions": actions,
            "summary": self._build_run_summary(
                observation, causes, hypotheses, decisions, actions
            ),
        }

    def run_batch(
        self,
        products: list[dict[str, Any]],
        auto_act: bool = False,
    ) -> dict[str, dict[str, Any]]:
        """批量运行多个产品。

        Args:
            products: 产品数据列表
            auto_act: 是否自动执行

        Returns:
            {product_id: result}
        """
        results: dict[str, dict[str, Any]] = {}
        for p in products:
            result = self.run(
                product_id=p.get("product_id", ""),
                metrics=p.get("metrics"),
                creative_data=p.get("creative_data"),
                market_data=p.get("market_data"),
                signals=p.get("signals"),
                auto_act=auto_act,
            )
            results[p.get("product_id", "unknown")] = result
        return results

    # ── Query ──────────────────────────────────────────────

    def get_last_observation(self) -> GrowthObservation | None:
        return self._last_observation

    def get_last_causes(self) -> list[RootCause]:
        return list(self._last_causes)

    def get_last_hypotheses(self) -> list[GrowthHypothesis]:
        return list(self._last_hypotheses)

    def get_last_decisions(self) -> list[AgentDecision]:
        return list(self._last_decisions)

    def get_top_decision(self) -> AgentDecision | None:
        if not self._last_decisions:
            return None
        return max(self._last_decisions, key=lambda d: d.priority)

    def get_status(self) -> dict[str, Any]:
        """获取 Agent 状态。"""
        return {
            "has_observation": self._last_observation is not None,
            "cause_count": len(self._last_causes),
            "hypothesis_count": len(self._last_hypotheses),
            "decision_count": len(self._last_decisions),
            "top_priority": self.get_top_decision().priority if self.get_top_decision() else 0,
            "runtime_status": self._runtime.runtime.status,
        }

    def _build_run_summary(
        self,
        observation: GrowthObservation,
        causes: list[RootCause],
        hypotheses: list[GrowthHypothesis],
        decisions: list[AgentDecision],
        actions: list[GrowthAction],
    ) -> str:
        """构建运行摘要。"""
        parts: list[str] = []
        parts.append(
            f"Observed: {observation.product_id} "
            f"(severity={observation.severity.value}, signals={len(observation.signals)})"
        )
        if causes:
            parts.append(
                f"Top cause: {causes[0].category} "
                f"(confidence={causes[0].confidence:.2f})"
            )
        if hypotheses:
            actionable = [h for h in hypotheses if h.is_actionable]
            parts.append(f"Hypotheses: {len(hypotheses)} ({len(actionable)} actionable)")
        if decisions:
            parts.append(
                f"Decisions: {len(decisions)} "
                f"(top priority={decisions[0].priority})"
            )
        if actions:
            parts.append(f"Actions executed: {len(actions)}")

        return " | ".join(parts)

    def __repr__(self) -> str:
        return (
            f"AutonomousGrowthAgent("
            f"observations={self._perception.observation_count}, "
            f"rules={self._reasoning.rule_count})"
        )