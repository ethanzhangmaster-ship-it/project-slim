"""E14.4.4.4 Mutation Learning — 变异学习引擎.

从历史变异记录中学习「哪些基因变异最有效」:

  输入: 历史变异记录 (gene_category + mutation_action + outcome)
  输出: MutationPriority (基因类别 → 变异优先级)

核心能力:
  - 变异记录: 记录每次基因变异的尝试和结果
  - 有效性计算: 每个基因类别的变异成功率 × 平均影响
  - 优先级排序: 按有效性 × 置信度排序
  - 学习建议: 推荐当前最优变异方向

设计原则:
  - 确定性、可解释 — 基于历史频次统计
  - 与 RewardModel 互补 — RewardModel 负责「什么有价值」，MutationLearning 负责「怎么变异」
  - 支持基因类别级别的变异学习
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..memory import CreativeMemory, CreativeDecisionRecord, CreativeDecisionOutcome
from ..strategy import GeneMutationAction


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class GeneCategory(str, Enum):
    """基因类别."""
    HOOK = "hook"
    VISUAL = "visual"
    GAMEPLAY = "gameplay"
    EMOTION = "emotion"
    AUDIENCE = "audience"
    CONTEXT = "context"
    MONETIZATION = "monetization"


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class MutationRecord:
    """单次变异记录.

    Attributes:
        record_id: 记录 ID
        gene_category: 基因类别
        mutation_action: 变异动作
        parent_creative_id: 父创意 ID
        variant_creative_id: 变体创意 ID
        before_metrics: 变异前指标
        after_metrics: 变异后指标
        reward: 奖励值
        roas_impact: ROAS 影响 (变化量)
        outcome: 结果
        created_at: 创建时间
    """
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    gene_category: GeneCategory = GeneCategory.HOOK
    mutation_action: GeneMutationAction = GeneMutationAction.CHANGE
    parent_creative_id: str = ""
    variant_creative_id: str = ""
    before_metrics: dict[str, float] = field(default_factory=dict)
    after_metrics: dict[str, float] = field(default_factory=dict)
    reward: float = 0.0
    roas_impact: float = 0.0
    outcome: CreativeDecisionOutcome = CreativeDecisionOutcome.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "gene_category": self.gene_category.value,
            "mutation_action": self.mutation_action.value,
            "parent_creative_id": self.parent_creative_id,
            "variant_creative_id": self.variant_creative_id,
            "before_metrics": self.before_metrics,
            "after_metrics": self.after_metrics,
            "reward": round(self.reward, 4),
            "roas_impact": round(self.roas_impact, 4),
            "outcome": self.outcome.value,
            "created_at": self.created_at,
        }

    @property
    def is_success(self) -> bool:
        return self.outcome == CreativeDecisionOutcome.SUCCESS

    @property
    def is_significant_impact(self) -> bool:
        """是否有显著影响 (ROAS 变化 >= 10%)."""
        return abs(self.roas_impact) >= 0.1


@dataclass
class MutationEffectiveness:
    """变异有效性 — 某个基因类别 × 变异动作的表现.

    Attributes:
        gene_category: 基因类别
        mutation_action: 变异动作
        attempt_count: 尝试次数
        success_count: 成功次数
        success_rate: 成功率
        avg_roas_impact: 平均 ROAS 影响
        avg_reward: 平均奖励
        confidence: 置信度
        last_updated: 最后更新时间
    """
    gene_category: GeneCategory = GeneCategory.HOOK
    mutation_action: GeneMutationAction = GeneMutationAction.CHANGE
    attempt_count: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    avg_roas_impact: float = 0.0
    avg_reward: float = 0.0
    confidence: float = 0.0
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_category": self.gene_category.value,
            "mutation_action": self.mutation_action.value,
            "attempt_count": self.attempt_count,
            "success_count": self.success_count,
            "success_rate": round(self.success_rate, 4),
            "avg_roas_impact": round(self.avg_roas_impact, 4),
            "avg_reward": round(self.avg_reward, 4),
            "confidence": round(self.confidence, 4),
            "last_updated": self.last_updated,
        }

    @property
    def is_reliable(self) -> bool:
        return self.attempt_count >= 3 and self.confidence >= 0.4

    @property
    def effectiveness_score(self) -> float:
        """综合有效性分数: success_rate × avg_impact × confidence."""
        return self.success_rate * abs(self.avg_roas_impact) * self.confidence


@dataclass
class MutationPriority:
    """变异优先级 — 推荐变异方向.

    Attributes:
        gene_category: 基因类别
        mutation_action: 推荐变异动作
        priority_score: 优先级分数
        effectiveness: 有效性数据
        recommendation: 推荐理由
        suggested_weight: 建议权重 (用于策略生成)
    """
    gene_category: GeneCategory = GeneCategory.HOOK
    mutation_action: GeneMutationAction = GeneMutationAction.CHANGE
    priority_score: float = 0.0
    effectiveness: MutationEffectiveness | None = None
    recommendation: str = ""
    suggested_weight: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_category": self.gene_category.value,
            "mutation_action": self.mutation_action.value,
            "priority_score": round(self.priority_score, 4),
            "effectiveness": self.effectiveness.to_dict() if self.effectiveness else None,
            "recommendation": self.recommendation,
            "suggested_weight": round(self.suggested_weight, 4),
        }


@dataclass
class MutationLearningReport:
    """变异学习报告.

    Attributes:
        report_id: 报告 ID
        total_records: 总变异记录数
        gene_categories_covered: 覆盖的基因类别数
        reliable_effectiveness: 可靠有效性数据
        priorities: 变异优先级排序
        summary: 报告摘要
        created_at: 创建时间
    """
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    gene_categories_covered: int = 0
    reliable_effectiveness: list[MutationEffectiveness] = field(default_factory=list)
    priorities: list[MutationPriority] = field(default_factory=list)
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "total_records": self.total_records,
            "gene_categories_covered": self.gene_categories_covered,
            "reliable_effectiveness": [e.to_dict() for e in self.reliable_effectiveness],
            "priorities": [p.to_dict() for p in self.priorities],
            "summary": self.summary,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# Mutation Learning
# ═══════════════════════════════════════════════════════════════


class MutationLearning:
    """变异学习引擎 — 学习「哪些变异最有效」.

    职责:
      1. 从历史决策记录中提取变异记录
      2. 计算每个基因类别 × 变异动作的有效性
      3. 基于有效性排序变异优先级
      4. 为策略生成提供变异权重建议

    用法:
        learner = MutationLearning(memory)
        learner.record(gene_category=GeneCategory.HOOK, action=GeneMutationAction.CHANGE, ...)
        priorities = learner.get_priorities()  # 获取变异优先级
    """

    def __init__(self, memory: CreativeMemory | None = None, min_attempts: int = 3):
        self._memory = memory or CreativeMemory()
        self._min_attempts = min_attempts
        self._records: list[MutationRecord] = []
        self._effectiveness: dict[str, MutationEffectiveness] = {}  # key = "category:action"

    # ── 记录 ──────────────────────────────────────────────────

    def record(
        self,
        gene_category: GeneCategory = GeneCategory.HOOK,
        mutation_action: GeneMutationAction = GeneMutationAction.CHANGE,
        parent_creative_id: str = "",
        variant_creative_id: str = "",
        before_metrics: dict[str, float] | None = None,
        after_metrics: dict[str, float] | None = None,
        reward: float = 0.0,
        outcome: CreativeDecisionOutcome = CreativeDecisionOutcome.PENDING,
    ) -> MutationRecord:
        """记录一次变异尝试.

        Args:
            gene_category: 基因类别
            mutation_action: 变异动作
            parent_creative_id: 父创意 ID
            variant_creative_id: 变体创意 ID
            before_metrics: 变异前指标
            after_metrics: 变异后指标
            reward: 奖励值
            outcome: 结果

        Returns:
            MutationRecord: 变异记录
        """
        before = before_metrics or {}
        after = after_metrics or {}

        roas_before = before.get("roas", 0)
        roas_after = after.get("roas", 0)
        roas_impact = (roas_after - roas_before) / max(roas_before, 0.01) if roas_before > 0 else 0.0

        record = MutationRecord(
            gene_category=gene_category,
            mutation_action=mutation_action,
            parent_creative_id=parent_creative_id,
            variant_creative_id=variant_creative_id,
            before_metrics=before,
            after_metrics=after,
            reward=reward,
            roas_impact=roas_impact,
            outcome=outcome,
        )
        self._records.append(record)

        # 更新有效性
        self._update_effectiveness(record)

        return record

    def record_from_decision(
        self,
        decision: CreativeDecisionRecord,
    ) -> MutationRecord | None:
        """从已解析的决策记录中提取变异记录.

        从 GENERATE_VARIANTS / MUTATE_DNA 类型的决策中提取变异信息.

        Args:
            decision: 已解析的决策记录

        Returns:
            MutationRecord | None
        """
        if decision.action_type.value not in ("generate_variants", "mutate_dna"):
            return None

        params = decision.action_params
        gene_category_raw = params.get("gene_category", "")
        if not gene_category_raw:
            return None

        # 映射基因类别
        try:
            gene_category = GeneCategory(gene_category_raw)
        except ValueError:
            return None

        # 映射变异动作
        mutation_action_raw = params.get("mutation_action", "change")
        try:
            mutation_action = GeneMutationAction(mutation_action_raw)
        except ValueError:
            mutation_action = GeneMutationAction.CHANGE

        return self.record(
            gene_category=gene_category,
            mutation_action=mutation_action,
            parent_creative_id=decision.creative_id,
            variant_creative_id=params.get("variant_creative_id", ""),
            before_metrics=decision.before_metrics,
            after_metrics=decision.after_metrics,
            reward=decision.reward,
            outcome=decision.outcome,
        )

    def record_batch_from_decisions(
        self,
        decisions: list[CreativeDecisionRecord],
    ) -> list[MutationRecord]:
        """批量从决策记录中提取变异记录."""
        records = []
        for d in decisions:
            r = self.record_from_decision(d)
            if r:
                records.append(r)
        return records

    def import_from_memory(self) -> int:
        """从 CreativeMemory 中导入所有已解析的变异相关决策."""
        resolved = self._memory.get_resolved()
        count = 0
        for record in resolved:
            if self.record_from_decision(record):
                count += 1
        return count

    # ── 有效性计算 ────────────────────────────────────────────

    def _update_effectiveness(self, record: MutationRecord) -> None:
        """更新变异有效性."""
        key = f"{record.gene_category.value}:{record.mutation_action.value}"
        eff = self._effectiveness.get(key)

        if not eff:
            eff = MutationEffectiveness(
                gene_category=record.gene_category,
                mutation_action=record.mutation_action,
            )
            self._effectiveness[key] = eff

        eff.attempt_count += 1
        if record.is_success:
            eff.success_count += 1

        eff.success_rate = eff.success_count / max(eff.attempt_count, 1)

        # 更新平均 ROAS 影响
        old_total = eff.attempt_count - 1
        eff.avg_roas_impact = (eff.avg_roas_impact * old_total + record.roas_impact) / max(eff.attempt_count, 1)

        # 更新平均奖励
        eff.avg_reward = (eff.avg_reward * old_total + record.reward) / max(eff.attempt_count, 1)

        # 置信度: 基于尝试次数和成功率
        eff.confidence = min(eff.attempt_count / 10.0, 1.0) * 0.6 + eff.success_rate * 0.4
        eff.last_updated = datetime.now(timezone.utc).isoformat()

    def get_effectiveness(
        self,
        gene_category: GeneCategory,
        mutation_action: GeneMutationAction | None = None,
    ) -> MutationEffectiveness | None:
        """获取指定基因类别 × 变异动作的有效性."""
        if mutation_action:
            key = f"{gene_category.value}:{mutation_action.value}"
            return self._effectiveness.get(key)

        # 聚合该基因类别的所有动作
        matched = [
            e for k, e in self._effectiveness.items()
            if k.startswith(f"{gene_category.value}:")
        ]
        if not matched:
            return None

        total_attempts = sum(e.attempt_count for e in matched)
        total_success = sum(e.success_count for e in matched)
        return MutationEffectiveness(
            gene_category=gene_category,
            mutation_action=GeneMutationAction.CHANGE,
            attempt_count=total_attempts,
            success_count=total_success,
            success_rate=total_success / max(total_attempts, 1),
            avg_roas_impact=sum(e.avg_roas_impact for e in matched) / len(matched),
            avg_reward=sum(e.avg_reward for e in matched) / len(matched),
            confidence=sum(e.confidence for e in matched) / len(matched),
        )

    def get_all_effectiveness(self) -> list[MutationEffectiveness]:
        """获取所有变异有效性."""
        return list(self._effectiveness.values())

    def get_reliable_effectiveness(self) -> list[MutationEffectiveness]:
        """获取可靠的变异有效性 (attempt >= min_attempts, confidence >= 0.4)."""
        return [e for e in self._effectiveness.values() if e.is_reliable]

    # ── 优先级排序 ────────────────────────────────────────────

    def get_priorities(
        self,
        min_confidence: float = 0.3,
        top_n: int = 10,
    ) -> list[MutationPriority]:
        """获取变异优先级排序.

        排序规则:
          - 按 effectiveness_score (success_rate × avg_impact × confidence) 降序
          - 过滤掉置信度不足的

        Args:
            min_confidence: 最小置信度
            top_n: 返回 Top N

        Returns:
            list[MutationPriority]: 变异优先级列表
        """
        priorities = []

        for key, eff in self._effectiveness.items():
            if eff.confidence < min_confidence:
                continue
            if eff.attempt_count < self._min_attempts:
                continue

            score = eff.effectiveness_score

            # 生成推荐理由
            if eff.success_rate >= 0.7 and eff.avg_roas_impact > 0:
                recommendation = (
                    f"强烈推荐变异 {eff.gene_category.value} ("
                    f"成功率 {eff.success_rate:.0%}, "
                    f"平均ROAS提升 {eff.avg_roas_impact:+.0%})"
                )
                suggested_weight = min(eff.success_rate * 1.2, 1.0)
            elif eff.success_rate >= 0.5:
                recommendation = (
                    f"推荐变异 {eff.gene_category.value} ("
                    f"成功率 {eff.success_rate:.0%})"
                )
                suggested_weight = eff.success_rate * 0.8
            elif eff.avg_roas_impact > 0:
                recommendation = (
                    f"探索变异 {eff.gene_category.value} ("
                    f"平均ROAS提升 {eff.avg_roas_impact:+.0%}, "
                    f"但样本不足)"
                )
                suggested_weight = 0.3
            else:
                recommendation = (
                    f"谨慎变异 {eff.gene_category.value} ("
                    f"成功率 {eff.success_rate:.0%})"
                )
                suggested_weight = 0.1

            priorities.append(MutationPriority(
                gene_category=eff.gene_category,
                mutation_action=eff.mutation_action,
                priority_score=score,
                effectiveness=eff,
                recommendation=recommendation,
                suggested_weight=suggested_weight,
            ))

        priorities.sort(key=lambda p: p.priority_score, reverse=True)
        return priorities[:top_n]

    def get_priorities_for_strategy(
        self,
        exclude_categories: list[GeneCategory] | None = None,
    ) -> dict[str, float]:
        """获取用于策略生成的变异权重建议.

        返回 {gene_category: suggested_weight} 字典，用于
        CreativeStrategyEngine 调整变异权重.

        Args:
            exclude_categories: 排除的基因类别

        Returns:
            dict[str, float]: 基因类别 → 建议权重
        """
        exclude = exclude_categories or []
        exclude_values = set(c.value for c in exclude)

        priorities = self.get_priorities(min_confidence=0.2)
        weights: dict[str, float] = {}

        for p in priorities:
            if p.gene_category.value not in exclude_values:
                weights[p.gene_category.value] = p.suggested_weight

        # 补充未覆盖的基因类别 (默认权重 0.3)
        default_weights = {
            "hook": 0.30,
            "visual": 0.20,
            "gameplay": 0.15,
            "emotion": 0.15,
            "audience": 0.10,
            "context": 0.05,
            "monetization": 0.05,
        }
        for cat, default_w in default_weights.items():
            if cat not in weights and cat not in exclude_values:
                weights[cat] = default_w

        return weights

    def get_top_mutation_categories(
        self,
        top_n: int = 5,
    ) -> list[GeneCategory]:
        """获取最值得变异的基因类别."""
        priorities = self.get_priorities(top_n=top_n)
        seen = set()
        categories = []
        for p in priorities:
            if p.gene_category.value not in seen:
                seen.add(p.gene_category.value)
                categories.append(p.gene_category)
        return categories[:top_n]

    # ── 查询 ──────────────────────────────────────────────────

    def get_records_by_category(
        self,
        gene_category: GeneCategory,
    ) -> list[MutationRecord]:
        """获取指定基因类别的所有变异记录."""
        return [r for r in self._records if r.gene_category == gene_category]

    def get_records_by_action(
        self,
        mutation_action: GeneMutationAction,
    ) -> list[MutationRecord]:
        """获取指定变异动作的所有记录."""
        return [r for r in self._records if r.mutation_action == mutation_action]

    def get_recent(self, n: int = 20) -> list[MutationRecord]:
        """获取最近的变异记录."""
        return self._records[-n:]

    # ── 报告 ──────────────────────────────────────────────────

    def generate_report(self) -> MutationLearningReport:
        """生成变异学习报告."""
        reliable = self.get_reliable_effectiveness()
        priorities = self.get_priorities()
        categories = set(r.gene_category for r in self._records)

        if reliable:
            best = reliable[0]
            summary = (
                f"共 {len(self._records)} 条变异记录，覆盖 {len(categories)} 个基因类别。"
                f"最佳变异方向: {best.gene_category.value} × {best.mutation_action.value} "
                f"(成功率 {best.success_rate:.0%}，平均ROAS影响 {best.avg_roas_impact:+.0%})"
            )
        elif self._records:
            summary = (
                f"共 {len(self._records)} 条记录，{len(categories)} 个基因类别，"
                f"但无足够数据形成可靠结论"
            )
        else:
            summary = "暂无变异记录"

        return MutationLearningReport(
            total_records=len(self._records),
            gene_categories_covered=len(categories),
            reliable_effectiveness=reliable,
            priorities=priorities,
            summary=summary,
        )

    def stats(self) -> dict[str, Any]:
        return {
            "total_records": len(self._records),
            "total_effectiveness": len(self._effectiveness),
            "reliable_effectiveness": len(self.get_reliable_effectiveness()),
            "by_category": {
                cat.value: len(self.get_records_by_category(cat))
                for cat in GeneCategory
            },
        }

    def reset(self) -> None:
        self._records.clear()
        self._effectiveness.clear()


def create_mutation_learning(
    memory: CreativeMemory | None = None,
    min_attempts: int = 3,
) -> MutationLearning:
    """创建默认 MutationLearning."""
    return MutationLearning(memory=memory, min_attempts=min_attempts)