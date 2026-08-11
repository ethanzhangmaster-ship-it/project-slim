"""E13.4.5 MemoryEvolution — 记忆进化引擎.

核心职责:
  让 Memory 不再只是存储，而是自动进化——合并相似知识、升级置信度、
  建立跨层引用、管理知识衰减，形成真正的 Self-Improving Growth Agent。

进化流程:
  1. Consolidate: 合并相似 Pattern/Strategy/Failure
  2. Evolve Patterns: 新经验升级/降级已有模式置信度
  3. Evolve Strategies: 新模式出现时更新策略步骤引用
  4. Cross-Reference: 建立 Pattern ↔ Strategy ↔ Failure 知识图谱
  5. Decay: 过期知识自动衰减
  6. Track: 记录完整进化历史

用法:
    evo = MemoryEvolution(pattern_store, strategy_memory, failure_memory)
    evo.evolve(experience_store)  # 触发全量进化
    metrics = evo.get_metrics()   # 查看进化质量
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from .evolution_models import (
    ConsolidationResult,
    EvolutionConfig,
    EvolutionEvent,
    EvolutionEventType,
    EvolutionMetrics,
    EvolutionTarget,
    KnowledgeGraph,
)
from .failure_models import FailurePattern
from .models import PatternMemory


class MemoryEvolution:
    """记忆进化引擎 — 驱动记忆从存储到进化的升级.

    将 Pattern Memory、Strategy Memory、Failure Memory 三层知识
    进行自动合并、升级、引用和衰减，使决策智能持续提升。

    用法:
        evo = MemoryEvolution(pattern_store, strategy_memory, failure_memory)
        evo.evolve(experience_store)
        print(evo.summary())
    """

    def __init__(
        self,
        pattern_store: Any = None,
        strategy_memory: Any = None,
        failure_memory: Any = None,
        config: EvolutionConfig | None = None,
    ):
        """初始化进化引擎.

        Args:
            pattern_store: PatternStore 实例
            strategy_memory: StrategyMemory 实例
            failure_memory: FailureMemory 实例
            config: 进化参数配置
        """
        self._pattern_store = pattern_store
        self._strategy_memory = strategy_memory
        self._failure_memory = failure_memory
        self._config = config or EvolutionConfig()

        # 进化历史
        self._history: list[EvolutionEvent] = []
        self._knowledge_graph = KnowledgeGraph()

    # ═══════════════════════════════════════════════════════════
    # Main Evolution Entry Point
    # ═══════════════════════════════════════════════════════════

    def evolve(
        self,
        experience_store: Any = None,
    ) -> EvolutionMetrics:
        """触发全量进化 — 对所有记忆层进行进化操作.

        Args:
            experience_store: ExperienceStore 实例 (用于升级已有模式)

        Returns:
            EvolutionMetrics: 进化质量指标
        """
        events: list[EvolutionEvent] = []

        # Step 1: Consolidate (合并相似知识)
        if self._config.auto_consolidate:
            events += self._consolidate_patterns()
            events += self._consolidate_failures()

        # Step 2: Evolve Patterns (经验升级/降级)
        if self._config.auto_upgrade and experience_store is not None:
            events += self._evolve_patterns(experience_store)

        # Step 3: Evolve Strategies (更新策略引用)
        if self._config.auto_upgrade:
            events += self._evolve_strategies()

        # Step 4: Cross-Reference (建立跨层引用)
        if self._config.auto_cross_reference:
            events += self._build_cross_references()

        # Step 5: Decay (过期衰减)
        if self._config.auto_decay:
            events += self._apply_decay()

        # 记录历史
        self._history.extend(events)
        self._trim_history()

        # 更新知识图谱
        self._knowledge_graph.last_updated = datetime.now(timezone.utc).isoformat()

        return self._compute_metrics()

    # ═══════════════════════════════════════════════════════════
    # Consolidation
    # ═══════════════════════════════════════════════════════════

    def _consolidate_patterns(self) -> list[EvolutionEvent]:
        """合并相似 Pattern — 将相同 action+opportunity 的模式合并升级."""
        events: list[EvolutionEvent] = []
        if self._pattern_store is None:
            return events

        patterns = self._pattern_store.get_all()
        if len(patterns) < 2:
            return events

        # 按 (action_type, opportunity_type) 分组
        groups: dict[str, list[PatternMemory]] = defaultdict(list)
        for p in patterns:
            key = f"{p.condition.action_type}|{p.condition.opportunity_type}"
            groups[key].append(p)

        for group_key, group in groups.items():
            if len(group) < 2:
                continue

            # 计算相似度: 同组内模式应该相似，检查是否值得合并
            result = self._merge_pattern_group(group)
            if result is not None and result.improvement >= self._config.min_confidence_improvement:
                # 移除旧模式 (通过直接操作 _patterns 列表)
                for pid in result.source_ids[1:]:  # 保留第一个，移除其余
                    self._pattern_store._patterns = [
                        p for p in self._pattern_store._patterns if p.pattern_id != pid
                    ]
                # 更新第一个模式为合并后的结果
                merged = self._build_merged_pattern(group, result)
                self._pattern_store._patterns = [
                    merged if p.pattern_id == result.source_ids[0] else p
                    for p in self._pattern_store._patterns
                ]
                events.extend(result.events)

        return events

    def _merge_pattern_group(
        self,
        group: list[PatternMemory],
    ) -> ConsolidationResult | None:
        """合并一组相似模式."""
        if len(group) < 2:
            return None

        source_ids = [p.pattern_id for p in group]
        avg_conf_before = round(sum(p.performance.success_rate for p in group) / len(group), 4)

        # 合并后置信度: 加权平均 (权重 = 样本数)
        total_samples = sum(p.performance.samples for p in group)
        if total_samples == 0:
            return None

        weighted_confidence = round(
            sum(p.performance.success_rate * p.performance.samples for p in group) / total_samples,
            4,
        )

        improvement = round(weighted_confidence - avg_conf_before, 4)
        if improvement < self._config.min_confidence_improvement:
            return None

        # 生成合并事件
        event = EvolutionEvent(
            event_type=EvolutionEventType.CONSOLIDATE,
            target_type=EvolutionTarget.PATTERN,
            source_ids=source_ids,
            target_id=source_ids[0],  # 保留第一个ID作为合并后ID
            before_state={"avg_confidence": avg_conf_before, "pattern_count": len(group)},
            after_state={"confidence": weighted_confidence, "total_evidence": total_samples},
            delta={"confidence": improvement, "evidence": float(total_samples)},
            reason=f"Merged {len(group)} similar patterns with {total_samples} total evidence",
        )

        return ConsolidationResult(
            consolidated_id=source_ids[0],
            source_ids=source_ids,
            target_type=EvolutionTarget.PATTERN,
            name=f"Pattern {group[0].condition.action_type}",
            confidence_before=avg_conf_before,
            confidence_after=weighted_confidence,
            total_evidence=total_samples,
            improvement=improvement,
            merged_fields=["performance.samples", "performance.success_rate"],
            events=[event],
        )

    def _build_merged_pattern(
        self,
        group: list[PatternMemory],
        result: ConsolidationResult,
    ) -> PatternMemory:
        """构建合并后的模式."""
        base = group[0]
        total_samples = sum(p.performance.samples for p in group)
        total_success = sum(p.performance.success_count for p in group)
        weighted_reward = (
            round(sum(p.performance.avg_reward * p.performance.samples for p in group) / total_samples, 4)
            if total_samples > 0
            else base.performance.avg_reward
        )

        base.performance.samples = total_samples
        base.performance.success_count = total_success
        base.performance.success_rate = result.confidence_after
        base.performance.avg_reward = weighted_reward
        base.performance.last_seen = datetime.now(timezone.utc).isoformat()

        return base

    def _consolidate_failures(self) -> list[EvolutionEvent]:
        """合并相似 Failure Pattern."""
        events: list[EvolutionEvent] = []
        if self._failure_memory is None:
            return events

        failures = self._failure_memory.get_all()
        if len(failures) < 2:
            return events

        # 按 (blocked_action, opportunity_type) 分组
        groups: dict[str, list[FailurePattern]] = defaultdict(list)
        for f in failures:
            key = f"{f.blocked_action}|{f.condition.opportunity_type}"
            groups[key].append(f)

        for group_key, group in groups.items():
            if len(group) < 2:
                continue

            source_ids = [f.failure_id for f in group]
            avg_fr_before = round(sum(f.failure_rate for f in group) / len(group), 4)
            total_attempts = sum(f.total_attempts for f in group)
            if total_attempts == 0:
                continue

            weighted_fr = round(
                sum(f.failure_rate * f.total_attempts for f in group) / total_attempts,
                4,
            )
            improvement = round(weighted_fr - avg_fr_before, 4)

            # 保留第一个，删除其余
            keeper = group[0]
            keeper.failure_rate = weighted_fr
            keeper.total_attempts = total_attempts
            keeper.failed_attempts = int(total_attempts * weighted_fr)
            keeper.compute_confidence()
            keeper.compute_severity()

            for f in group[1:]:
                self._failure_memory._patterns.remove(f)

            event = EvolutionEvent(
                event_type=EvolutionEventType.CONSOLIDATE,
                target_type=EvolutionTarget.FAILURE,
                source_ids=source_ids,
                target_id=keeper.failure_id,
                before_state={"avg_failure_rate": avg_fr_before},
                after_state={"failure_rate": weighted_fr, "total_attempts": total_attempts},
                delta={"failure_rate": improvement},
                reason=f"Merged {len(group)} failure patterns with {total_attempts} total attempts",
            )
            events.append(event)

        return events

    # ═══════════════════════════════════════════════════════════
    # Pattern Evolution
    # ═══════════════════════════════════════════════════════════

    def _evolve_patterns(self, experience_store: Any) -> list[EvolutionEvent]:
        """Pattern 进化 — 新经验升级/降级已有模式置信度."""
        events: list[EvolutionEvent] = []
        if self._pattern_store is None:
            return events

        recent_experiences = experience_store.get_all()
        if not recent_experiences:
            return events

        patterns = self._pattern_store.get_all()

        for pattern in patterns:
            # 查找匹配该模式的新经验
            matching = self._find_matching_experiences(pattern, recent_experiences)
            if not matching:
                continue

            # 计算新证据对模式的影响
            new_success_rate = sum(1 for e in matching if e.is_successful()) / len(matching)
            old_rate = pattern.performance.success_rate

            # 确定是升级还是降级
            if abs(new_success_rate - old_rate) < self._config.min_confidence_improvement:
                continue

            event_type = EvolutionEventType.UPGRADE if new_success_rate > old_rate else EvolutionEventType.DOWNGRADE

            before = {"confidence": old_rate, "samples": pattern.performance.samples}
            # 更新模式
            pattern.performance.samples += len(matching)
            pattern.performance.success_count += sum(1 for e in matching if e.is_successful())
            pattern.performance.success_rate = round(
                pattern.performance.success_count / pattern.performance.samples, 4
            )
            pattern.performance.last_seen = datetime.now(timezone.utc).isoformat()
            after = {"confidence": pattern.performance.success_rate, "samples": pattern.performance.samples}

            event = EvolutionEvent(
                event_type=event_type,
                target_type=EvolutionTarget.PATTERN,
                source_ids=[pattern.pattern_id],
                target_id=pattern.pattern_id,
                before_state=before,
                after_state=after,
                delta={"confidence": round(after["confidence"] - before["confidence"], 4)},
                reason=f"New evidence: {len(matching)} experiences ({new_success_rate:.0%} success)",
            )
            events.append(event)

        return events

    def _find_matching_experiences(
        self,
        pattern: PatternMemory,
        experiences: list[Any],
    ) -> list[Any]:
        """查找匹配模式的新经验."""
        matching = []
        for exp in experiences:
            if exp.action_type != pattern.condition.action_type:
                continue
            if (pattern.condition.opportunity_type
                    and exp.context.opportunity_type != pattern.condition.opportunity_type):
                continue
            if (pattern.condition.audience_segment
                    and exp.context.audience_segment != pattern.condition.audience_segment):
                continue
            matching.append(exp)
        return matching

    # ═══════════════════════════════════════════════════════════
    # Strategy Evolution
    # ═══════════════════════════════════════════════════════════

    def _evolve_strategies(self) -> list[EvolutionEvent]:
        """Strategy 进化 — 新模式出现时更新策略步骤引用."""
        events: list[EvolutionEvent] = []
        if self._strategy_memory is None or self._pattern_store is None:
            return events

        strategies = self._strategy_memory.get_all()
        patterns = self._pattern_store.get_all()

        for strategy in strategies:
            for step in strategy.steps:
                # 如果步骤已有 pattern_id，检查是否需要更新
                if step.pattern_id:
                    matching = [p for p in patterns if p.pattern_id == step.pattern_id]
                    if matching and matching[0].performance.success_rate > 0.7:
                        step.approval_level = "auto"
                    continue

                # 尝试为步骤找到匹配的 pattern
                best_match = self._find_best_pattern_for_step(step, patterns)
                if best_match is not None:
                    before = step.pattern_id or "none"
                    step.pattern_id = best_match.pattern_id
                    event = EvolutionEvent(
                        event_type=EvolutionEventType.CROSS_REFERENCE,
                        target_type=EvolutionTarget.STRATEGY,
                        source_ids=[best_match.pattern_id],
                        target_id=strategy.strategy_id,
                        before_state={"step_pattern": before},
                        after_state={"step_pattern": best_match.pattern_id},
                        delta={"linked_patterns": 1.0},
                        reason=f"Step {step.order} ({step.action_type}) linked to pattern {best_match.pattern_id}",
                    )
                    events.append(event)

        return events

    def _find_best_pattern_for_step(
        self,
        step: Any,
        patterns: list[PatternMemory],
    ) -> PatternMemory | None:
        """为策略步骤找到最佳匹配模式."""
        candidates = []
        for p in patterns:
            if p.condition.action_type == step.action_type:
                score = p.performance.success_rate * (1.0 if p.performance.samples >= 10 else 0.5)
                candidates.append((score, p))

        if not candidates:
            return None

        candidates.sort(key=lambda x: -x[0])
        best_score, best_pattern = candidates[0]

        # 只有高质量模式才值得引用
        if best_score >= 0.4:
            return best_pattern
        return None

    # ═══════════════════════════════════════════════════════════
    # Cross-Reference
    # ═══════════════════════════════════════════════════════════

    def _build_cross_references(self) -> list[EvolutionEvent]:
        """建立跨层知识图谱 — Pattern ↔ Strategy ↔ Failure."""
        events: list[EvolutionEvent] = []
        kg = KnowledgeGraph()
        cross_refs = 0

        # 1. Pattern → Strategy
        if self._pattern_store is not None and self._strategy_memory is not None:
            patterns = self._pattern_store.get_all()
            strategies = self._strategy_memory.get_all()

            for strategy in strategies:
                kg.strategy_to_patterns[strategy.strategy_id] = []
                for step in strategy.steps:
                    if step.pattern_id:
                        kg.strategy_to_patterns[strategy.strategy_id].append(step.pattern_id)
                        if step.pattern_id not in kg.pattern_to_strategies:
                            kg.pattern_to_strategies[step.pattern_id] = []
                        kg.pattern_to_strategies[step.pattern_id].append({
                            "strategy_id": strategy.strategy_id,
                            "strategy_name": strategy.name,
                            "step_order": step.order,
                        })
                        cross_refs += 1

            # 孤立模式
            for p in patterns:
                if p.pattern_id not in kg.pattern_to_strategies:
                    kg.isolated_patterns.append(p.pattern_id)

            # 孤立策略步骤
            for strategy in strategies:
                for step in strategy.steps:
                    if not step.pattern_id:
                        kg.isolated_strategies.append(
                            f"{strategy.strategy_id}:step_{step.order}"
                        )

        # 2. Failure → Pattern
        if self._failure_memory is not None and self._pattern_store is not None:
            failures = self._failure_memory.get_all()
            patterns = self._pattern_store.get_all() if self._pattern_store else []

            for failure in failures:
                kg.failure_to_patterns[failure.failure_id] = []
                kg.failure_to_strategies[failure.failure_id] = []

                for p in patterns:
                    if p.condition.action_type == failure.blocked_action:
                        kg.failure_to_patterns[failure.failure_id].append(p.pattern_id)
                        cross_refs += 1

        # 3. 计算密度
        kg.cross_references = cross_refs
        total_nodes = len(kg.pattern_to_strategies) + len(kg.strategy_to_patterns)
        if total_nodes > 0:
            max_edges = total_nodes * (total_nodes - 1)
            kg.graph_density = round(cross_refs / max_edges, 4) if max_edges > 0 else 0.0

        # 如果有新的跨层引用建立，记录事件
        if cross_refs > 0:
            event = EvolutionEvent(
                event_type=EvolutionEventType.CROSS_REFERENCE,
                target_type=EvolutionTarget.CROSS_LAYER,
                before_state={"cross_references": self._knowledge_graph.cross_references},
                after_state={"cross_references": cross_refs},
                delta={"new_references": float(cross_refs)},
                reason=f"Built cross-layer knowledge graph with {cross_refs} references, "
                        f"{len(kg.isolated_patterns)} isolated patterns, "
                        f"{len(kg.isolated_strategies)} isolated strategy steps",
            )
            events.append(event)

        self._knowledge_graph = kg
        return events

    # ═══════════════════════════════════════════════════════════
    # Decay
    # ═══════════════════════════════════════════════════════════

    def _apply_decay(self) -> list[EvolutionEvent]:
        """知识衰减 — 长期未使用的知识降低置信度."""
        events: list[EvolutionEvent] = []
        now = datetime.now(timezone.utc)
        decay_threshold = now - timedelta(days=self._config.decay_days)

        # Pattern 衰减
        if self._pattern_store is not None:
            for pattern in self._pattern_store.get_all():
                if not pattern.performance.last_seen:
                    continue
                try:
                    last_seen = datetime.fromisoformat(pattern.performance.last_seen.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    continue

                if last_seen < decay_threshold:
                    days_since = (now - last_seen).days
                    decay = self._config.decay_rate * (days_since - self._config.decay_days)
                    old_conf = pattern.performance.success_rate
                    new_conf = max(0.0, round(old_conf - decay, 4))

                    if new_conf < old_conf:
                        pattern.performance.success_rate = new_conf
                        event = EvolutionEvent(
                            event_type=EvolutionEventType.DECAY,
                            target_type=EvolutionTarget.PATTERN,
                            source_ids=[pattern.pattern_id],
                            target_id=pattern.pattern_id,
                            before_state={"confidence": old_conf},
                            after_state={"confidence": new_conf},
                            delta={"confidence": round(new_conf - old_conf, 4)},
                            reason=f"Decayed after {days_since} days unused",
                        )
                        events.append(event)

        # Failure 衰减
        if self._failure_memory is not None:
            for failure in self._failure_memory.get_all():
                try:
                    last_updated = datetime.fromisoformat(failure.updated_at.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    continue

                if last_updated < decay_threshold:
                    days_since = (now - last_updated).days
                    decay = self._config.decay_rate * (days_since - self._config.decay_days) * 0.5
                    old_conf = failure.confidence
                    new_conf = max(0.0, round(old_conf - decay, 4))

                    if new_conf < old_conf:
                        failure.confidence = new_conf
                        event = EvolutionEvent(
                            event_type=EvolutionEventType.DECAY,
                            target_type=EvolutionTarget.FAILURE,
                            source_ids=[failure.failure_id],
                            target_id=failure.failure_id,
                            before_state={"confidence": old_conf},
                            after_state={"confidence": new_conf},
                            delta={"confidence": round(new_conf - old_conf, 4)},
                            reason=f"Decayed after {days_since} days since last update",
                        )
                        events.append(event)

        return events

    # ═══════════════════════════════════════════════════════════
    # Knowledge Graph
    # ═══════════════════════════════════════════════════════════

    def get_knowledge_graph(self) -> KnowledgeGraph:
        """获取当前知识图谱."""
        if self._knowledge_graph.cross_references == 0:
            self._build_cross_references()
        return self._knowledge_graph

    def get_isolated_knowledge(self) -> dict[str, list[str]]:
        """获取孤立知识 (未被引用的模式/策略)."""
        kg = self.get_knowledge_graph()
        return {
            "isolated_patterns": kg.isolated_patterns,
            "isolated_strategies": kg.isolated_strategies,
        }

    # ═══════════════════════════════════════════════════════════
    # Metrics
    # ═══════════════════════════════════════════════════════════

    def _compute_metrics(self) -> EvolutionMetrics:
        """计算进化质量指标."""
        events = self._history
        if not events:
            return EvolutionMetrics()

        metrics = EvolutionMetrics()
        metrics.total_events = len(events)
        metrics.last_evolution = events[-1].timestamp

        for e in events:
            if e.event_type == EvolutionEventType.CONSOLIDATE:
                metrics.consolidations += 1
            elif e.event_type == EvolutionEventType.UPGRADE:
                metrics.upgrades += 1
            elif e.event_type == EvolutionEventType.DOWNGRADE:
                metrics.downgrades += 1
            elif e.event_type == EvolutionEventType.DECAY:
                metrics.decays += 1
            elif e.event_type == EvolutionEventType.CONFLICT_RESOLVE:
                metrics.conflict_resolutions += 1
            elif e.event_type == EvolutionEventType.CROSS_REFERENCE:
                metrics.cross_references += 1
            elif e.event_type == EvolutionEventType.NEW_KNOWLEDGE:
                metrics.new_knowledge += 1
            elif e.event_type == EvolutionEventType.DEPRECATE:
                metrics.deprecations += 1

        # 置信度变化
        upgrades = [e for e in events if e.event_type == EvolutionEventType.UPGRADE]
        downgrades = [e for e in events if e.event_type == EvolutionEventType.DOWNGRADE]
        all_confidence_events = upgrades + downgrades

        if all_confidence_events:
            befores = [e.before_state.get("confidence", 0) for e in all_confidence_events]
            afters = [e.after_state.get("confidence", 0) for e in all_confidence_events]
            metrics.avg_confidence_before = round(sum(befores) / len(befores), 4)
            metrics.avg_confidence_after = round(sum(afters) / len(afters), 4)
            metrics.confidence_improvement = round(
                metrics.avg_confidence_after - metrics.avg_confidence_before, 4
            )

        # 知识图谱
        kg = self._knowledge_graph
        metrics.knowledge_graph_size = len(kg.pattern_to_strategies) + len(kg.strategy_to_patterns)
        metrics.knowledge_graph_density = kg.graph_density

        # 综合进化评分
        metrics.evolution_score = self._compute_evolution_score(metrics)

        return metrics

    def _compute_evolution_score(self, metrics: EvolutionMetrics) -> float:
        """计算综合进化评分 [0, 1].

        Score = 0.3 × 升级率 + 0.2 × 合并率 + 0.2 × 图谱密度 + 0.15 × 置信度提升 + 0.15 × 活跃度
        """
        if metrics.total_events == 0:
            return 0.0

        upgrade_rate = metrics.upgrades / max(metrics.total_events, 1)
        consolidate_rate = metrics.consolidations / max(metrics.total_events, 1)
        density = min(1.0, metrics.knowledge_graph_density * 10)  # 放大密度
        improvement = min(1.0, max(0.0, metrics.confidence_improvement + 0.5))  # 归一化
        activity = min(1.0, metrics.total_events / 100)  # 活跃度

        score = (
            0.3 * upgrade_rate
            + 0.2 * consolidate_rate
            + 0.2 * density
            + 0.15 * improvement
            + 0.15 * activity
        )
        return round(score, 4)

    def get_metrics(self) -> EvolutionMetrics:
        """获取进化指标."""
        return self._compute_metrics()

    # ═══════════════════════════════════════════════════════════
    # History
    # ═══════════════════════════════════════════════════════════

    def get_history(self, limit: int = 100) -> list[EvolutionEvent]:
        """获取进化历史."""
        return self._history[-limit:] if limit > 0 else self._history

    def get_history_by_type(
        self,
        event_type: EvolutionEventType,
    ) -> list[EvolutionEvent]:
        """按类型获取进化历史."""
        return [e for e in self._history if e.event_type == event_type]

    def _trim_history(self) -> None:
        """裁剪历史记录."""
        if len(self._history) > self._config.max_evolution_history:
            self._history = self._history[-self._config.max_evolution_history:]

    def clear_history(self) -> None:
        """清空进化历史."""
        self._history.clear()

    # ═══════════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════════

    def summary(self) -> str:
        """生成进化摘要."""
        metrics = self._compute_metrics()
        kg = self._knowledge_graph

        lines = [
            "=" * 50,
            "  Memory Evolution Summary",
            "=" * 50,
            f"  Total Events:       {metrics.total_events}",
            f"  Consolidations:     {metrics.consolidations}",
            f"  Upgrades:           {metrics.upgrades}",
            f"  Downgrades:         {metrics.downgrades}",
            f"  Decays:             {metrics.decays}",
            f"  Cross References:   {metrics.cross_references}",
            "-" * 50,
            f"  Confidence Before:  {metrics.avg_confidence_before:.4f}",
            f"  Confidence After:   {metrics.avg_confidence_after:.4f}",
            f"  Improvement:        {metrics.confidence_improvement:+.4f}",
            "-" * 50,
            f"  Knowledge Graph:    {metrics.knowledge_graph_size} nodes",
            f"  Graph Density:      {metrics.knowledge_graph_density:.4f}",
            f"  Isolated Patterns:  {len(kg.isolated_patterns)}",
            f"  Isolated Strategies:{len(kg.isolated_strategies)}",
            "-" * 50,
            f"  Evolution Score:    {metrics.evolution_score:.4f}",
            f"  Last Evolution:     {metrics.last_evolution}",
            "=" * 50,
        ]
        return "\n".join(lines)

    @property
    def history_count(self) -> int:
        return len(self._history)

    @property
    def config(self) -> EvolutionConfig:
        return self._config