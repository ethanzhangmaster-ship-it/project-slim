"""E13.4.4 FailureMemory — 失败记忆系统.

核心职责:
  从 ExperienceStore 中提取失败模式，建立 Negative Knowledge Base，
  为 Decision Executor 提供实时风险检查。

与 Pattern/Strategy Memory 的区别:
  - Pattern: 什么有效？
  - Strategy: 怎么做？
  - Failure: 什么不能做？

提取逻辑:
  1. 从 ExperienceStore 获取所有失败经验
  2. 按 (action_type, opportunity_type, audience, product) 分组
  3. 计算每组失败率、平均损失、严重程度
  4. 过滤显著失败模式 (failure_rate >= 50%, attempts >= 3)

接入 Decision Executor:
  Opportunity → Strategy Recommendation → Failure Check → Risk Score → Execute

流程:
  ExperienceStore (failed)
      ↓
  _extract_failures()
      ↓
  _aggregate_patterns()
      ↓
  _compute_severity()
      ↓
  FailurePattern[]
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .experience_store import ExperienceStore
from .failure_models import (
    FailureCategory,
    FailureCondition,
    FailurePattern,
    FailureQuery,
    FailureSeverity,
    FailureStats,
    FailureWarning,
)
from .models import GrowthExperience


class FailureMemory:
    """失败记忆 — 提取和查询 Negative Knowledge.

    用法:
        exp_store = ExperienceStore()
        fm = FailureMemory(exp_store)
        patterns = fm.extract()
        warnings = fm.check_strategy(strategy)
    """

    # 最低提取阈值
    MIN_ATTEMPTS = 3
    MIN_FAILURE_RATE = 0.5

    def __init__(
        self,
        exp_store: ExperienceStore,
        max_capacity: int = 300,
    ):
        """初始化失败记忆.

        Args:
            exp_store: ExperienceStore 实例
            max_capacity: 最大存储容量
        """
        self._exp_store = exp_store
        self._patterns: list[FailurePattern] = []
        self._max_capacity = max_capacity
        self._total_stored: int = 0

    # ═══════════════════════════════════════════════════════════
    # Extraction
    # ═══════════════════════════════════════════════════════════

    def extract(
        self,
        min_attempts: int = 3,
        min_failure_rate: float = 0.5,
        experiences: list[GrowthExperience] | None = None,
    ) -> list[FailurePattern]:
        """从失败经验中提取失败模式.

        Args:
            min_attempts: 最小尝试次数
            min_failure_rate: 最低失败率
            experiences: 经验列表 (默认从 exp_store 获取全部)

        Returns:
            list[FailurePattern]: 按严重程度降序排列
        """
        if experiences is None:
            experiences = self._exp_store.get_all()

        if not experiences:
            return []

        # Step 1: 筛选失败经验
        failures = [e for e in experiences if not e.is_successful()]
        if len(failures) < min_attempts:
            return []

        # Step 2: 按 (action_type, opportunity_type, audience, product) 分组
        grouped = self._group_failures(failures)

        # Step 3: 构建 FailurePattern
        patterns: list[FailurePattern] = []
        for group_key, group_exps in grouped.items():
            if len(group_exps) < min_attempts:
                continue

            pattern = self._build_pattern(group_key, group_exps)
            if pattern.failure_rate >= min_failure_rate:
                pattern.compute_confidence()
                pattern.compute_severity()
                patterns.append(pattern)

        # Step 4: 排序
        self._rank_patterns(patterns)

        return patterns

    def extract_and_store(
        self,
        min_attempts: int = 3,
        min_failure_rate: float = 0.5,
    ) -> list[str]:
        """提取并自动存储."""
        patterns = self.extract(min_attempts=min_attempts, min_failure_rate=min_failure_rate)
        return self.store_batch(patterns)

    def _group_failures(
        self,
        failures: list[GrowthExperience],
    ) -> dict[str, list[GrowthExperience]]:
        """按维度分组失败经验."""
        grouped: dict[str, list[GrowthExperience]] = defaultdict(list)
        for exp in failures:
            key = self._failure_key(exp)
            grouped[key].append(exp)
        return grouped

    def _failure_key(self, exp: GrowthExperience) -> str:
        """生成失败分组键."""
        ctx = exp.context
        return (
            f"{exp.action_type}"
            f"|{ctx.opportunity_type}"
            f"|{ctx.audience_segment}"
            f"|{ctx.product_id}"
        )

    def _build_pattern(
        self,
        group_key: str,
        failures: list[GrowthExperience],
    ) -> FailurePattern:
        """从一组失败经验构建 FailurePattern."""
        if not failures:
            return FailurePattern()

        # 同时需要计算该条件下的总尝试次数 (包括成功的)
        # 通过 action_type + opportunity_type + audience + product 从 exp_store 查询
        rep = failures[0]
        action_type = rep.action_type
        opportunity_type = rep.context.opportunity_type
        audience = rep.context.audience_segment
        product = rep.context.product_id

        # 计算总尝试次数 (成功 + 失败)
        all_experiences = self._exp_store.get_all()
        total_attempts = sum(
            1 for e in all_experiences
            if e.action_type == action_type
            and e.context.opportunity_type == opportunity_type
            and e.context.audience_segment == audience
            and e.context.product_id == product
        )

        failed_count = len(failures)
        failure_rate = round(failed_count / total_attempts, 4) if total_attempts > 0 else 0.0

        # 损失计算
        losses = [abs(e.reward) for e in failures if e.reward < 0]
        avg_loss = round(sum(losses) / len(losses), 2) if losses else 0.0
        max_loss = round(max(losses), 2) if losses else 0.0

        # 条件
        condition = FailureCondition(
            scenario=self._infer_failure_scenario(rep),
            opportunity_type=opportunity_type,
            signal_types=rep.context.trigger_signals,
            audience_segment=audience,
            product_category=product,
            action_type=action_type,
        )

        # 类别
        category = self._infer_failure_category(rep, failure_rate)

        # 名称
        name = self._generate_failure_name(rep, failure_rate)

        # 建议
        suggestion = self._generate_suggestion(rep, failure_rate)

        # 描述
        description = self._generate_description(rep, failure_rate, total_attempts, avg_loss)

        return FailurePattern(
            name=name,
            category=category,
            condition=condition,
            blocked_action=action_type,
            failure_rate=failure_rate,
            total_attempts=total_attempts,
            failed_attempts=failed_count,
            avg_loss=avg_loss,
            max_loss=max_loss,
            suggestion=suggestion,
            source_experience_ids=[e.experience_id for e in failures],
            tags=self._extract_failure_tags(failures),
            description=description,
        )

    def _infer_failure_scenario(self, exp: GrowthExperience) -> str:
        """推断失败场景描述."""
        opp = exp.context.opportunity_type
        scenario_map = {
            "creative_scale": "Scaling creative in low-performance context",
            "creative_fatigue": "Attempting to refresh fatigued creative",
            "roas_drop": "ROAS dropping and action made it worse",
            "budget_waste": "Budget increase wasted on poor performers",
            "scale_opportunity": "Scaling too aggressively without validation",
            "audience_expansion": "Expanding to wrong audience segment",
        }
        if opp in scenario_map:
            return scenario_map[opp]
        return f"Action {exp.action_type} failed in context: {opp}"

    def _infer_failure_category(
        self,
        exp: GrowthExperience,
        failure_rate: float,
    ) -> FailureCategory:
        """推断失败类别."""
        opp = exp.context.opportunity_type
        action = exp.action_type

        if "budget" in opp or "budget" in action:
            return FailureCategory.BUDGET_WASTE
        if "scale" in opp or "scale" in action:
            return FailureCategory.SCALE_TOO_FAST
        if "roas" in opp:
            return FailureCategory.ROAS_COLLAPSE
        if "audience" in opp:
            return FailureCategory.AUDIENCE_MISMATCH
        if "creative" in opp:
            return FailureCategory.CREATIVE_BACKFIRE
        return FailureCategory.GENERAL

    def _generate_failure_name(
        self,
        exp: GrowthExperience,
        failure_rate: float,
    ) -> str:
        """生成失败模式名称."""
        action = exp.action_type.replace("_", " ").title()
        audience = exp.context.audience_segment
        product = exp.context.product_id
        parts = [f"Avoid: {action}"]
        if product:
            parts.append(f"on {product.upper()}")
        if audience:
            parts.append(f"for {audience}")
        parts.append(f"({failure_rate:.0%} fail)")
        return " ".join(parts)

    def _generate_suggestion(
        self,
        exp: GrowthExperience,
        failure_rate: float,
    ) -> str:
        """生成替代建议."""
        action = exp.action_type
        if failure_rate >= 0.9:
            return f"STRONGLY AVOID {action}. Consider alternative approach or manual review."
        if failure_rate >= 0.7:
            return f"AVOID {action} in this context. Require manual approval before execution."
        if failure_rate >= 0.5:
            return f"CAUTION: {action} has high failure rate. Consider smaller scale test first."
        return f"Monitor {action} carefully if executed."

    def _generate_description(
        self,
        exp: GrowthExperience,
        failure_rate: float,
        total_attempts: int,
        avg_loss: float,
    ) -> str:
        """生成失败模式描述."""
        return (
            f"Action '{exp.action_type}' in context '{exp.context.opportunity_type}' "
            f"failed {failure_rate:.0%} of the time "
            f"({exp.failed_attempts if hasattr(exp, 'failed_attempts') else '?'}/{total_attempts} attempts). "
            f"Average loss: {avg_loss:.2f}. "
            + (f"Audience: {exp.context.audience_segment}. " if exp.context.audience_segment else "")
            + (f"Product: {exp.context.product_id}." if exp.context.product_id else "")
        )

    def _extract_failure_tags(self, failures: list[GrowthExperience]) -> list[str]:
        """从失败经验中提取标签."""
        tags: set[str] = set()
        for exp in failures:
            for tag in exp.tags:
                tags.add(tag)
        return sorted(tags)

    # ═══════════════════════════════════════════════════════════
    # Store
    # ═══════════════════════════════════════════════════════════

    def store(self, pattern: FailurePattern) -> str:
        """存储一条失败模式.

        Args:
            pattern: FailurePattern 实例

        Returns:
            failure_id: 失败模式ID
        """
        existing = self._find_existing(pattern)
        if existing is not None:
            # 更新现有模式
            existing.failure_rate = pattern.failure_rate
            existing.total_attempts = pattern.total_attempts
            existing.failed_attempts = pattern.failed_attempts
            existing.avg_loss = pattern.avg_loss
            existing.max_loss = max(existing.max_loss, pattern.max_loss)
            existing.confidence = pattern.confidence
            existing.severity = pattern.severity
            existing.source_experience_ids = list(
                set(existing.source_experience_ids + pattern.source_experience_ids)
            )
            existing.tags = list(set(existing.tags + pattern.tags))
            existing.updated_at = datetime.now(timezone.utc).isoformat()
            existing.compute_confidence()
            existing.compute_severity()
            return existing.failure_id

        self._patterns.append(pattern)
        self._total_stored += 1

        if len(self._patterns) > self._max_capacity:
            overflow = len(self._patterns) - self._max_capacity
            self._patterns = self._patterns[overflow:]

        return pattern.failure_id

    def store_batch(self, patterns: list[FailurePattern]) -> list[str]:
        """批量存储失败模式."""
        return [self.store(p) for p in patterns]

    def _find_existing(self, pattern: FailurePattern) -> FailurePattern | None:
        """查找已存在的相同失败模式."""
        new_key = self._pattern_match_key(pattern)
        for p in self._patterns:
            if self._pattern_match_key(p) == new_key:
                return p
        return None

    def _pattern_match_key(self, pattern: FailurePattern) -> str:
        """生成模式匹配键."""
        c = pattern.condition
        return f"{c.action_type}|{c.opportunity_type}|{c.audience_segment}|{c.product_category}"

    # ═══════════════════════════════════════════════════════════
    # Query
    # ═══════════════════════════════════════════════════════════

    def query(self, q: FailureQuery) -> list[FailurePattern]:
        """按条件查询失败模式.

        Args:
            q: FailureQuery 查询条件

        Returns:
            list[FailurePattern]: 匹配的失败模式列表
        """
        results = self._patterns

        # 动作类型过滤
        if q.action_types:
            results = [p for p in results if p.blocked_action in q.action_types]

        # 机会类型过滤
        if q.opportunity_types:
            results = [
                p for p in results
                if p.condition.opportunity_type in q.opportunity_types
            ]

        # 类别过滤
        if q.categories:
            results = [p for p in results if p.category.value in q.categories]

        # 受众过滤
        if q.audience_segment:
            results = [
                p for p in results
                if p.condition.audience_segment == q.audience_segment
            ]

        # 产品过滤
        if q.product_category:
            results = [
                p for p in results
                if p.condition.product_category == q.product_category
            ]

        # 失败率过滤
        if q.min_failure_rate > 0:
            results = [p for p in results if p.failure_rate >= q.min_failure_rate]

        # 尝试次数过滤
        if q.min_attempts > 0:
            results = [p for p in results if p.total_attempts >= q.min_attempts]

        # 损失过滤
        if q.min_loss > 0:
            results = [p for p in results if p.avg_loss >= q.min_loss]

        # 严重程度过滤
        if q.severity_levels:
            results = [p for p in results if p.severity.value in q.severity_levels]

        # 阻止级过滤
        if q.blocking_only:
            results = [p for p in results if p.is_blocking()]

        # 有意义过滤
        if q.significant_only:
            results = [p for p in results if p.is_significant()]

        # 标签过滤
        if q.tags:
            results = [p for p in results if any(t in p.tags for t in q.tags)]

        # 排序
        results = self._sort_results(results, q.sort_by, q.sort_desc)

        # 限制
        if q.limit > 0 and len(results) > q.limit:
            results = results[:q.limit]

        return results

    def _sort_results(
        self,
        results: list[FailurePattern],
        sort_by: str,
        desc: bool,
    ) -> list[FailurePattern]:
        """排序结果."""
        if sort_by == "failure_rate":
            key = lambda p: p.failure_rate
        elif sort_by == "attempts":
            key = lambda p: p.total_attempts
        elif sort_by == "avg_loss":
            key = lambda p: p.avg_loss
        elif sort_by == "severity":
            sev_order = {
                FailureSeverity.CRITICAL: 4,
                FailureSeverity.HIGH: 3,
                FailureSeverity.MEDIUM: 2,
                FailureSeverity.LOW: 1,
                FailureSeverity.NEGLIGIBLE: 0,
            }
            key = lambda p: sev_order.get(p.severity, 0)
        else:
            key = lambda p: p.failure_rate
        return sorted(results, key=key, reverse=desc)

    # ═══════════════════════════════════════════════════════════
    # Warning / Risk Check
    # ═══════════════════════════════════════════════════════════

    def check_action(
        self,
        action_type: str,
        opportunity_type: str = "",
        signal_types: list[str] | None = None,
        audience_segment: str = "",
        product_category: str = "",
    ) -> list[FailureWarning]:
        """检查单个动作是否存在失败风险.

        Args:
            action_type: 待检查的动作类型
            opportunity_type: 当前机会类型
            signal_types: 当前信号类型
            audience_segment: 当前受众
            product_category: 当前产品

        Returns:
            list[FailureWarning]: 匹配的失败警告列表 (按 risk_score 降序)
        """
        warnings: list[FailureWarning] = []

        for pattern in self._patterns:
            if not pattern.is_significant():
                continue
            if not pattern.condition.matches(
                action_type=action_type,
                opportunity_type=opportunity_type,
                signal_types=signal_types,
                audience_segment=audience_segment,
                product_category=product_category,
            ):
                continue

            warning = self._build_warning(pattern, action_type)
            warnings.append(warning)

        warnings.sort(key=lambda w: -w.risk_score)
        return warnings

    def check_strategy(
        self,
        strategy: Any,
        opportunity_type: str = "",
        signal_types: list[str] | None = None,
        audience_segment: str = "",
        product_category: str = "",
    ) -> dict[str, list[FailureWarning]]:
        """检查策略中所有步骤是否存在失败风险.

        Args:
            strategy: GrowthStrategyPattern 实例 (有 .steps 属性)
            opportunity_type: 当前机会类型
            signal_types: 当前信号类型
            audience_segment: 当前受众
            product_category: 当前产品

        Returns:
            dict[str, list[FailureWarning]]: {step_index: [warnings]}
        """
        all_warnings: dict[str, list[FailureWarning]] = {}

        for step in strategy.steps:
            warnings = self.check_action(
                action_type=step.action_type,
                opportunity_type=opportunity_type or strategy.trigger.opportunity_type,
                signal_types=signal_types or strategy.trigger.signal_types,
                audience_segment=audience_segment or strategy.trigger.audience_segment,
                product_category=product_category or strategy.trigger.product_category,
            )
            if warnings:
                all_warnings[f"step_{step.order}"] = warnings

        return all_warnings

    def get_blocking_warnings(
        self,
        action_type: str,
        opportunity_type: str = "",
        signal_types: list[str] | None = None,
        audience_segment: str = "",
        product_category: str = "",
    ) -> list[FailureWarning]:
        """获取阻止级警告 (CRITICAL/HIGH).

        Returns:
            list[FailureWarning]: 需要阻止或人工审批的警告
        """
        warnings = self.check_action(
            action_type=action_type,
            opportunity_type=opportunity_type,
            signal_types=signal_types,
            audience_segment=audience_segment,
            product_category=product_category,
        )
        return [w for w in warnings if w.requires_approval]

    def compute_risk_score(
        self,
        action_type: str,
        opportunity_type: str = "",
        signal_types: list[str] | None = None,
        audience_segment: str = "",
        product_category: str = "",
    ) -> float:
        """计算动作的综合风险评分 [0, 1].

        Returns:
            float: 风险评分 (0 = 无风险, 1 = 极高风险)
        """
        warnings = self.check_action(
            action_type=action_type,
            opportunity_type=opportunity_type,
            signal_types=signal_types,
            audience_segment=audience_segment,
            product_category=product_category,
        )

        if not warnings:
            return 0.0

        # 取最高风险
        return max(w.risk_score for w in warnings)

    def _build_warning(
        self,
        pattern: FailurePattern,
        action_type: str,
    ) -> FailureWarning:
        """构建失败警告."""
        # 风险评分: failure_rate × confidence × loss_factor
        loss_factor = min(1.0, pattern.avg_loss / 1000.0) if pattern.avg_loss > 0 else 0.5
        risk_score = round(
            pattern.failure_rate * pattern.confidence * (0.5 + 0.5 * loss_factor),
            4,
        )

        # 是否需要审批
        requires_approval = pattern.is_blocking() or risk_score >= 0.5

        # 上下文摘要
        context_parts = []
        if pattern.condition.opportunity_type:
            context_parts.append(f"opportunity={pattern.condition.opportunity_type}")
        if pattern.condition.audience_segment:
            context_parts.append(f"audience={pattern.condition.audience_segment}")
        if pattern.condition.product_category:
            context_parts.append(f"product={pattern.condition.product_category}")

        return FailureWarning(
            pattern_id=pattern.failure_id,
            pattern_name=pattern.name,
            action_type=action_type,
            risk_score=risk_score,
            failure_rate=pattern.failure_rate,
            expected_loss=pattern.avg_loss,
            severity=pattern.severity,
            suggestion=pattern.suggestion,
            requires_approval=requires_approval,
            context_summary=", ".join(context_parts) if context_parts else "general",
        )

    # ═══════════════════════════════════════════════════════════
    # Convenience Methods
    # ═══════════════════════════════════════════════════════════

    def get_by_action(self, action_type: str) -> list[FailurePattern]:
        """按动作类型获取失败模式."""
        return self.query(FailureQuery(action_types=[action_type]))

    def get_blocking_patterns(self) -> list[FailurePattern]:
        """获取所有阻止级失败模式."""
        return self.query(FailureQuery(blocking_only=True))

    def get_critical_patterns(self) -> list[FailurePattern]:
        """获取所有致命失败模式."""
        return self.query(FailureQuery(severity_levels=["critical"]))

    def get_most_dangerous(self, n: int = 10) -> list[FailurePattern]:
        """获取最危险的失败模式 (按 avg_loss 排序)."""
        return self.query(FailureQuery(
            limit=n,
            sort_by="avg_loss",
            sort_desc=True,
        ))

    def get_all(self) -> list[FailurePattern]:
        """获取所有失败模式."""
        return list(self._patterns)

    @property
    def count(self) -> int:
        return len(self._patterns)

    @property
    def total_stored(self) -> int:
        return self._total_stored

    def clear(self) -> None:
        self._patterns.clear()

    # ═══════════════════════════════════════════════════════════
    # Statistics
    # ═══════════════════════════════════════════════════════════

    def get_stats(self) -> FailureStats:
        """获取失败模式库统计."""
        patterns = self._patterns
        total = len(patterns)

        if total == 0:
            return FailureStats()

        significant = [p for p in patterns if p.is_significant()]
        blocking = [p for p in patterns if p.is_blocking()]
        avg_failure_rate = round(sum(p.failure_rate for p in patterns) / total, 4)
        avg_loss = round(sum(p.avg_loss for p in patterns) / total, 2)
        total_avoided = round(sum(p.avg_loss * p.total_attempts * p.failure_rate for p in patterns), 2)

        # 按类别统计
        by_category: dict[str, dict[str, float]] = {}
        cat_groups: dict[str, list[FailurePattern]] = defaultdict(list)
        for p in patterns:
            cat_groups[p.category.value].append(p)
        for cat, group in cat_groups.items():
            by_category[cat] = {
                "count": len(group),
                "avg_failure_rate": round(sum(p.failure_rate for p in group) / len(group), 4) if group else 0,
            }

        # 按严重程度统计
        by_severity: dict[str, int] = {}
        for p in patterns:
            sev = p.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1

        # 按动作统计
        by_action: dict[str, int] = {}
        for p in patterns:
            act = p.blocked_action
            by_action[act] = by_action.get(act, 0) + 1

        # Top 危险模式
        top = sorted(patterns, key=lambda p: -p.avg_loss)[:10]
        top_dangerous = [
            {
                "failure_id": p.failure_id,
                "name": p.name,
                "blocked_action": p.blocked_action,
                "failure_rate": p.failure_rate,
                "avg_loss": p.avg_loss,
                "severity": p.severity.value,
            }
            for p in top
        ]

        return FailureStats(
            total_patterns=total,
            total_significant=len(significant),
            total_blocking=len(blocking),
            by_category=by_category,
            by_severity=by_severity,
            by_action=by_action,
            top_dangerous=top_dangerous,
            avg_failure_rate=avg_failure_rate,
            avg_loss=avg_loss,
            total_avoided_loss=total_avoided,
        )

    def _rank_patterns(self, patterns: list[FailurePattern]) -> None:
        """按严重程度 + 失败率降序排序."""
        sev_order = {
            FailureSeverity.CRITICAL: 5,
            FailureSeverity.HIGH: 4,
            FailureSeverity.MEDIUM: 3,
            FailureSeverity.LOW: 2,
            FailureSeverity.NEGLIGIBLE: 1,
        }
        patterns.sort(key=lambda p: -(sev_order.get(p.severity, 0) * 10 + p.failure_rate * 100))