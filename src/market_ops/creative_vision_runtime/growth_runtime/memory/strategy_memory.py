"""E13.4.3 StrategyMemory — 增长策略记忆系统.

核心职责:
  从 ExperienceStore + PatternStore 中提取多步增长策略 (Playbook)，
  为 Opportunity Engine 提供完整方案推荐。

与 Pattern Memory 的区别:
  - Pattern: 单步动作规律 (什么情况下什么动作有效？)
  - Strategy: 多步完整方案 (面对问题应该执行什么流程？)

提取逻辑:
  1. 从 ExperienceStore 获取所有经验
  2. 按 entity_id 分组，按时间排序
  3. 提取连续成功动作链 (2+ 步)
  4. 聚合相似链为策略
  5. 关联 PatternMemory 到每个步骤
  6. 计算策略评分和置信度

流程:
  ExperienceStore + PatternStore
      ↓
  _extract_chains()
      ↓
  _aggregate_chains()
      ↓
  _link_patterns()
      ↓
  _build_strategy()
      ↓
  GrowthStrategyPattern[]

连接:
  ExperienceStore + PatternStore → StrategyMemory → OpportunityEngine
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .experience_store import ExperienceStore
from .models import GrowthExperience
from .pattern_store import PatternStore
from .strategy_models import (
    GrowthStrategyPattern,
    StrategyCategory,
    StrategyPerformance,
    StrategyQuality,
    StrategyQuery,
    StrategyStats,
    StrategyStep,
    StrategyTriggerCondition,
)


class StrategyMemory:
    """增长策略记忆 — 从经验中提取和执行多步增长策略.

    用法:
        exp_store = ExperienceStore()
        pattern_store = PatternStore()
        sm = StrategyMemory(exp_store, pattern_store)
        strategies = sm.extract()
        best = sm.recommend(opportunity_type="creative_scale")
    """

    # 质量等级阈值
    QUALITY_THRESHOLDS = {
        StrategyQuality.PROVEN: {"min_executions": 100, "min_success_rate": 0.7},
        StrategyQuality.RELIABLE: {"min_executions": 30, "min_success_rate": 0.6},
        StrategyQuality.EMERGING: {"min_executions": 10, "min_success_rate": 0.5},
        StrategyQuality.EXPERIMENTAL: {"min_executions": 3, "min_success_rate": 0.4},
    }

    def __init__(
        self,
        exp_store: ExperienceStore,
        pattern_store: PatternStore | None = None,
        max_capacity: int = 500,
    ):
        """初始化策略记忆.

        Args:
            exp_store: ExperienceStore 实例
            pattern_store: PatternStore 实例 (可选)
            max_capacity: 最大存储容量
        """
        self._exp_store = exp_store
        self._pattern_store = pattern_store
        self._strategies: list[GrowthStrategyPattern] = []
        self._max_capacity = max_capacity
        self._total_stored: int = 0

    # ═══════════════════════════════════════════════════════════
    # Extraction
    # ═══════════════════════════════════════════════════════════

    def extract(
        self,
        min_chain_length: int = 2,
        min_samples: int = 3,
        experiences: list[GrowthExperience] | None = None,
    ) -> list[GrowthStrategyPattern]:
        """从经验中提取增长策略.

        Args:
            min_chain_length: 最小动作链长度 (至少 2 步)
            min_samples: 每个策略最少样本数
            experiences: 经验列表 (默认从 exp_store 获取全部)

        Returns:
            list[GrowthStrategyPattern]: 按 score 降序排列的策略列表
        """
        if experiences is None:
            experiences = self._exp_store.get_all()

        if len(experiences) < min_samples:
            return []

        # Step 1: 提取动作链
        chains = self._extract_chains(experiences, min_chain_length)

        if not chains:
            return []

        # Step 2: 聚合相似链
        aggregated = self._aggregate_chains(chains, min_samples)

        # Step 3: 构建策略
        strategies: list[GrowthStrategyPattern] = []
        for chain_key, chain_group in aggregated.items():
            strategy = self._build_strategy(chain_key, chain_group)
            if strategy is not None:
                strategy.compute_score()
                strategies.append(strategy)

        # Step 4: 链接 Pattern
        if self._pattern_store is not None:
            strategies = self._link_patterns(strategies)

        # Step 5: 排序
        self._rank_strategies(strategies)

        return strategies

    def extract_and_store(
        self,
        min_chain_length: int = 2,
        min_samples: int = 3,
    ) -> list[str]:
        """提取并自动存储策略."""
        strategies = self.extract(min_chain_length=min_chain_length, min_samples=min_samples)
        return self.store_batch(strategies)

    # ═══════════════════════════════════════════════════════════
    # Chain Extraction
    # ═══════════════════════════════════════════════════════════

    def _extract_chains(
        self,
        experiences: list[GrowthExperience],
        min_chain_length: int,
    ) -> list[list[GrowthExperience]]:
        """从经验中提取连续成功动作链.

        按 entity_id 分组，按时间排序，提取连续成功序列。
        """
        # 按 entity_id 分组
        by_entity: dict[str, list[GrowthExperience]] = defaultdict(list)
        for exp in experiences:
            by_entity[exp.context.entity_id].append(exp)

        chains: list[list[GrowthExperience]] = []

        for entity_id, entity_exps in by_entity.items():
            # 按时间排序
            sorted_exps = sorted(entity_exps, key=lambda e: e.timestamp)

            # 滑动窗口提取连续成功链
            current_chain: list[GrowthExperience] = []
            for exp in sorted_exps:
                if exp.is_successful():
                    current_chain.append(exp)
                else:
                    # 失败打断链
                    if len(current_chain) >= min_chain_length:
                        chains.append(current_chain)
                    current_chain = []

            # 处理末尾链
            if len(current_chain) >= min_chain_length:
                chains.append(current_chain)

        return chains

    def _aggregate_chains(
        self,
        chains: list[list[GrowthExperience]],
        min_samples: int,
    ) -> dict[str, list[list[GrowthExperience]]]:
        """聚合相同动作序列的链.

        返回: {chain_key: [chain1, chain2, ...]}
        """
        grouped: dict[str, list[list[GrowthExperience]]] = defaultdict(list)

        for chain in chains:
            key = self._chain_key(chain)
            grouped[key].append(chain)

        # 过滤掉样本不足的
        return {k: v for k, v in grouped.items() if len(v) >= min_samples}

    def _chain_key(self, chain: list[GrowthExperience]) -> str:
        """生成动作链的聚合键."""
        actions = [e.action_type for e in chain]
        # 使用机会类型 + 动作序列作为键
        opportunity = chain[0].context.opportunity_type if chain else ""
        audience = chain[0].context.audience_segment if chain else ""
        product = chain[0].context.product_id if chain else ""
        return f"{opportunity}|{audience}|{product}|{'→'.join(actions)}"

    # ═══════════════════════════════════════════════════════════
    # Strategy Building
    # ═══════════════════════════════════════════════════════════

    def _build_strategy(
        self,
        chain_key: str,
        chain_group: list[list[GrowthExperience]],
    ) -> GrowthStrategyPattern | None:
        """从一组相似链构建策略."""
        if not chain_group or not chain_group[0]:
            return None

        # 代表性链 (取第一条)
        representative = chain_group[0]

        # 构建步骤
        steps: list[StrategyStep] = []
        for i, exp in enumerate(representative):
            step = StrategyStep(
                order=i + 1,
                action_type=exp.action_type,
                action_params=exp.action_params,
                expected_impact=self._summarize_step_impact(exp, chain_group, i),
                approval_level="auto",
                timeout_hours=24.0,
            )
            steps.append(step)

        # 构建触发条件
        first_exp = representative[0]
        trigger = StrategyTriggerCondition(
            scenario=self._infer_scenario(first_exp),
            opportunity_type=first_exp.context.opportunity_type,
            signal_types=first_exp.context.trigger_signals,
            audience_segment=first_exp.context.audience_segment,
            product_category=first_exp.context.product_id,
        )

        # 计算表现
        performance = self._compute_strategy_performance(chain_group)

        # 推断类别
        category = self._infer_category(first_exp, steps)

        # 策略名称
        name = self._generate_name(first_exp, steps)

        # 描述
        description = self._generate_description(first_exp, steps, performance)

        # 来源
        all_exp_ids: list[str] = []
        for chain in chain_group:
            for exp in chain:
                all_exp_ids.append(exp.experience_id)

        strategy = GrowthStrategyPattern(
            name=name,
            category=category,
            trigger=trigger,
            steps=steps,
            performance=performance,
            source_experience_ids=list(set(all_exp_ids)),
            tags=self._extract_chain_tags(chain_group),
            description=description,
            prerequisites="",
            risks="",
        )

        strategy.compute_score()
        return strategy

    def _compute_strategy_performance(
        self,
        chain_group: list[list[GrowthExperience]],
    ) -> StrategyPerformance:
        """计算策略的历史表现."""
        # 扁平化所有链中的所有经验
        all_exps: list[GrowthExperience] = []
        for chain in chain_group:
            all_exps.extend(chain)

        total = len(chain_group)  # 链的数量 = 执行次数
        # 判断整条链是否成功: 链中所有经验都成功才算成功
        successful = sum(
            1 for chain in chain_group
            if all(e.is_successful() for e in chain)
        )
        success_rate = round(successful / total, 4) if total > 0 else 0.0

        # 平均奖励: 链中所有经验的平均 reward
        avg_reward = round(sum(e.reward for e in all_exps) / len(all_exps), 4) if all_exps else 0.0

        # 平均 ROAS 变化
        roas_deltas = [
            e.outcome.metrics_delta.get("roas", 0.0)
            for e in all_exps
            if "roas" in e.outcome.metrics_delta
        ]
        avg_roas = round(sum(roas_deltas) / len(roas_deltas), 4) if roas_deltas else 0.0

        # 时间范围
        timestamps = sorted([e.timestamp for e in all_exps])
        first_seen = timestamps[0] if timestamps else ""
        last_seen = timestamps[-1] if timestamps else ""

        # 趋势 (最近 10 条链)
        recent_chains = sorted(chain_group, key=lambda c: max(e.timestamp for e in c), reverse=True)[:10]
        trend = [
            1.0 if all(e.is_successful() for e in chain) else 0.0
            for chain in recent_chains
        ]

        # 质量
        quality = self._assign_quality(total, success_rate)

        return StrategyPerformance(
            total_executions=total,
            successful_executions=successful,
            success_rate=success_rate,
            avg_reward=avg_reward,
            avg_roas_change=avg_roas,
            avg_duration_hours=0.0,
            quality=quality,
            first_seen=first_seen,
            last_seen=last_seen,
            trend=trend,
        )

    def _assign_quality(self, executions: int, success_rate: float) -> StrategyQuality:
        """根据执行次数和成功率分配质量等级."""
        for quality, thresholds in self.QUALITY_THRESHOLDS.items():
            if executions >= thresholds["min_executions"] and success_rate >= thresholds["min_success_rate"]:
                return quality
        return StrategyQuality.UNTESTED

    def _infer_scenario(self, exp: GrowthExperience) -> str:
        """从经验推断场景描述."""
        opp = exp.context.opportunity_type
        scenario_map = {
            "creative_scale": "Creative scaling opportunity detected",
            "creative_fatigue": "Creative fatigue detected",
            "creative_refresh": "Creative needs refresh",
            "roas_drop": "ROAS dropping below threshold",
            "roas_recovery": "ROAS recovery opportunity",
            "budget_waste": "Budget waste detected",
            "scale_opportunity": "Scaling opportunity identified",
            "audience_expansion": "Audience expansion opportunity",
        }
        if opp in scenario_map:
            return scenario_map[opp]
        signals = exp.context.trigger_signals
        if signals:
            return f"Triggered by signals: {', '.join(signals[:3])}"
        return f"Growth opportunity: {opp}"

    def _infer_category(
        self,
        first_exp: GrowthExperience,
        steps: list[StrategyStep],
    ) -> StrategyCategory:
        """推断策略类别."""
        opp = first_exp.context.opportunity_type
        action_types = [s.action_type for s in steps]

        if "creative_scale" in opp or "scale_opportunity" in opp:
            return StrategyCategory.CREATIVE_SCALE
        if "creative_fatigue" in opp or "creative_refresh" in opp:
            return StrategyCategory.CREATIVE_REVIVAL
        if "roas" in opp:
            return StrategyCategory.ROAS_RECOVERY
        if "budget" in opp:
            return StrategyCategory.BUDGET_OPTIMIZATION
        if "audience" in opp:
            return StrategyCategory.AUDIENCE_EXPANSION
        if any(a in action_types for a in ["launch_campaign", "create_population"]):
            return StrategyCategory.NEW_LAUNCH
        return StrategyCategory.GENERAL

    def _generate_name(
        self,
        first_exp: GrowthExperience,
        steps: list[StrategyStep],
    ) -> str:
        """生成策略名称."""
        opp = first_exp.context.opportunity_type
        audience = first_exp.context.audience_segment
        product = first_exp.context.product_id

        name_parts = []
        if product:
            name_parts.append(product.upper() if len(product) <= 5 else product)
        if audience:
            name_parts.append(audience.replace("_", " ").title())

        opp_name = opp.replace("_", " ").title()
        name_parts.append(opp_name)

        return f"{' '.join(name_parts)} Pipeline"

    def _generate_description(
        self,
        first_exp: GrowthExperience,
        steps: list[StrategyStep],
        performance: StrategyPerformance,
    ) -> str:
        """生成策略描述."""
        step_descs = [f"{s.order}. {s.action_type}" for s in steps]
        steps_text = " → ".join(step_descs)
        return (
            f"Multi-step strategy for {first_exp.context.opportunity_type}. "
            f"Steps: {steps_text}. "
            f"Historical success rate: {performance.success_rate:.0%} "
            f"({performance.total_executions} executions)."
        )

    def _summarize_step_impact(
        self,
        exp: GrowthExperience,
        chain_group: list[list[GrowthExperience]],
        step_index: int,
    ) -> str:
        """总结某一步骤在所有链中的预期影响."""
        impacts: list[str] = []
        for chain in chain_group:
            if step_index < len(chain):
                chain_exp = chain[step_index]
                if chain_exp.outcome.actual_impact:
                    impacts.append(chain_exp.outcome.actual_impact)

        if impacts:
            from collections import Counter
            return Counter(impacts).most_common(1)[0][0]

        # 降级到指标变化
        metrics_deltas: dict[str, list[float]] = defaultdict(list)
        for chain in chain_group:
            if step_index < len(chain):
                for metric, delta in chain[step_index].outcome.metrics_delta.items():
                    metrics_deltas[metric].append(delta)

        if metrics_deltas:
            parts = [
                f"{k}: {sum(v)/len(v):+.2f}"
                for k, v in sorted(metrics_deltas.items())[:3]
            ]
            return ", ".join(parts)

        return f"Step {step_index + 1}: {exp.action_type}"

    def _extract_chain_tags(self, chain_group: list[list[GrowthExperience]]) -> list[str]:
        """从链组中提取标签."""
        tags: set[str] = set()
        for chain in chain_group:
            for exp in chain:
                for tag in exp.tags:
                    tags.add(tag)
        return sorted(tags)

    # ═══════════════════════════════════════════════════════════
    # Pattern Linking
    # ═══════════════════════════════════════════════════════════

    def _link_patterns(
        self,
        strategies: list[GrowthStrategyPattern],
    ) -> list[GrowthStrategyPattern]:
        """将策略步骤链接到已验证的 PatternMemory."""
        if self._pattern_store is None:
            return strategies

        for strategy in strategies:
            for step in strategy.steps:
                pattern = self._pattern_store.get_best_pattern(
                    opportunity_type=strategy.trigger.opportunity_type,
                    action_type=step.action_type,
                )
                if pattern is not None:
                    step.pattern_id = pattern.pattern_id
                    strategy.source_pattern_ids.append(pattern.pattern_id)

            # 去重 source_pattern_ids
            strategy.source_pattern_ids = list(set(strategy.source_pattern_ids))

        return strategies

    # ═══════════════════════════════════════════════════════════
    # Store
    # ═══════════════════════════════════════════════════════════

    def store(self, strategy: GrowthStrategyPattern) -> str:
        """存储一条策略.

        Args:
            strategy: GrowthStrategyPattern 实例

        Returns:
            strategy_id: 策略ID
        """
        # 检查是否已存在相同策略 (相同 trigger + 相同步骤序列)
        existing = self._find_existing(strategy)
        if existing is not None:
            # 更新现有策略
            existing.performance = strategy.performance
            existing.score = strategy.score
            existing.confidence = strategy.confidence
            existing.source_experience_ids = list(
                set(existing.source_experience_ids + strategy.source_experience_ids)
            )
            existing.source_pattern_ids = list(
                set(existing.source_pattern_ids + strategy.source_pattern_ids)
            )
            existing.tags = list(set(existing.tags + strategy.tags))
            existing.updated_at = datetime.now(timezone.utc).isoformat()
            existing.compute_score()
            return existing.strategy_id

        self._strategies.append(strategy)
        self._total_stored += 1

        # 容量控制
        if len(self._strategies) > self._max_capacity:
            overflow = len(self._strategies) - self._max_capacity
            self._strategies = self._strategies[overflow:]

        return strategy.strategy_id

    def store_batch(self, strategies: list[GrowthStrategyPattern]) -> list[str]:
        """批量存储策略."""
        return [self.store(s) for s in strategies]

    def _find_existing(self, strategy: GrowthStrategyPattern) -> GrowthStrategyPattern | None:
        """查找已存在的相同策略."""
        new_key = self._strategy_match_key(strategy)
        for s in self._strategies:
            if self._strategy_match_key(s) == new_key:
                return s
        return None

    def _strategy_match_key(self, strategy: GrowthStrategyPattern) -> str:
        """生成策略匹配键."""
        actions = "→".join(s.action_type for s in strategy.steps)
        return (
            f"{strategy.trigger.opportunity_type}"
            f"|{strategy.trigger.audience_segment}"
            f"|{strategy.trigger.product_category}"
            f"|{actions}"
        )

    # ═══════════════════════════════════════════════════════════
    # Query
    # ═══════════════════════════════════════════════════════════

    def query(self, q: StrategyQuery) -> list[GrowthStrategyPattern]:
        """按条件查询策略.

        Args:
            q: StrategyQuery 查询条件

        Returns:
            list[GrowthStrategyPattern]: 匹配的策略列表
        """
        results = self._strategies

        # 场景过滤
        if q.scenario:
            results = [
                s for s in results
                if q.scenario.lower() in s.trigger.scenario.lower()
            ]

        # 机会类型过滤
        if q.opportunity_types:
            results = [
                s for s in results
                if s.trigger.opportunity_type in q.opportunity_types
            ]

        # 类别过滤
        if q.categories:
            results = [
                s for s in results
                if s.category.value in q.categories
            ]

        # 受众过滤
        if q.audience_segment:
            results = [
                s for s in results
                if s.trigger.audience_segment == q.audience_segment
            ]

        # 产品类别过滤
        if q.product_category:
            results = [
                s for s in results
                if s.trigger.product_category == q.product_category
            ]

        # 执行次数过滤
        if q.min_executions > 0:
            results = [
                s for s in results
                if s.performance.total_executions >= q.min_executions
            ]

        # 成功率过滤
        if q.min_success_rate > 0:
            results = [
                s for s in results
                if s.performance.success_rate >= q.min_success_rate
            ]

        # 评分过滤
        if q.min_score > 0:
            results = [
                s for s in results
                if s.score >= q.min_score
            ]

        # 可执行过滤
        if q.actionable_only:
            results = [s for s in results if s.is_actionable()]

        # 已验证过滤
        if q.proven_only:
            results = [s for s in results if s.is_proven()]

        # 质量等级过滤
        if q.quality_levels:
            results = [
                s for s in results
                if s.performance.quality.value in q.quality_levels
            ]

        # 标签过滤
        if q.tags:
            results = [
                s for s in results
                if any(t in s.tags for t in q.tags)
            ]

        # 排序
        if q.sort_by == "score":
            results = sorted(results, key=lambda s: -s.score if q.sort_desc else s.score)
        elif q.sort_by == "executions":
            results = sorted(results, key=lambda s: -s.performance.total_executions if q.sort_desc else s.performance.total_executions)
        elif q.sort_by == "success_rate":
            results = sorted(results, key=lambda s: -s.performance.success_rate if q.sort_desc else s.performance.success_rate)
        elif q.sort_by == "avg_reward":
            results = sorted(results, key=lambda s: -s.performance.avg_reward if q.sort_desc else s.performance.avg_reward)

        # 数量限制
        if q.limit > 0 and len(results) > q.limit:
            results = results[:q.limit]

        return results

    # ═══════════════════════════════════════════════════════════
    # Recommendation
    # ═══════════════════════════════════════════════════════════

    def recommend(
        self,
        opportunity_type: str = "",
        signal_types: list[str] | None = None,
        audience_segment: str = "",
        product_category: str = "",
        actionable_only: bool = True,
        top_n: int = 5,
    ) -> list[GrowthStrategyPattern]:
        """为机会推荐最佳策略.

        Args:
            opportunity_type: 机会类型
            signal_types: 信号类型列表
            audience_segment: 受众分群
            product_category: 产品类别
            actionable_only: 仅返回可执行策略
            top_n: 返回前 N 个策略

        Returns:
            list[GrowthStrategyPattern]: 推荐策略列表 (按匹配度 + 评分)
        """
        if not self._strategies:
            return []

        # 计算每个策略的匹配度
        scored: list[tuple[GrowthStrategyPattern, float]] = []
        for strategy in self._strategies:
            if actionable_only and not strategy.is_actionable():
                continue

            match_score = self._compute_match_score(
                strategy,
                opportunity_type=opportunity_type,
                signal_types=signal_types,
                audience_segment=audience_segment,
                product_category=product_category,
            )

            if match_score > 0:
                # 综合评分 = 匹配度 × 策略评分
                combined = match_score * strategy.score
                scored.append((strategy, combined))

        # 排序
        scored.sort(key=lambda x: -x[1])
        return [s for s, _ in scored[:top_n]]

    def recommend_best(
        self,
        opportunity_type: str = "",
        signal_types: list[str] | None = None,
        audience_segment: str = "",
        product_category: str = "",
    ) -> GrowthStrategyPattern | None:
        """推荐单个最佳策略."""
        results = self.recommend(
            opportunity_type=opportunity_type,
            signal_types=signal_types,
            audience_segment=audience_segment,
            product_category=product_category,
            top_n=1,
        )
        return results[0] if results else None

    def _compute_match_score(
        self,
        strategy: GrowthStrategyPattern,
        opportunity_type: str = "",
        signal_types: list[str] | None = None,
        audience_segment: str = "",
        product_category: str = "",
    ) -> float:
        """计算策略与机会的匹配度 [0, 1]."""
        score = 0.0
        weight_total = 0.0

        # 机会类型匹配 (权重: 0.4)
        if opportunity_type:
            weight_total += 0.4
            if strategy.trigger.opportunity_type == opportunity_type:
                score += 0.4

        # 信号类型匹配 (权重: 0.2)
        if signal_types:
            weight_total += 0.2
            if any(s in strategy.trigger.signal_types for s in signal_types):
                score += 0.2

        # 受众匹配 (权重: 0.2)
        if audience_segment:
            weight_total += 0.2
            if strategy.trigger.audience_segment == audience_segment:
                score += 0.2

        # 产品类别匹配 (权重: 0.2)
        if product_category:
            weight_total += 0.2
            if strategy.trigger.product_category == product_category:
                score += 0.2

        if weight_total == 0:
            return 1.0  # 无过滤条件，所有策略匹配

        return score / weight_total

    # ═══════════════════════════════════════════════════════════
    # Convenience Methods
    # ═══════════════════════════════════════════════════════════

    def get_by_opportunity(self, opportunity_type: str, limit: int = 20) -> list[GrowthStrategyPattern]:
        """按机会类型获取策略."""
        return self.query(StrategyQuery(
            opportunity_types=[opportunity_type],
            limit=limit,
            sort_by="score",
            sort_desc=True,
        ))

    def get_by_category(self, category: StrategyCategory, limit: int = 20) -> list[GrowthStrategyPattern]:
        """按类别获取策略."""
        return self.query(StrategyQuery(
            categories=[category.value],
            limit=limit,
            sort_by="score",
            sort_desc=True,
        ))

    def get_top_strategies(self, n: int = 10) -> list[GrowthStrategyPattern]:
        """获取最高评分策略."""
        return self.query(StrategyQuery(limit=n, sort_by="score", sort_desc=True))

    def get_actionable_strategies(self, n: int = 20) -> list[GrowthStrategyPattern]:
        """获取可执行策略."""
        return self.query(StrategyQuery(
            actionable_only=True,
            limit=n,
            sort_by="score",
            sort_desc=True,
        ))

    def get_proven_strategies(self, n: int = 20) -> list[GrowthStrategyPattern]:
        """获取已验证策略."""
        return self.query(StrategyQuery(
            proven_only=True,
            limit=n,
            sort_by="score",
            sort_desc=True,
        ))

    def get_all(self) -> list[GrowthStrategyPattern]:
        """获取所有策略."""
        return list(self._strategies)

    # ═══════════════════════════════════════════════════════════
    # Statistics
    # ═══════════════════════════════════════════════════════════

    def get_stats(self) -> StrategyStats:
        """获取策略库统计."""
        strategies = self._strategies
        total = len(strategies)

        if total == 0:
            return StrategyStats()

        actionable = [s for s in strategies if s.is_actionable()]
        proven = [s for s in strategies if s.is_proven()]
        avg_score = round(sum(s.score for s in strategies) / total, 4)
        avg_executions = round(sum(s.performance.total_executions for s in strategies) / total, 2)
        avg_steps = round(sum(len(s.steps) for s in strategies) / total, 2)

        # 按类别统计
        by_category: dict[str, dict[str, float]] = {}
        cat_groups: dict[str, list[GrowthStrategyPattern]] = defaultdict(list)
        for s in strategies:
            cat_groups[s.category.value].append(s)
        for cat, group in cat_groups.items():
            by_category[cat] = {
                "count": len(group),
                "avg_score": round(sum(s.score for s in group) / len(group), 4) if group else 0,
            }

        # 按质量统计
        by_quality: dict[str, int] = {}
        for s in strategies:
            q = s.performance.quality.value
            by_quality[q] = by_quality.get(q, 0) + 1

        # Top 策略
        top = sorted(strategies, key=lambda s: -s.score)[:10]
        top_strategies = [
            {
                "strategy_id": s.strategy_id,
                "name": s.name,
                "steps": s.get_step_count(),
                "score": s.score,
                "executions": s.performance.total_executions,
                "success_rate": s.performance.success_rate,
            }
            for s in top
        ]

        return StrategyStats(
            total_strategies=total,
            total_actionable=len(actionable),
            total_proven=len(proven),
            by_category=by_category,
            by_quality=by_quality,
            top_strategies=top_strategies,
            avg_score=avg_score,
            avg_executions=avg_executions,
            avg_steps=avg_steps,
        )

    # ═══════════════════════════════════════════════════════════
    # Management
    # ═══════════════════════════════════════════════════════════

    @property
    def count(self) -> int:
        return len(self._strategies)

    @property
    def total_stored(self) -> int:
        return self._total_stored

    def clear(self) -> None:
        self._strategies.clear()

    def _rank_strategies(self, strategies: list[GrowthStrategyPattern]) -> None:
        """按 score 降序排序."""
        strategies.sort(key=lambda s: -s.score)