"""E14.4.4.5 Creative Policy — 上下文感知决策策略.

Creative Policy 是 Learning Loop 的最终决策层，整合所有学习模块:

  输入: 当前上下文 (游戏/平台/市场/阶段 + 当前指标)
  输出: PolicyDecision (推荐动作 + 优先级 + 置信度)

核心能力:
  - 上下文感知: 根据 game/platform/market/stage 感知场景
  - 策略决策: 整合 Pattern Miner + Strategy Memory + Mutation Learning 的结果
  - 动作推荐: 输出具体的策略动作 (REFRESH_HOOK, CHANGE_VISUAL, etc.)
  - 置信度评估: 综合各模块置信度输出最终决策置信度

决策流程:
  Context → Pattern Mining → Strategy Matching → Mutation Priority → Policy Decision

设计原则:
  - 确定性、可解释 — 所有决策可追溯
  - 分层决策 — 从模式→策略→变异逐步精细化
  - 不替代 StrategyEngine — 而是为其提供学习后的参数优化
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..memory import CreativeMemory, CreativeDecisionRecord, CreativeDecisionOutcome, CreativeActionType
from ..strategy import CreativeStrategyType, GeneMutationAction
from ..opportunity import CreativeOpportunity, CreativeOpportunityType, OpportunityPriority
from .pattern_miner import PatternMiner, DNAPattern, PatternConfidence
from .strategy_memory import StrategyMemory, ContextProfile, StrategyEffectiveness
from .mutation_learning import MutationLearning, GeneCategory, MutationPriority


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class PolicyConfidence(str, Enum):
    """策略置信度等级."""
    HIGH = "high"          # 多模块一致，样本充足
    MEDIUM = "medium"      # 单一模块有数据，或部分一致
    LOW = "low"            # 数据不足，基于默认规则
    INSUFFICIENT = "insufficient"  # 无数据


class PolicyAction(str, Enum):
    """策略动作."""
    REFRESH_HOOK = "refresh_hook"
    CHANGE_VISUAL = "change_visual"
    CHANGE_EMOTION = "change_emotion"
    CHANGE_GAMEPLAY = "change_gameplay"
    EXPLORE_AUDIENCE = "explore_audience"
    COPY_WINNER = "copy_winner"
    EXPLORE_NEW = "explore_new"
    SCALE_WINNER = "scale_winner"
    REFRESH_CREATIVE = "refresh_creative"
    HOLD = "hold"  # 保持现状


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class PolicyContext:
    """策略上下文 — 描述当前决策环境.

    Attributes:
        context_id: 上下文 ID
        game: 游戏名称
        platform: 平台
        market: 市场
        genre: 游戏类型
        stage: 投放阶段
        current_roas: 当前 ROAS
        current_ctr: 当前 CTR
        current_fatigue: 当前疲劳度
        current_frequency: 当前频次
        current_ltv: 当前 LTV
        active_creative_count: 活跃素材数
        creative_id: 目标素材 ID (可选)
    """
    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    game: str = ""
    platform: str = ""
    market: str = ""
    genre: str = ""
    stage: str = ""
    current_roas: float = 0.0
    current_ctr: float = 0.0
    current_fatigue: float = 0.0
    current_frequency: float = 0.0
    current_ltv: float = 0.0
    active_creative_count: int = 0
    creative_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "game": self.game,
            "platform": self.platform,
            "market": self.market,
            "genre": self.genre,
            "stage": self.stage,
            "current_roas": self.current_roas,
            "current_ctr": self.current_ctr,
            "current_fatigue": self.current_fatigue,
            "current_frequency": self.current_frequency,
            "current_ltv": self.current_ltv,
            "active_creative_count": self.active_creative_count,
            "creative_id": self.creative_id,
        }

    def to_context_profile(self) -> ContextProfile:
        """转换为 StrategyMemory 的 ContextProfile."""
        return ContextProfile(
            game=self.game,
            platform=self.platform,
            market=self.market,
            genre=self.genre,
            stage=self.stage,
            metrics={
                "roas": self.current_roas,
                "ctr": self.current_ctr,
                "fatigue": self.current_fatigue,
                "frequency": self.current_frequency,
                "ltv": self.current_ltv,
            },
        )

    @property
    def is_fatigued(self) -> bool:
        return self.current_fatigue >= 0.6

    @property
    def is_underperforming(self) -> bool:
        return self.current_roas < 0.8

    @property
    def is_healthy(self) -> bool:
        return self.current_roas >= 1.2 and self.current_fatigue < 0.4


@dataclass
class PolicyDecision:
    """策略决策 — 最终推荐动作.

    Attributes:
        decision_id: 决策 ID
        action: 推荐动作
        priority: 优先级
        confidence: 置信度等级
        confidence_score: 置信度分数
        rationale: 决策理由
        supporting_patterns: 支持的模式
        supporting_strategies: 支持的策略
        supporting_mutations: 支持的变异优先级
        strategy_type: 对应的策略类型
        expected_impact: 预期影响
        suggested_params: 建议参数 (传递给策略引擎)
        created_at: 创建时间
    """
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action: PolicyAction = PolicyAction.HOLD
    priority: OpportunityPriority = OpportunityPriority.MEDIUM
    confidence: PolicyConfidence = PolicyConfidence.LOW
    confidence_score: float = 0.0
    rationale: str = ""
    supporting_patterns: list[DNAPattern] = field(default_factory=list)
    supporting_strategies: list[StrategyEffectiveness] = field(default_factory=list)
    supporting_mutations: list[MutationPriority] = field(default_factory=list)
    strategy_type: CreativeStrategyType = CreativeStrategyType.UNKNOWN
    expected_impact: str = ""
    suggested_params: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "action": self.action.value,
            "priority": self.priority.value,
            "confidence": self.confidence.value,
            "confidence_score": round(self.confidence_score, 4),
            "rationale": self.rationale,
            "supporting_patterns": [p.to_dict() for p in self.supporting_patterns],
            "supporting_strategies": [s.to_dict() for s in self.supporting_strategies],
            "supporting_mutations": [m.to_dict() for m in self.supporting_mutations],
            "strategy_type": self.strategy_type.value,
            "expected_impact": self.expected_impact,
            "suggested_params": self.suggested_params,
            "created_at": self.created_at,
        }


@dataclass
class PolicyReport:
    """策略报告 — 批量决策结果.

    Attributes:
        report_id: 报告 ID
        decisions: 决策列表
        total_decisions: 总决策数
        high_confidence: 高置信度决策数
        summary: 报告摘要
        created_at: 创建时间
    """
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decisions: list[PolicyDecision] = field(default_factory=list)
    total_decisions: int = 0
    high_confidence: int = 0
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "decisions": [d.to_dict() for d in self.decisions],
            "total_decisions": self.total_decisions,
            "high_confidence": self.high_confidence,
            "summary": self.summary,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# Context → Default Action Mapping
# ═══════════════════════════════════════════════════════════════

# 基于指标状态的默认动作映射 (当学习数据不足时使用)
DEFAULT_ACTION_RULES: list[tuple[dict[str, Any], PolicyAction]] = [
    # (条件, 动作)
    ({"fatigue_gt": 0.7, "frequency_gt": 4.0}, PolicyAction.REFRESH_HOOK),
    ({"fatigue_gt": 0.5, "roas_lt": 0.8}, PolicyAction.REFRESH_CREATIVE),
    ({"roas_lt": 0.5, "ctr_lt": 0.01}, PolicyAction.CHANGE_VISUAL),
    ({"fatigue_gt": 0.6}, PolicyAction.CHANGE_EMOTION),
    ({"roas_gt": 1.5, "fatigue_lt": 0.3}, PolicyAction.SCALE_WINNER),
    ({"roas_lt": 0.8}, PolicyAction.REFRESH_CREATIVE),
    ({"active_lt": 5}, PolicyAction.EXPLORE_NEW),
    ({"roas_gt": 1.2}, PolicyAction.HOLD),
]


# PolicyAction → CreativeStrategyType 映射
POLICY_TO_STRATEGY: dict[PolicyAction, CreativeStrategyType] = {
    PolicyAction.REFRESH_HOOK: CreativeStrategyType.REFRESH_HOOK,
    PolicyAction.CHANGE_VISUAL: CreativeStrategyType.CHANGE_VISUAL_STYLE,
    PolicyAction.CHANGE_EMOTION: CreativeStrategyType.CHANGE_EMOTION,
    PolicyAction.CHANGE_GAMEPLAY: CreativeStrategyType.CHANGE_GAMEPLAY_SHOWCASE,
    PolicyAction.EXPLORE_AUDIENCE: CreativeStrategyType.EXPLORE_NEW_AUDIENCE,
    PolicyAction.COPY_WINNER: CreativeStrategyType.COPY_WINNER_DNA,
    PolicyAction.EXPLORE_NEW: CreativeStrategyType.EXPLORE_NEW_DNA,
    PolicyAction.SCALE_WINNER: CreativeStrategyType.SCALE_WINNER,
    PolicyAction.REFRESH_CREATIVE: CreativeStrategyType.REFRESH_CREATIVE,
    PolicyAction.HOLD: CreativeStrategyType.UNKNOWN,
}


# PolicyAction → 预期影响
ACTION_IMPACTS: dict[PolicyAction, str] = {
    PolicyAction.REFRESH_HOOK: "更换Hook后预计CTR提升20-30%，前3秒留存改善",
    PolicyAction.CHANGE_VISUAL: "视觉更新后预计CTR提升10-20%",
    PolicyAction.CHANGE_EMOTION: "情绪调整后预计付费率提升5-15%",
    PolicyAction.CHANGE_GAMEPLAY: "玩法展示变化后预计留存率提升5-10%",
    PolicyAction.EXPLORE_AUDIENCE: "新受众探索预计扩大20-30%覆盖",
    PolicyAction.COPY_WINNER: "复制赢家DNA预计ROAS达到1.5+",
    PolicyAction.EXPLORE_NEW: "探索新DNA组合可能发现蓝海方向",
    PolicyAction.SCALE_WINNER: "扩大投放预计保持ROAS 1.5+",
    PolicyAction.REFRESH_CREATIVE: "刷新后预计CTR提升15-25%，ROAS恢复至1.0+",
    PolicyAction.HOLD: "保持当前策略，监控指标变化",
}


# ═══════════════════════════════════════════════════════════════
# Creative Policy
# ═══════════════════════════════════════════════════════════════


class CreativePolicy:
    """创意策略 — 上下文感知的最终决策引擎.

    整合所有 E14.4.4 学习模块，根据当前上下文生成最优策略决策.

    决策流程:
      1. Pattern Mining: 从历史赢家中挖掘当前场景下的最优 DNA 模式
      2. Strategy Matching: 从 Strategy Memory 中匹配当前场景的最优策略
      3. Mutation Priority: 从 Mutation Learning 中获取变异优先级
      4. 综合决策: 融合三层结果，输出最终 PolicyDecision

    用法:
        policy = CreativePolicy(memory, pattern_miner, strategy_memory, mutation_learning)
        decision = policy.decide(context)  # 根据上下文生成决策
        decisions = policy.decide_batch(contexts)  # 批量决策
    """

    def __init__(
        self,
        memory: CreativeMemory | None = None,
        pattern_miner: PatternMiner | None = None,
        strategy_memory: StrategyMemory | None = None,
        mutation_learning: MutationLearning | None = None,
    ):
        self._memory = memory or CreativeMemory()
        self._pattern_miner = pattern_miner or PatternMiner(memory=self._memory)
        self._strategy_memory = strategy_memory or StrategyMemory(memory=self._memory)
        self._mutation_learning = mutation_learning or MutationLearning(memory=self._memory)
        self._history: list[PolicyDecision] = []

    # ── 核心决策 ──────────────────────────────────────────────

    def decide(self, context: PolicyContext) -> PolicyDecision:
        """根据上下文生成最优策略决策.

        三层决策融合:
          1. Pattern Mining → 当前场景下最优 DNA 模式
          2. Strategy Memory → 当前场景下最优策略
          3. Mutation Learning → 当前最优变异方向

        Args:
            context: 策略上下文

        Returns:
            PolicyDecision: 策略决策
        """
        # 1. Pattern Mining: 获取可靠模式
        reliable_patterns = self._pattern_miner.get_reliable_patterns()

        # 2. Strategy Memory: 匹配当前场景的最优策略
        context_profile = context.to_context_profile()
        recommended_strategies = self._strategy_memory.recommend(
            context_profile, min_confidence=0.2, top_n=5,
        )

        # 3. Mutation Learning: 获取变异优先级
        mutation_priorities = self._mutation_learning.get_priorities(
            min_confidence=0.2, top_n=5,
        )

        # 4. 综合决策
        decision = self._fuse_decisions(
            context=context,
            patterns=reliable_patterns,
            strategies=recommended_strategies,
            mutations=mutation_priorities,
        )

        self._history.append(decision)
        return decision

    def decide_batch(
        self,
        contexts: list[PolicyContext],
    ) -> PolicyReport:
        """批量决策.

        Args:
            contexts: 上下文列表

        Returns:
            PolicyReport: 策略报告
        """
        decisions = [self.decide(ctx) for ctx in contexts]
        high = sum(1 for d in decisions if d.confidence == PolicyConfidence.HIGH)

        return PolicyReport(
            decisions=decisions,
            total_decisions=len(decisions),
            high_confidence=high,
            summary=f"共 {len(decisions)} 个决策，{high} 个高置信度",
        )

    # ── 决策融合 ──────────────────────────────────────────────

    def _fuse_decisions(
        self,
        context: PolicyContext,
        patterns: list[DNAPattern],
        strategies: list[StrategyEffectiveness],
        mutations: list[MutationPriority],
    ) -> PolicyDecision:
        """融合三层学习结果生成最终决策.

        融合策略:
          1. 如果 Strategy Memory 有足够数据 → 优先使用策略推荐
          2. 如果 Pattern Miner 有可靠模式 → 结合模式推荐
          3. 如果以上都不足 → 使用默认规则 (基于指标)
          4. Mutation Learning 用于调整权重参数
        """
        # 评估各层数据充足度
        has_strategy_data = len(strategies) > 0 and strategies[0].attempt_count >= 5
        has_pattern_data = len(patterns) > 0
        has_mutation_data = len(mutations) > 0

        # 场景 1: Strategy Memory 数据充足 → 优先使用
        if has_strategy_data:
            return self._decide_from_strategies(context, strategies, mutations)

        # 场景 2: Pattern Miner 有数据 → 结合模式
        if has_pattern_data:
            return self._decide_from_patterns(context, patterns, mutations)

        # 场景 3: 全部不足 → 使用默认规则
        return self._decide_from_defaults(context, mutations)

    def _decide_from_strategies(
        self,
        context: PolicyContext,
        strategies: list[StrategyEffectiveness],
        mutations: list[MutationPriority],
    ) -> PolicyDecision:
        """从 Strategy Memory 结果生成决策."""
        best = strategies[0]
        action = self._strategy_type_to_action(best.strategy_type)
        strategy_type = best.strategy_type
        confidence = self._compute_confidence(
            strategy_data=True, pattern_data=False, mutation_data=len(mutations) > 0,
            strategy_count=best.attempt_count,
        )

        # 构建建议参数 (包含 mutation 学习的权重)
        mutation_weights = {}
        if mutations:
            mutation_weights = {
                m.gene_category.value: m.suggested_weight
                for m in mutations[:5]
            }

        return PolicyDecision(
            action=action,
            priority=self._estimate_priority(best.success_rate, best.confidence),
            confidence=confidence[0],
            confidence_score=confidence[1],
            rationale=(
                f"基于历史策略记忆: {best.strategy_type.value} 在 "
                f"({context.game}/{context.platform}/{context.market}) 场景下 "
                f"成功率 {best.success_rate:.0%}，置信度 {best.confidence:.2f}"
            ),
            supporting_strategies=strategies,
            supporting_mutations=mutations,
            strategy_type=strategy_type,
            expected_impact=ACTION_IMPACTS.get(action, "继续观察"),
            suggested_params={
                "mutation_weights": mutation_weights,
                "source": "strategy_memory",
                "context": context.to_dict(),
            },
        )

    def _decide_from_patterns(
        self,
        context: PolicyContext,
        patterns: list[DNAPattern],
        mutations: list[MutationPriority],
    ) -> PolicyDecision:
        """从 Pattern Miner 结果生成决策."""
        # 从图案中推断最佳动作
        best_pattern = patterns[0]
        action = self._infer_action_from_pattern(best_pattern)
        strategy_type = POLICY_TO_STRATEGY.get(action, CreativeStrategyType.REFRESH_HOOK)
        confidence = self._compute_confidence(
            strategy_data=False, pattern_data=True, mutation_data=len(mutations) > 0,
            pattern_count=best_pattern.occurrence_count,
        )

        mutation_weights = {}
        if mutations:
            mutation_weights = {
                m.gene_category.value: m.suggested_weight
                for m in mutations[:5]
            }

        return PolicyDecision(
            action=action,
            priority=self._estimate_priority(best_pattern.success_rate, best_pattern.confidence_score),
            confidence=confidence[0],
            confidence_score=confidence[1],
            rationale=(
                f"基于DNA模式挖掘: {best_pattern.gene_key} "
                f"成功率 {best_pattern.success_rate:.0%}，"
                f"样本 {best_pattern.occurrence_count}"
            ),
            supporting_patterns=patterns,
            supporting_mutations=mutations,
            strategy_type=strategy_type,
            expected_impact=ACTION_IMPACTS.get(action, "继续观察"),
            suggested_params={
                "mutation_weights": mutation_weights,
                "source": "pattern_miner",
                "target_genes": best_pattern.genes,
            },
        )

    def _decide_from_defaults(
        self,
        context: PolicyContext,
        mutations: list[MutationPriority],
    ) -> PolicyDecision:
        """从默认规则生成决策."""
        action = self._apply_default_rules(context)
        strategy_type = POLICY_TO_STRATEGY.get(action, CreativeStrategyType.UNKNOWN)

        mutation_weights = {}
        if mutations:
            mutation_weights = {
                m.gene_category.value: m.suggested_weight
                for m in mutations[:5]
            }

        return PolicyDecision(
            action=action,
            priority=OpportunityPriority.MEDIUM,
            confidence=PolicyConfidence.LOW,
            confidence_score=0.3,
            rationale=(
                f"基于默认规则决策 (数据不足): "
                f"ROAS={context.current_roas:.2f}, "
                f"疲劳度={context.current_fatigue:.2f}, "
                f"频次={context.current_frequency:.1f}"
            ),
            supporting_mutations=mutations,
            strategy_type=strategy_type,
            expected_impact=ACTION_IMPACTS.get(action, "继续观察"),
            suggested_params={
                "mutation_weights": mutation_weights,
                "source": "default_rules",
            },
        )

    # ── 默认规则 ──────────────────────────────────────────────

    def _apply_default_rules(self, context: PolicyContext) -> PolicyAction:
        """应用默认规则确定动作."""
        for conditions, action in DEFAULT_ACTION_RULES:
            if self._check_conditions(context, conditions):
                return action
        return PolicyAction.HOLD

    def _check_conditions(self, context: PolicyContext, conditions: dict[str, Any]) -> bool:
        """检查条件是否满足."""
        for key, threshold in conditions.items():
            if key.startswith("fatigue_gt"):
                if not (context.current_fatigue > threshold):
                    return False
            elif key.startswith("fatigue_lt"):
                if not (context.current_fatigue < threshold):
                    return False
            elif key.startswith("frequency_gt"):
                if not (context.current_frequency > threshold):
                    return False
            elif key.startswith("roas_gt"):
                if not (context.current_roas > threshold):
                    return False
            elif key.startswith("roas_lt"):
                if not (context.current_roas < threshold):
                    return False
            elif key.startswith("ctr_lt"):
                if not (context.current_ctr < threshold):
                    return False
            elif key.startswith("active_lt"):
                if not (context.active_creative_count < threshold):
                    return False
        return True

    # ── 辅助方法 ──────────────────────────────────────────────

    def _strategy_type_to_action(self, strategy_type: CreativeStrategyType) -> PolicyAction:
        """策略类型 → 策略动作."""
        mapping: dict[CreativeStrategyType, PolicyAction] = {
            CreativeStrategyType.REFRESH_HOOK: PolicyAction.REFRESH_HOOK,
            CreativeStrategyType.CHANGE_VISUAL_STYLE: PolicyAction.CHANGE_VISUAL,
            CreativeStrategyType.CHANGE_GAMEPLAY_SHOWCASE: PolicyAction.CHANGE_GAMEPLAY,
            CreativeStrategyType.CHANGE_EMOTION: PolicyAction.CHANGE_EMOTION,
            CreativeStrategyType.COPY_WINNER_DNA: PolicyAction.COPY_WINNER,
            CreativeStrategyType.EXPLORE_NEW_DNA: PolicyAction.EXPLORE_NEW,
            CreativeStrategyType.OPTIMIZE_OPENING: PolicyAction.REFRESH_HOOK,
            CreativeStrategyType.SCALE_WINNER: PolicyAction.SCALE_WINNER,
            CreativeStrategyType.EXPLORE_NEW_AUDIENCE: PolicyAction.EXPLORE_AUDIENCE,
            CreativeStrategyType.TEST_NEW_CONCEPT: PolicyAction.EXPLORE_NEW,
            CreativeStrategyType.REFRESH_CREATIVE: PolicyAction.REFRESH_CREATIVE,
        }
        return mapping.get(strategy_type, PolicyAction.HOLD)

    def _infer_action_from_pattern(self, pattern: DNAPattern) -> PolicyAction:
        """从 DNA 模式推断动作."""
        # 根据模式中的基因类别推断动作
        gene_categories = set(pattern.genes.keys())

        if "hook" in gene_categories:
            return PolicyAction.REFRESH_HOOK
        if "visual" in gene_categories:
            return PolicyAction.CHANGE_VISUAL
        if "emotion" in gene_categories:
            return PolicyAction.CHANGE_EMOTION
        if "gameplay" in gene_categories:
            return PolicyAction.CHANGE_GAMEPLAY
        if "audience" in gene_categories:
            return PolicyAction.EXPLORE_AUDIENCE

        return PolicyAction.REFRESH_CREATIVE

    def _compute_confidence(
        self,
        strategy_data: bool = False,
        pattern_data: bool = False,
        mutation_data: bool = False,
        strategy_count: int = 0,
        pattern_count: int = 0,
    ) -> tuple[PolicyConfidence, float]:
        """计算综合置信度.

        Returns:
            (PolicyConfidence, confidence_score)
        """
        score = 0.0

        if strategy_data:
            score += 0.5
            if strategy_count >= 10:
                score += 0.2
        if pattern_data:
            score += 0.3
            if pattern_count >= 20:
                score += 0.1
        if mutation_data:
            score += 0.1

        score = min(score, 1.0)

        if score >= 0.7:
            return PolicyConfidence.HIGH, score
        elif score >= 0.4:
            return PolicyConfidence.MEDIUM, score
        elif score > 0:
            return PolicyConfidence.LOW, score
        else:
            return PolicyConfidence.INSUFFICIENT, 0.0

    def _estimate_priority(
        self,
        success_rate: float,
        confidence: float,
    ) -> OpportunityPriority:
        """根据成功率和置信度估算优先级."""
        score = success_rate * confidence
        if score >= 0.6:
            return OpportunityPriority.HIGH
        elif score >= 0.3:
            return OpportunityPriority.MEDIUM
        else:
            return OpportunityPriority.LOW

    # ── 查询 ──────────────────────────────────────────────────

    def get_history(self, n: int = 20) -> list[PolicyDecision]:
        return self._history[-n:]

    def get_high_confidence_decisions(self) -> list[PolicyDecision]:
        return [d for d in self._history if d.confidence == PolicyConfidence.HIGH]

    def stats(self) -> dict[str, Any]:
        total = len(self._history)
        if total == 0:
            return {"total": 0}
        conf_counts: dict[str, int] = {}
        for d in self._history:
            c = d.confidence.value
            conf_counts[c] = conf_counts.get(c, 0) + 1
        return {
            "total": total,
            "by_confidence": conf_counts,
            "high_confidence": len(self.get_high_confidence_decisions()),
        }

    def reset(self) -> None:
        self._history.clear()


def create_creative_policy(
    memory: CreativeMemory | None = None,
    pattern_miner: PatternMiner | None = None,
    strategy_memory: StrategyMemory | None = None,
    mutation_learning: MutationLearning | None = None,
) -> CreativePolicy:
    """创建默认 CreativePolicy."""
    return CreativePolicy(
        memory=memory,
        pattern_miner=pattern_miner,
        strategy_memory=strategy_memory,
        mutation_learning=mutation_learning,
    )