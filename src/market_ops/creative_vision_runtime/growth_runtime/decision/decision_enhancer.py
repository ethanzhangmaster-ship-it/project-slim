"""E13.5 / E13.6.5 Decision Enhancer — Pattern + Decision → Decision 桥接层.

Day 6.5 升级:
  将 PatternRetriever (经验模式) 和 DecisionMemoryRetriever (行为轨迹)
  的结果合并注入 DecisionEngine 的决策流程。

核心职责:
  1. PatternRetriever: 查询"历史上类似情况最佳动作是什么"
  2. DecisionMemoryRetriever: 查询"我之前实际做过什么决定"
  3. 两者合并 → 形成完整的决策上下文

功能:
  - enhance: 用 Pattern + Decision 历史增强 DecisionInput
  - add_pattern_strategies: 将模式推荐转换为策略候选
  - adjust_confidence: 基于 Pattern + Decision 历史调整置信度
  - generate_enhancement_report: 生成增强报告

Confidence 合并算法:
  final_confidence = base_confidence × 0.5
                    + pattern_confidence × 0.3
                    + decision_history_confidence × 0.2

连接:
  PatternRetriever + DecisionMemoryRetriever → DecisionEnhancer → DecisionEngine.decide()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .decision_memory_retriever import (
    DecisionContext,
    DecisionHistoryResult,
    DecisionMemoryRetriever,
)
from .pattern_retriever import (
    PatternRecommendation,
    PatternRetriever,
    RetrievalContext,
    RetrievalResult,
)


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class EnhancementReport:
    """增强报告 — 记录 Pattern + Decision → Decision 增强的详细信息.

    Attributes:
        retrieval_result: Pattern 检索结果
        decision_history: Decision 历史检索结果 (Day 6.5 新增)
        strategies_added: 从 Pattern 中添加的策略候选数
        confidence_adjustments: 置信度调整记录
        merged_confidence: 合并后的最终置信度 (Day 6.5 新增)
        warnings: 基于 Pattern + Decision 的警告
        pattern_used: 是否使用了 Pattern 历史
        decision_used: 是否使用了 Decision 历史 (Day 6.5 新增)
        summary: 增强摘要
    """
    retrieval_result: RetrievalResult | None = None
    decision_history: DecisionHistoryResult | None = None
    strategies_added: int = 0
    confidence_adjustments: list[dict[str, Any]] = field(default_factory=list)
    merged_confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    pattern_used: bool = False
    decision_used: bool = False
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_used": self.pattern_used,
            "decision_used": self.decision_used,
            "strategies_added": self.strategies_added,
            "confidence_adjustments": self.confidence_adjustments,
            "merged_confidence": round(self.merged_confidence, 4),
            "warnings": self.warnings,
            "summary": self.summary,
            "retrieval": self.retrieval_result.to_dict() if self.retrieval_result else None,
            "decision_history": self.decision_history.to_dict() if self.decision_history else None,
        }


# ═══════════════════════════════════════════════════════════════
# Decision Enhancer
# ═══════════════════════════════════════════════════════════════


class DecisionEnhancer:
    """决策增强器 — 将 Pattern + Decision 记忆注入 Decision 流程.

    Day 6.5 升级:
      现在同时使用 PatternRetriever 和 DecisionMemoryRetriever，
      形成完整的决策上下文:
        Pattern Memory (What should I do) + Decision Memory (What did I do)

    核心流程:
      1. 从 Opportunity 构建 RetrievalContext
      2. 通过 PatternRetriever 检索历史模式
      3. 通过 DecisionMemoryRetriever 检索历史决策 (Day 6.5 新增)
      4. 将模式推荐转换为策略候选
      5. 调整现有策略的置信度 (基于 Pattern + Decision)
      6. 添加历史模式警告
      7. 返回增强后的 DecisionInput + EnhancementReport

    用法:
        store = PatternStore()
        pattern_retriever = PatternRetriever(store)
        decision_retriever = DecisionMemoryRetriever(decision_memory)

        enhancer = DecisionEnhancer(
            pattern_retriever=pattern_retriever,
            decision_retriever=decision_retriever,
        )

        enhanced_input, report = enhancer.enhance(decision_input)
        engine = DecisionEngine()
        output = engine.decide(enhanced_input)
    """

    # ── 增强参数 ──────────────────────────────────────────────

    # 模式策略的基础评分
    PATTERN_BASE_SCORE = 0.70       # 来自历史模式的策略基础评分
    # 置信度增强参数
    PATTERN_CONFIDENCE_BOOST = 0.15  # 模式匹配时置信度提升
    MAX_CONFIDENCE_BOOST = 0.25      # 最大置信度提升
    # 模式策略的优先级偏移
    PATTERN_PRIORITY_BOOST = 0.15    # 模式策略额外优先级

    # Day 6.5: 置信度合并权重
    BASE_WEIGHT = 0.5                # 基础置信度权重
    PATTERN_WEIGHT = 0.3             # 模式置信度权重
    DECISION_WEIGHT = 0.2            # 决策历史置信度权重

    def __init__(
        self,
        pattern_retriever: PatternRetriever,
        decision_retriever: DecisionMemoryRetriever | None = None,
        pattern_base_score: float = 0.70,
        pattern_confidence_boost: float = 0.15,
        max_confidence_boost: float = 0.25,
        pattern_priority_boost: float = 0.15,
        base_weight: float = 0.5,
        pattern_weight: float = 0.3,
        decision_weight: float = 0.2,
    ):
        """初始化决策增强器.

        Args:
            pattern_retriever: PatternRetriever 实例
            decision_retriever: DecisionMemoryRetriever 实例 (Day 6.5 新增)
            pattern_base_score: 模式策略基础评分
            pattern_confidence_boost: 置信度提升幅度
            max_confidence_boost: 最大置信度提升
            pattern_priority_boost: 模式策略优先级偏移
            base_weight: 基础置信度权重
            pattern_weight: 模式置信度权重
            decision_weight: 决策历史置信度权重
        """
        self._retriever = pattern_retriever
        self._decision_retriever = decision_retriever
        self._pattern_base_score = pattern_base_score
        self._pattern_confidence_boost = pattern_confidence_boost
        self._max_confidence_boost = max_confidence_boost
        self._pattern_priority_boost = pattern_priority_boost
        self._base_weight = base_weight
        self._pattern_weight = pattern_weight
        self._decision_weight = decision_weight

    # ═══════════════════════════════════════════════════════════
    # Main API
    # ═══════════════════════════════════════════════════════════

    def enhance(
        self,
        input_data: Any,
        retrieval_context: RetrievalContext | None = None,
        decision_context: DecisionContext | None = None,
    ) -> tuple[Any, EnhancementReport]:
        """用 Pattern + Decision 历史增强 DecisionInput.

        Day 6.5 升级:
          同时查询 Pattern Memory 和 Decision Memory，
          合并两者的置信度。

        Args:
            input_data: DecisionInput 实例
            retrieval_context: Pattern 检索上下文 (如果为 None，从 opportunity 构建)
            decision_context: Decision 检索上下文 (如果为 None，从 retrieval_context 构建)

        Returns:
            tuple[DecisionInput, EnhancementReport]: 增强后的输入和报告
        """
        report = EnhancementReport()

        # Step 1: 构建 Pattern 检索上下文
        if retrieval_context is None:
            retrieval_context = self._build_context(input_data)

        if retrieval_context is None:
            report.summary = "No retrieval context available, skipping enhancement."
            return input_data, report

        # Step 2: 检索 Pattern 历史模式
        pattern_result = self._retriever.retrieve(retrieval_context)
        report.retrieval_result = pattern_result

        if pattern_result.has_recommendations:
            report.pattern_used = True

        # Step 3: 检索 Decision 历史决策 (Day 6.5 新增)
        if self._decision_retriever is not None:
            if decision_context is None:
                decision_context = self._build_decision_context(retrieval_context)
            if decision_context is not None:
                decision_result = self._decision_retriever.retrieve(decision_context)
                report.decision_history = decision_result
                if decision_result.has_recommendations:
                    report.decision_used = True

        # Step 4: 将模式推荐转换为策略候选
        if report.pattern_used:
            strategies_added = self._add_pattern_strategies(input_data, pattern_result)
            report.strategies_added = strategies_added

        # Step 5: 调整现有策略置信度 (基于 Pattern + Decision)
        if report.pattern_used or report.decision_used:
            adjustments = self._adjust_confidences(input_data, pattern_result, report)
            report.confidence_adjustments = adjustments

        # Step 6: 合并置信度 (Day 6.5: Pattern + Decision)
        if report.pattern_used or report.decision_used:
            report.merged_confidence = self._merge_confidence(
                input_data, pattern_result, report.decision_history,
            )

        # Step 7: 添加历史警告 (Pattern + Decision)
        if report.pattern_used:
            pattern_warnings = self._add_pattern_warnings(input_data, pattern_result)
            report.warnings.extend(pattern_warnings)
        if report.decision_used and report.decision_history:
            decision_warnings = list(report.decision_history.warnings)
            report.warnings.extend(decision_warnings)

        # Step 8: 生成摘要
        report.summary = self._generate_summary(
            pattern_result if report.pattern_used else None,
            report.strategies_added,
            report.confidence_adjustments,
            report.warnings,
            report,
        )

        return input_data, report

    def enhance_and_retrieve(
        self,
        input_data: Any,
        retrieval_context: RetrievalContext | None = None,
        decision_context: DecisionContext | None = None,
    ) -> tuple[Any, EnhancementReport, RetrievalResult]:
        """增强 DecisionInput 并同时返回检索结果."""
        enhanced, report = self.enhance(input_data, retrieval_context, decision_context)
        return enhanced, report, report.retrieval_result or RetrievalResult()

    # ═══════════════════════════════════════════════════════════
    # Context Building
    # ═══════════════════════════════════════════════════════════

    def _build_context(self, input_data: Any) -> RetrievalContext | None:
        """从 DecisionInput 构建 RetrievalContext."""
        opportunity = getattr(input_data, "opportunity", None)
        if opportunity is None:
            return None

        # 尝试使用 from_opportunity
        ctx = RetrievalContext.from_opportunity(opportunity)

        # 补充 metadata 中的信息
        metadata = getattr(input_data, "metadata", {}) or {}
        if isinstance(metadata, dict):
            if "audience_segment" in metadata:
                ctx.audience_segment = metadata["audience_segment"]
            if "signal_types" in metadata:
                ctx.signal_types = metadata["signal_types"]
            if "product_category" in metadata:
                ctx.product_category = metadata["product_category"]
            if "metrics_snapshot" in metadata:
                ctx.metrics_snapshot = metadata["metrics_snapshot"]
            if "opportunity_type" in metadata:
                ctx.opportunity_type = metadata["opportunity_type"]
            if "category" in metadata:
                ctx.category = metadata["category"]
            if "action_type" in metadata:
                ctx.action_type = metadata["action_type"]

        return ctx

    # ═══════════════════════════════════════════════════════════
    # Decision Context Building (Day 6.5 新增)
    # ═══════════════════════════════════════════════════════════

    def _build_decision_context(
        self,
        retrieval_context: RetrievalContext,
    ) -> DecisionContext | None:
        """从 Pattern RetrievalContext 构建 DecisionContext."""
        if not retrieval_context.opportunity_type:
            return None
        return DecisionContext(
            opportunity_type=retrieval_context.opportunity_type,
            action_type=retrieval_context.action_type,
            audience_segment=retrieval_context.audience_segment,
            signal_types=retrieval_context.signal_types,
            metrics=retrieval_context.metrics_snapshot,
        )

    # ═══════════════════════════════════════════════════════════
    # Confidence Merging (Day 6.5 新增)
    # ═══════════════════════════════════════════════════════════

    def _merge_confidence(
        self,
        input_data: Any,
        pattern_result: RetrievalResult,
        decision_history: DecisionHistoryResult | None,
    ) -> float:
        """合并 Pattern + Decision 置信度.

        公式:
          final = base × 0.5 + pattern × 0.3 + decision × 0.2

        base: 从 DecisionInput 中提取的基础置信度
        pattern: Pattern 推荐中最高置信度
        decision: Decision 历史成功率
        """
        # 基础置信度
        base_confidence = 0.50
        strategies = getattr(input_data, "strategies", None)
        if strategies and len(strategies) > 0:
            s0 = strategies[0]
            if isinstance(s0, dict):
                base_confidence = s0.get("confidence_score", s0.get("final_score", 0.50))
            elif hasattr(s0, "confidence_score"):
                base_confidence = s0.confidence_score

        # Pattern 置信度
        pattern_confidence = 0.0
        if pattern_result.has_recommendations and pattern_result.top_action:
            pattern_confidence = pattern_result.top_action.confidence

        # Decision 置信度
        decision_confidence = 0.0
        if decision_history and decision_history.has_recommendations:
            decision_confidence = decision_history.confidence

        merged = round(
            base_confidence * self._base_weight
            + pattern_confidence * self._pattern_weight
            + decision_confidence * self._decision_weight,
            4,
        )

        return min(1.0, merged)

    # ═══════════════════════════════════════════════════════════
    # Strategy Injection
    # ═══════════════════════════════════════════════════════════

    def _add_pattern_strategies(
        self,
        input_data: Any,
        result: RetrievalResult,
    ) -> int:
        """将模式推荐转换为策略候选并添加到 DecisionInput.

        为每个推荐动作创建一个 StrategyCandidate，包含:
          - 历史成功率
          - 模式置信度
          - 样本量
          - 推荐理由
        """
        added = 0
        strategies = getattr(input_data, "strategies", None)
        if strategies is None:
            return 0

        # 收集已存在的 strategy_id
        existing_ids = set()
        for s in strategies:
            if isinstance(s, dict):
                existing_ids.add(s.get("strategy_id", ""))
            elif hasattr(s, "strategy_id"):
                existing_ids.add(s.strategy_id)

        for rec in result.recommendations:
            if not rec.is_actionable:
                continue

            strategy_id = f"pattern_{rec.pattern.pattern_id[:8]}"
            if strategy_id in existing_ids:
                continue

            # 模式策略评分
            pattern_score = self._compute_pattern_strategy_score(rec)

            strategy = {
                "strategy_id": strategy_id,
                "strategy_name": f"[Pattern] {rec.pattern.action.action_type}",
                "strategy": {
                    "action_type": rec.pattern.action.action_type,
                    "params_template": rec.pattern.action.params_template,
                    "expected_impact": rec.pattern.action.expected_impact,
                },
                "historical_score": round(
                    rec.pattern.performance.success_rate * rec.pattern.performance.avg_reward,
                    4,
                ),
                "confidence_score": pattern_score,
                "risk_score": round(1.0 - rec.pattern.performance.success_rate, 4),
                "final_score": pattern_score,
                "metadata": {
                    "source": "pattern_memory",
                    "pattern_id": rec.pattern.pattern_id,
                    "samples": rec.pattern.performance.samples,
                    "success_rate": rec.pattern.performance.success_rate,
                    "avg_reward": rec.pattern.performance.avg_reward,
                    "similarity": rec.similarity_score,
                    "reasoning": rec.reasoning,
                },
            }
            strategies.append(strategy)
            existing_ids.add(strategy_id)
            added += 1

        return added

    def _compute_pattern_strategy_score(
        self,
        rec: PatternRecommendation,
    ) -> float:
        """计算模式策略的评分."""
        perf = rec.pattern.performance
        # 基础分 × 成功率 × 奖励调整
        score = (
            self._pattern_base_score
            * (0.4 + 0.6 * perf.success_rate)
            * (0.5 + 0.5 * max(perf.avg_reward, 0.01))
        )
        return round(min(1.0, score), 4)

    # ═══════════════════════════════════════════════════════════
    # Confidence Adjustment
    # ═══════════════════════════════════════════════════════════

    def _adjust_confidences(
        self,
        input_data: Any,
        result: RetrievalResult,
        report: EnhancementReport,
    ) -> list[dict[str, Any]]:
        """基于 Pattern + Decision 历史调整现有策略的置信度.

        如果某个策略的动作类型与历史成功模式匹配，
        提升其置信度; 如果匹配历史失败模式，降低置信度。
        Day 6.5: 同时考虑 Decision 历史中的失败模式。
        """
        adjustments: list[dict[str, Any]] = []
        strategies = getattr(input_data, "strategies", None)
        if not strategies:
            return adjustments

        for i, strategy in enumerate(strategies):
            action_type = self._extract_action_type(strategy)

            # Pattern 匹配检查
            for rec in result.recommendations:
                if rec.pattern.action.action_type != action_type:
                    continue
                if not rec.is_actionable:
                    continue

                boost = min(
                    self._max_confidence_boost,
                    self._pattern_confidence_boost * rec.confidence,
                )
                self._apply_confidence_boost(strategy, boost)

                adjustments.append({
                    "strategy_index": i,
                    "action_type": action_type,
                    "adjustment": f"+{boost:.2f}",
                    "source": "pattern",
                    "reason": f"Pattern match: {rec.pattern.performance.samples} cases, "
                              f"{rec.pattern.performance.success_rate * 100:.0f}% success",
                    "pattern_id": rec.pattern.pattern_id,
                })
                break

            # Pattern avoid 检查
            for avoid in result.avoid_actions:
                if avoid.pattern.action.action_type != action_type:
                    continue
                penalty = -0.15
                self._apply_confidence_boost(strategy, penalty)
                adjustments.append({
                    "strategy_index": i,
                    "action_type": action_type,
                    "adjustment": f"{penalty:.2f}",
                    "source": "pattern",
                    "reason": f"Pattern warns: {avoid.pattern.performance.samples} cases, "
                              f"{(1.0 - avoid.pattern.performance.success_rate) * 100:.0f}% failure",
                    "pattern_id": avoid.pattern.pattern_id,
                })
                break

            # Day 6.5: Decision 历史警告检查
            if report.decision_history and report.decision_history.has_warnings:
                for warning in report.decision_history.warnings:
                    if action_type in warning and "AVOID" in warning:
                        decision_penalty = -0.20
                        self._apply_confidence_boost(strategy, decision_penalty)
                        adjustments.append({
                            "strategy_index": i,
                            "action_type": action_type,
                            "adjustment": f"{decision_penalty:.2f}",
                            "source": "decision_history",
                            "reason": f"Decision history warns: {warning}",
                        })
                        break

        return adjustments

    @staticmethod
    def _extract_action_type(strategy: Any) -> str:
        """从策略中提取动作类型."""
        if isinstance(strategy, dict):
            inner = strategy.get("strategy", {})
            if isinstance(inner, dict):
                return inner.get("action_type", "")
            return strategy.get("action_type", "")
        if hasattr(strategy, "action_type"):
            return strategy.action_type
        return ""

    @staticmethod
    def _apply_confidence_boost(strategy: Any, boost: float) -> None:
        """对策略应用置信度调整."""
        if isinstance(strategy, dict):
            if "confidence_score" in strategy:
                strategy["confidence_score"] = round(
                    min(1.0, max(0.0, strategy["confidence_score"] + boost)),
                    4,
                )
            if "final_score" in strategy:
                strategy["final_score"] = round(
                    min(1.0, max(0.0, strategy["final_score"] + boost * 0.5)),
                    4,
                )
        elif hasattr(strategy, "confidence_score"):
            strategy.confidence_score = round(
                min(1.0, max(0.0, strategy.confidence_score + boost)),
                4,
            )

    # ═══════════════════════════════════════════════════════════
    # Warnings
    # ═══════════════════════════════════════════════════════════

    def _add_pattern_warnings(
        self,
        input_data: Any,
        result: RetrievalResult,
    ) -> list[str]:
        """基于历史模式添加决策警告."""
        warnings: list[str] = []

        # 添加 avoid 模式警告
        for avoid in result.avoid_actions[:3]:
            perf = avoid.pattern.performance
            warnings.append(
                f"Historical warning: {avoid.pattern.action.action_type} under "
                f"{avoid.pattern.condition.opportunity_type} has "
                f"{(1.0 - perf.success_rate) * 100:.0f}% failure rate "
                f"({perf.samples} samples)"
            )

        # 如果没有匹配的模式
        if not result.has_recommendations:
            warnings.append(
                "No historical patterns found for this scenario. "
                "Decision will be made without prior experience."
            )

        # 添加 warnings 到 input_data
        if hasattr(input_data, "warnings"):
            # DecisionInput doesn't have a direct warnings attribute,
            # but metadata can carry them
            pass

        return warnings

    # ═══════════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════════

    def _generate_summary(
        self,
        result: RetrievalResult | None,
        strategies_added: int,
        adjustments: list[dict[str, Any]],
        warnings: list[str],
        report: EnhancementReport,
    ) -> str:
        """生成增强摘要."""
        parts: list[str] = []

        # Pattern 部分
        if result and result.top_action:
            parts.append(
                f"Pattern-enhanced: top recommendation is "
                f"'{result.top_action.pattern.action.action_type}' "
                f"(confidence: {result.top_action.confidence:.2f})"
            )

        # Decision 部分 (Day 6.5 新增)
        if report.decision_used and report.decision_history:
            parts.append(
                f"Decision history: {report.decision_history.success_rate:.0%} success "
                f"({report.decision_history.total_matched} cases)"
            )

        if strategies_added > 0:
            parts.append(f"Added {strategies_added} pattern-based strategy candidates")

        if adjustments:
            boosts = [a for a in adjustments if a["adjustment"].startswith("+")]
            penalties = [a for a in adjustments if a["adjustment"].startswith("-")]
            if boosts:
                parts.append(f"Boosted {len(boosts)} strategies")
            if penalties:
                parts.append(f"Penalized {len(penalties)} strategies")

        # Day 6.5: 合并置信度
        if report.merged_confidence > 0:
            parts.append(f"Merged confidence: {report.merged_confidence:.2f}")

        if warnings:
            parts.append(f"{len(warnings)} warnings")

        return " | ".join(parts) if parts else "No enhancement applied."