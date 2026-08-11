"""E15.2.3 Action Selector — 动作选择器主类.

整合评分引擎、风险检查、记忆增强和可解释性层，从多个候选动作中
自动选择最优执行动作。

用法:
    selector = ActionSelector()
    result = selector.select(candidates)
"""

from __future__ import annotations

from typing import Any

from .explanation import DecisionExplainer
from .models import (
    ActionCandidate,
    ScoredCandidate,
    SelectedAction,
    SelectionResult,
    SelectionStatus,
)
from .scoring import ScoringEngine, ScoringWeights


# ═══════════════════════════════════════════════════════════════
# Action Selector
# ═══════════════════════════════════════════════════════════════


class ActionSelector:
    """E15.2.3 动作选择器 — 决策中枢.

    流程:
      1. 接收候选动作列表
      2. 评分引擎逐项评分
      3. 记忆增强因子注入
      4. 排序选出最优
      5. 生成解释

    Attributes:
        scoring_engine:  评分引擎
        explainer:       决策解释器
        memory_patterns: 历史记忆模式 (可选)
    """

    def __init__(
        self,
        weights: ScoringWeights | None = None,
        memory_patterns: dict[str, dict[str, Any]] | None = None,
    ):
        """初始化选择器.

        Args:
            weights:         自定义评分权重
            memory_patterns: 历史记忆模式映射
        """
        self._scoring_engine = ScoringEngine(weights)
        self._explainer = DecisionExplainer()
        self._memory_patterns: dict[str, dict[str, Any]] = memory_patterns or {}

    # ── Public API ──────────────────────────────────────────────

    def select(self, candidates: list[ActionCandidate]) -> SelectionResult:
        """从候选列表中选出最优动作.

        Args:
            candidates: 候选动作列表

        Returns:
            SelectionResult: 含选中动作和所有评分
        """
        # 1. 注入记忆增强因子
        enriched = self._apply_memory_boost(candidates)

        # 2. 评分
        scored = self._scoring_engine.score_batch(enriched)

        # 3. 选出最优
        selected = self._pick_best(scored)

        # 4. 标记被拒绝的
        self._mark_rejected(scored, selected)

        # 5. 构建结果
        result = SelectionResult(
            selected=selected,
            candidates=scored,
        )

        # 6. 生成解释
        if selected is not None:
            result.selected = self._explainer.explain(result)

        return result

    def select_single(self, candidate: ActionCandidate) -> SelectionResult:
        """单个候选的选择.

        Args:
            candidate: 单个候选

        Returns:
            SelectionResult
        """
        return self.select([candidate])

    def set_memory_patterns(self, patterns: dict[str, dict[str, Any]]) -> None:
        """设置历史记忆模式."""
        self._memory_patterns = patterns

    def add_memory_pattern(self, action_type: str, pattern: dict[str, Any]) -> None:
        """添加单个记忆模式."""
        self._memory_patterns[action_type] = pattern

    def get_weights(self) -> dict[str, float]:
        """获取当前评分权重."""
        return self._scoring_engine.get_weights()

    def set_weights(self, weights: ScoringWeights) -> None:
        """设置评分权重."""
        self._scoring_engine.set_weights(weights)

    # ── Internal Methods ────────────────────────────────────────

    def _apply_memory_boost(
        self, candidates: list[ActionCandidate]
    ) -> list[ActionCandidate]:
        """注入记忆增强因子.

        从 Pattern Memory 获取历史数据，计算 memory_boost。
        公式: memory_boost = success_rate × avg_reward

        Args:
            candidates: 原始候选

        Returns:
            增强后的候选 (memory_boost 已填充)
        """
        for c in candidates:
            pattern = self._memory_patterns.get(c.action_type)
            if pattern is None:
                continue

            success_rate = pattern.get("success_rate", 0.0)
            avg_reward = pattern.get("avg_reward", 0.0)

            if success_rate > 0 and avg_reward > 0:
                c.memory_boost = round(success_rate * avg_reward, 4)

        return candidates

    def _pick_best(
        self, scored: list[ScoredCandidate]
    ) -> SelectedAction | None:
        """从已排序的评分列表选出最优.

        Args:
            scored: 按得分降序排列的评分列表

        Returns:
            SelectedAction | None
        """
        eligible = [s for s in scored if s.status != SelectionStatus.BLOCKED]
        if not eligible:
            return None

        best = eligible[0]
        return SelectedAction(
            action_id=best.candidate.action_id,
            action_type=best.candidate.action_type,
            score=best.total_score,
            confidence=best.candidate.confidence,
        )

    def _mark_rejected(
        self,
        scored: list[ScoredCandidate],
        selected: SelectedAction | None,
    ) -> None:
        """标记未被选中的候选为 REJECTED.

        Args:
            scored:   评分列表
            selected: 选中的动作
        """
        if selected is None:
            return

        for s in scored:
            if s.status == SelectionStatus.BLOCKED:
                continue
            if s.candidate.action_id == selected.action_id:
                s.status = SelectionStatus.SELECTED
            else:
                s.status = SelectionStatus.REJECTED


__all__ = ["ActionSelector"]