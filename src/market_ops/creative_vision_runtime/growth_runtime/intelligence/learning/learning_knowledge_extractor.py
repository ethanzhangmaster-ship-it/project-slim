"""E13.7.5 Learning Knowledge Extractor — 从历史学习中提取结构化知识.

Day 7.5.1:
  从 LearningExperience + LearningReward + AttributionResult 中提取:
    - LearnedPattern: 发现的行为模式
    - StrategyInsight: 策略级洞察
    - RiskSignal: 风险信号

核心流程:
  Experiences + Rewards + Attributions
              |
              v
  LearningKnowledgeExtractor
              |
              +--> _extract_patterns()     → list[LearnedPattern]
              |
              +--> _extract_strategies()   → list[StrategyInsight]
              |
              +--> _extract_risks()        → list[RiskSignal]
              |
              v
  LearningKnowledge (patterns + strategies + warnings + confidence)

设计原则:
  - 纯读取 Memory，不影响现有逻辑
  - 基于统计方法，确定性可解释
  - 多维聚合: creative/strategy/audience/timing
  - 自动置信度计算
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

from .models.learning_models import (
    AttributionResult,
    LearnedPattern,
    LearningExperience,
    LearningKnowledge,
    LearningReward,
    RiskSignal,
    StrategyInsight,
)


# ═══════════════════════════════════════════════════════════════
# LearningKnowledgeExtractor
# ═══════════════════════════════════════════════════════════════


class LearningKnowledgeExtractor:
    """从历史学习经验中提取结构化知识.

    用法:
        extractor = LearningKnowledgeExtractor(min_evidence=10)
        knowledge = extractor.extract(
            experiences=[...],
            rewards=[...],
            attributions=[...],
        )
    """

    def __init__(self, min_evidence: int = 10, min_confidence: float = 0.50) -> None:
        """初始化提取器.

        Args:
            min_evidence: 最小证据数 (样本不足时不提取)
            min_confidence: 最小置信度阈值
        """
        self._min_evidence = min_evidence
        self._min_confidence = min_confidence
        self._extraction_count: int = 0

    @property
    def extraction_count(self) -> int:
        return self._extraction_count

    # ── Public API ───────────────────────────────────────────────

    def extract(
        self,
        experiences: list[LearningExperience],
        rewards: list[LearningReward] | None = None,
        attributions: list[AttributionResult] | None = None,
    ) -> LearningKnowledge:
        """统一入口 — 从经验中提取知识.

        Args:
            experiences: 学习经验列表
            rewards: 奖励列表 (可选, 若为 None 则从 experience.reward 提取)
            attributions: 归因列表 (可选, 若为 None 则从 experience.attribution 提取)

        Returns:
            LearningKnowledge: 结构化知识
        """
        self._extraction_count += 1

        if len(experiences) < self._min_evidence:
            return LearningKnowledge(
                total_experiences=len(experiences),
                confidence=0.0,
                extraction_method="statistical",
                metadata={"reason": "insufficient_experiences", "min_required": self._min_evidence},
            )

        # 统一 rewards 和 attributions
        _rewards = rewards or [e.reward for e in experiences if e.reward is not None]
        _attributions = attributions or [e.attribution for e in experiences if e.attribution is not None]

        # 提取
        patterns = self._extract_patterns(experiences, _rewards, _attributions)
        strategies = self._extract_strategies(experiences, _rewards)
        risks = self._extract_risks(experiences, _rewards, _attributions)

        # 整体置信度
        confidence = self._compute_overall_confidence(patterns, strategies, risks, len(experiences))

        return LearningKnowledge(
            patterns=patterns,
            strategies=strategies,
            warnings=risks,
            confidence=round(confidence, 4),
            total_experiences=len(experiences),
            extraction_method="statistical",
        )

    # ── Pattern Extraction ──────────────────────────────────────

    def _extract_patterns(
        self,
        experiences: list[LearningExperience],
        rewards: list[LearningReward],
        attributions: list[AttributionResult],
    ) -> list[LearnedPattern]:
        """从经验中提取行为模式."""
        patterns: list[LearnedPattern] = []

        # 1. 按 primary_factor 分组
        factor_groups = self._group_by_primary_factor(experiences, attributions)

        for factor, group in factor_groups.items():
            if len(group) < self._min_evidence:
                continue

            # 2. 按 condition 子分组
            condition_groups = self._group_by_condition(group)

            for condition, cond_group in condition_groups.items():
                if len(cond_group) < 3:
                    continue

                pattern = self._build_pattern(factor, condition, cond_group, rewards)
                if pattern and pattern.confidence >= self._min_confidence:
                    patterns.append(pattern)

        # 3. 按 action_type 分组提取
        action_patterns = self._extract_action_patterns(experiences, rewards)
        patterns.extend(action_patterns)

        # 去重 + 排序
        patterns = self._deduplicate_patterns(patterns)
        patterns.sort(key=lambda p: p.confidence, reverse=True)

        return patterns

    def _group_by_primary_factor(
        self,
        experiences: list[LearningExperience],
        attributions: list[AttributionResult],
    ) -> dict[str, list[LearningExperience]]:
        """按归因主因分组."""
        # 建立 decision_id → attribution 映射
        attr_map: dict[str, AttributionResult] = {}
        for a in attributions:
            if a.decision_id:
                attr_map[a.decision_id] = a

        groups: dict[str, list[LearningExperience]] = defaultdict(list)
        for e in experiences:
            attr = attr_map.get(e.decision_id)
            if attr:
                groups[attr.primary_factor].append(e)
            else:
                groups["unknown"].append(e)

        return dict(groups)

    def _group_by_condition(
        self, experiences: list[LearningExperience]
    ) -> dict[str, list[LearningExperience]]:
        """按条件分组 (action_type + strategy_name + opportunity_type)."""
        groups: dict[str, list[LearningExperience]] = defaultdict(list)
        for e in experiences:
            key = f"{e.action_type}|{e.strategy_name}|{e.context.get('opportunity_type', '')}"
            groups[key].append(e)
        return dict(groups)

    def _build_pattern(
        self,
        factor: str,
        condition: str,
        experiences: list[LearningExperience],
        rewards: list[LearningReward],
    ) -> LearnedPattern | None:
        """从一组经验构建模式."""
        total = len(experiences)
        if total < 3:
            return None

        # 提取 reward 数据 — 直接从 experience.reward 获取
        exp_rewards = [e.reward.total_reward for e in experiences if e.reward is not None]

        if not exp_rewards:
            return None

        avg_reward = sum(exp_rewards) / len(exp_rewards)
        success_count = sum(1 for r in exp_rewards if r > 0.15)
        success_rate = success_count / len(exp_rewards) if exp_rewards else 0.0

        # 置信度: 样本量因子 × 成功率确定性
        sample_factor = 1.0 - math.exp(-total / 10.0)
        confidence = sample_factor * (0.3 + abs(avg_reward) * 0.5 + success_rate * 0.2)
        confidence = round(min(0.95, confidence), 4)

        impact = "positive" if avg_reward > 0.15 else ("negative" if avg_reward < -0.15 else "neutral")

        return LearnedPattern(
            dimension=factor,
            condition=condition,
            impact=impact,
            avg_reward=round(avg_reward, 4),
            sample_count=total,
            confidence=confidence,
            success_rate=round(success_rate, 4),
            source_experience_ids=[e.learning_id for e in experiences],
            metadata={
                "action_types": list(set(e.action_type for e in experiences)),
                "strategy_names": list(set(e.strategy_name for e in experiences)),
            },
        )

    def _extract_action_patterns(
        self,
        experiences: list[LearningExperience],
        rewards: list[LearningReward],
    ) -> list[LearnedPattern]:
        """按 action_type 提取模式."""
        patterns: list[LearnedPattern] = []
        grouped: dict[str, list[LearningExperience]] = defaultdict(list)

        for e in experiences:
            grouped[e.action_type].append(e)

        for action_type, group in grouped.items():
            if len(group) < self._min_evidence:
                continue

            exp_rewards = [e.reward.total_reward for e in group if e.reward is not None]
            if not exp_rewards:
                continue

            avg_reward = sum(exp_rewards) / len(exp_rewards)
            success_count = sum(1 for r in exp_rewards if r > 0.15)
            success_rate = success_count / len(exp_rewards)

            sample_factor = 1.0 - math.exp(-len(group) / 10.0)
            confidence = sample_factor * (0.3 + abs(avg_reward) * 0.5 + success_rate * 0.2)
            confidence = round(min(0.95, confidence), 4)

            impact = "positive" if avg_reward > 0.15 else ("negative" if avg_reward < -0.15 else "neutral")

            patterns.append(LearnedPattern(
                dimension="action_type",
                condition=action_type,
                impact=impact,
                avg_reward=round(avg_reward, 4),
                sample_count=len(group),
                confidence=confidence,
                success_rate=round(success_rate, 4),
                source_experience_ids=[e.learning_id for e in group],
                metadata={"action_type": action_type},
            ))

        return patterns

    def _deduplicate_patterns(self, patterns: list[LearnedPattern]) -> list[LearnedPattern]:
        """去重: 同维度+条件只保留置信度最高的."""
        seen: dict[str, LearnedPattern] = {}
        for p in patterns:
            key = f"{p.dimension}|{p.condition}"
            if key not in seen or p.confidence > seen[key].confidence:
                seen[key] = p
        return list(seen.values())

    # ── Strategy Extraction ─────────────────────────────────────

    def _extract_strategies(
        self,
        experiences: list[LearningExperience],
        rewards: list[LearningReward],
    ) -> list[StrategyInsight]:
        """提取策略洞察."""
        insights: list[StrategyInsight] = []
        grouped: dict[str, list[LearningExperience]] = defaultdict(list)

        for e in experiences:
            key = f"{e.strategy_name}|{e.action_type}"
            grouped[key].append(e)

        for key, group in grouped.items():
            if len(group) < self._min_evidence:
                continue

            strategy_name = group[0].strategy_name
            action_type = group[0].action_type

            exp_rewards = [e.reward.total_reward for e in group if e.reward is not None]
            if not exp_rewards:
                continue

            avg_effectiveness = sum(exp_rewards) / len(exp_rewards)
            success_count = sum(1 for r in exp_rewards if r > 0.15)

            # 最佳上下文
            best_context = self._find_best_context(group)

            # 风险提示
            warnings = self._extract_strategy_warnings(exp_rewards, group)

            # 置信度
            sample_factor = 1.0 - math.exp(-len(group) / 10.0)
            reward_confidence = min(0.95, 0.5 + abs(avg_effectiveness) * 0.45)
            confidence = round(sample_factor * reward_confidence, 4)

            insights.append(StrategyInsight(
                strategy_name=strategy_name,
                action_type=action_type,
                avg_effectiveness=round(avg_effectiveness, 4),
                success_count=success_count,
                total_count=len(group),
                best_context=best_context,
                warnings=warnings,
                confidence=confidence,
            ))

        insights.sort(key=lambda s: s.avg_effectiveness, reverse=True)
        return insights

    def _find_best_context(
        self, experiences: list[LearningExperience]
    ) -> dict[str, Any]:
        """找到最佳适用上下文."""
        context: dict[str, Any] = {}
        field_values: dict[str, Counter] = defaultdict(Counter)

        for e in experiences:
            for k, v in e.context.items():
                if isinstance(v, (str, int, float, bool)):
                    field_values[k][str(v)] += 1

        for field, counter in field_values.items():
            if counter and counter.most_common(1)[0][1] >= len(experiences) * 0.5:
                context[field] = counter.most_common(1)[0][0]

        return context

    def _extract_strategy_warnings(
        self,
        rewards: list[float],
        experiences: list[LearningExperience],
    ) -> list[str]:
        """提取策略风险提示."""
        warnings: list[str] = []

        # 负奖励比例
        neg_rate = sum(1 for r in rewards if r < -0.15) / len(rewards) if rewards else 0
        if neg_rate > 0.3:
            warnings.append(f"High negative reward rate: {neg_rate:.0%}")

        # 趋势下降
        if len(rewards) >= 10:
            first_half = sum(rewards[:len(rewards)//2]) / (len(rewards)//2)
            second_half = sum(rewards[len(rewards)//2:]) / (len(rewards) - len(rewards)//2)
            if second_half < first_half - 0.15:
                warnings.append("Declining trend detected in recent executions")

        # 执行问题
        blocked_count = sum(1 for e in experiences if e.outcome.was_blocked)
        if blocked_count > 0:
            warnings.append(f"Blocked executions: {blocked_count}")

        return warnings

    # ── Risk Extraction ─────────────────────────────────────────

    def _extract_risks(
        self,
        experiences: list[LearningExperience],
        rewards: list[LearningReward],
        attributions: list[AttributionResult],
    ) -> list[RiskSignal]:
        """提取风险信号."""
        risks: list[RiskSignal] = []

        # 1. 创意疲劳检测
        creative_risk = self._detect_creative_fatigue(experiences, attributions)
        if creative_risk:
            risks.append(creative_risk)

        # 2. 策略衰减检测
        strategy_risk = self._detect_strategy_decay(experiences, rewards)
        if strategy_risk:
            risks.append(strategy_risk)

        # 3. 预算效率检测
        budget_risk = self._detect_budget_inefficiency(experiences)
        if budget_risk:
            risks.append(budget_risk)

        # 4. 受众饱和检测
        audience_risk = self._detect_audience_saturation(experiences, attributions)
        if audience_risk:
            risks.append(audience_risk)

        risks.sort(key=lambda r: {"critical": 0, "high": 1, "medium": 2, "low": 3}[r.risk_level])
        return risks

    def _detect_creative_fatigue(
        self,
        experiences: list[LearningExperience],
        attributions: list[AttributionResult],
    ) -> RiskSignal | None:
        """检测创意疲劳."""
        creative_exps = [
            e for e in experiences
            if e.action_type and "creative" in e.action_type.lower()
        ]
        if len(creative_exps) < 5:
            return None

        # 近期 creative 贡献下降
        attr_map = {a.decision_id: a for a in attributions if a.decision_id}
        creative_contribs = [
            attr_map[e.decision_id].creative_contribution
            for e in creative_exps
            if e.decision_id in attr_map
        ]

        if not creative_contribs:
            return None

        if len(creative_contribs) >= 10:
            recent = creative_contribs[-5:]
            older = creative_contribs[:5]
            recent_avg = sum(recent) / len(recent)
            older_avg = sum(older) / len(older)

            if recent_avg < older_avg - 0.15:
                risk_level = "high" if recent_avg < 0 else "medium"
                return RiskSignal(
                    signal_type="creative_fatigue",
                    risk_level=risk_level,
                    condition=f"Creative contribution declining: {older_avg:.2f} → {recent_avg:.2f}",
                    frequency=len(creative_exps),
                    avg_impact=round(recent_avg - older_avg, 4),
                    confidence=0.75,
                    recommendations=[
                        "Refresh creative assets",
                        "Test new creative variants",
                        "Reduce frequency on fatigued creatives",
                    ],
                )

        return None

    def _detect_strategy_decay(
        self,
        experiences: list[LearningExperience],
        rewards: list[LearningReward],
    ) -> RiskSignal | None:
        """检测策略衰减."""
        if len(experiences) < 10:
            return None

        exp_rewards = [e.reward.total_reward for e in experiences if e.reward is not None]
        if len(exp_rewards) < 10:
            return None

        recent = exp_rewards[-5:]
        older = exp_rewards[:5]
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)

        if recent_avg < older_avg - 0.2:
            risk_level = "high" if recent_avg < -0.15 else "medium"
            return RiskSignal(
                signal_type="strategy_decay",
                risk_level=risk_level,
                condition=f"Reward declining: {older_avg:.2f} → {recent_avg:.2f}",
                frequency=len(exp_rewards),
                avg_impact=round(recent_avg - older_avg, 4),
                confidence=min(0.9, 0.5 + abs(recent_avg - older_avg)),
                recommendations=[
                    "Re-evaluate current strategy",
                    "Consider strategy pivot",
                    "Analyze root cause of decay",
                ],
            )

        return None

    def _detect_budget_inefficiency(
        self, experiences: list[LearningExperience]
    ) -> RiskSignal | None:
        """检测预算效率问题."""
        budget_exps = [
            e for e in experiences
            if e.action_type and any(kw in e.action_type.lower() for kw in ["budget", "bid", "scale", "spend"])
        ]
        if len(budget_exps) < 5:
            return None

        exp_rewards = [e.reward.total_reward for e in budget_exps if e.reward is not None]
        if not exp_rewards:
            return None

        neg_rate = sum(1 for r in exp_rewards if r < -0.15) / len(exp_rewards)
        if neg_rate > 0.4:
            return RiskSignal(
                signal_type="budget_inefficiency",
                risk_level="high",
                condition=f"Budget actions have {neg_rate:.0%} negative rate",
                frequency=len(budget_exps),
                avg_impact=round(sum(exp_rewards) / len(exp_rewards), 4),
                confidence=min(0.85, 0.5 + neg_rate * 0.5),
                recommendations=[
                    "Review budget allocation strategy",
                    "Lower budget caps on underperforming campaigns",
                    "Implement stricter budget efficiency thresholds",
                ],
            )

        return None

    def _detect_audience_saturation(
        self,
        experiences: list[LearningExperience],
        attributions: list[AttributionResult],
    ) -> RiskSignal | None:
        """检测受众饱和."""
        audience_exps = [
            e for e in experiences
            if e.action_type and "audience" in e.action_type.lower()
        ]
        if len(audience_exps) < 5:
            return None

        attr_map = {a.decision_id: a for a in attributions if a.decision_id}
        audience_contribs = [
            attr_map[e.decision_id].audience_contribution
            for e in audience_exps
            if e.decision_id in attr_map
        ]

        if not audience_contribs:
            return None

        avg_contrib = sum(audience_contribs) / len(audience_contribs)
        if avg_contrib < -0.1:
            return RiskSignal(
                signal_type="audience_saturation",
                risk_level="medium",
                condition=f"Audience contribution negative: {avg_contrib:.2f}",
                frequency=len(audience_exps),
                avg_impact=round(avg_contrib, 4),
                confidence=0.7,
                recommendations=[
                    "Expand audience targeting",
                    "Test new audience segments",
                    "Refresh lookalike audiences",
                ],
            )

        return None

    # ── Confidence ──────────────────────────────────────────────

    def _compute_overall_confidence(
        self,
        patterns: list[LearnedPattern],
        strategies: list[StrategyInsight],
        risks: list[RiskSignal],
        total_experiences: int,
    ) -> float:
        """计算整体知识置信度."""
        # 样本充足度
        sample_factor = 1.0 - math.exp(-total_experiences / 50.0)

        # 模式置信度
        pattern_conf = (
            sum(p.confidence for p in patterns) / len(patterns) if patterns else 0.0
        )

        # 策略置信度
        strategy_conf = (
            sum(s.confidence for s in strategies) / len(strategies) if strategies else 0.0
        )

        # 综合
        confidence = sample_factor * (0.4 + pattern_conf * 0.35 + strategy_conf * 0.25)
        return round(min(0.95, confidence), 4)


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════


__all__ = [
    "LearningKnowledgeExtractor",
]