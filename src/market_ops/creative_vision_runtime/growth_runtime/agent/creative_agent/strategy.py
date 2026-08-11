"""E14.4.2.2 Creative Strategy Engine — 创意策略生成.

将 Creative Opportunity 转化为具体的 Creative Strategy:

  输入: CreativeOpportunity + DNA Memory + Winner Patterns
  输出: CreativeStrategy (strategy_type, keep_genes, change_genes, mutation_directions)

核心能力:
  - 机会→策略映射: 根据机会类型确定策略方向
  - 基因保持/变更: 基于 Winner DNA 和当前 DNA 决定保留和变更的基因
  - 变异方向: 给出具体的基因变异方向建议
  - 策略验证: 确保策略不会破坏核心基因结构

策略类型:
  - REFRESH_HOOK: 替换 Hook 基因
  - CHANGE_VISUAL_STYLE: 改变视觉风格
  - CHANGE_GAMEPLAY_SHOWCASE: 改变玩法展示
  - CHANGE_EMOTION: 改变情绪驱动
  - COPY_WINNER_DNA: 复制赢家 DNA
  - EXPLORE_NEW_DNA: 探索全新 DNA 组合
  - OPTIMIZE_OPENING: 优化前3秒
  - SCALE_WINNER: 扩大赢家投放
  - EXPLORE_NEW_AUDIENCE: 探索新受众
  - TEST_NEW_CONCEPT: 测试新概念
  - REFRESH_CREATIVE: 刷新素材

设计原则:
  - 确定性映射，不依赖 AI
  - 基于 Winner DNA 的学习机制
  - 策略可追溯、可解释
  - 与 E11 Evolution Engine 兼容
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .opportunity import (
    CreativeOpportunity,
    CreativeOpportunityType,
    OpportunityPriority,
)
from .dna_engine import (
    DNAEngine,
    CreativeDNAProfile,
    WinnerDNAReport,
    HookType,
    VisualStyle,
    EmotionType,
    GameplayFocus,
    AudienceType,
    ContextType,
)
from .memory import CreativeMemory, CreativeDNAMemoryEntry


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class CreativeStrategyType(str, Enum):
    """创意策略类型."""
    REFRESH_HOOK = "refresh_hook"              # 替换 Hook
    CHANGE_VISUAL_STYLE = "change_visual"       # 改变视觉风格
    CHANGE_GAMEPLAY_SHOWCASE = "change_gameplay" # 改变玩法展示
    CHANGE_EMOTION = "change_emotion"           # 改变情绪驱动
    COPY_WINNER_DNA = "copy_winner"             # 复制赢家 DNA
    EXPLORE_NEW_DNA = "explore"                 # 探索全新 DNA
    OPTIMIZE_OPENING = "optimize_opening"       # 优化前3秒
    SCALE_WINNER = "scale_winner"               # 扩大赢家
    EXPLORE_NEW_AUDIENCE = "explore_audience"   # 探索新受众
    TEST_NEW_CONCEPT = "test_concept"           # 测试新概念
    REFRESH_CREATIVE = "refresh_creative"       # 刷新素材
    UNKNOWN = "unknown"


class GeneMutationAction(str, Enum):
    """基因变异动作."""
    KEEP = "keep"          # 保持
    CHANGE = "change"      # 变更
    EXPLORE = "explore"    # 探索
    BOOST = "boost"        # 强化
    REDUCE = "reduce"      # 弱化


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class GeneMutation:
    """单个基因的变异指令.

    Attributes:
        gene_category: 基因类别 (hook/visual/gameplay/emotion/audience/context/monetization)
        action: 变异动作 (keep/change/explore/boost/reduce)
        current_value: 当前值
        target_values: 目标值候选 (多个可选方向)
        reason: 变异原因
        weight: 变异权重 (0-1)
    """
    gene_category: str = ""
    action: GeneMutationAction = GeneMutationAction.KEEP
    current_value: str = ""
    target_values: list[str] = field(default_factory=list)
    reason: str = ""
    weight: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_category": self.gene_category,
            "action": self.action.value,
            "current_value": self.current_value,
            "target_values": self.target_values,
            "reason": self.reason,
            "weight": self.weight,
        }


@dataclass
class CreativeStrategy:
    """创意策略 — 从机会到执行方向.

    Attributes:
        strategy_id: 策略 ID
        strategy_type: 策略类型
        opportunity_id: 触发机会 ID
        target_creative_id: 目标创意 ID
        keep_genes: 保持的基因 (不变)
        change_genes: 变更的基因 (变异方向)
        mutation_plan: 基因变异指令列表
        rationale: 策略理由
        expected_impact: 预期影响
        confidence: 置信度
        priority: 优先级
        winner_references: 参考的赢家 DNA ID
        created_at: 创建时间
        metadata: 扩展元数据
    """
    strategy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_type: CreativeStrategyType = CreativeStrategyType.UNKNOWN
    opportunity_id: str = ""
    target_creative_id: str = ""
    keep_genes: dict[str, str] = field(default_factory=dict)
    change_genes: dict[str, list[str]] = field(default_factory=dict)
    mutation_plan: list[GeneMutation] = field(default_factory=list)
    rationale: str = ""
    expected_impact: str = ""
    confidence: float = 0.0
    priority: OpportunityPriority = OpportunityPriority.MEDIUM
    winner_references: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_type": self.strategy_type.value,
            "opportunity_id": self.opportunity_id,
            "target_creative_id": self.target_creative_id,
            "keep_genes": self.keep_genes,
            "change_genes": self.change_genes,
            "mutation_plan": [m.to_dict() for m in self.mutation_plan],
            "rationale": self.rationale,
            "expected_impact": self.expected_impact,
            "confidence": self.confidence,
            "priority": self.priority.value,
            "winner_references": self.winner_references,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @property
    def mutation_count(self) -> int:
        return len(self.mutation_plan)

    @property
    def change_count(self) -> int:
        return len([m for m in self.mutation_plan if m.action != GeneMutationAction.KEEP])

    @property
    def summary(self) -> str:
        parts = [f"[{self.strategy_type.value}]"]
        if self.keep_genes:
            parts.append(f"keep={','.join(self.keep_genes.keys())}")
        if self.change_genes:
            change_parts = []
            for cat, targets in self.change_genes.items():
                change_parts.append(f"{cat}→{targets[0] if targets else '?'}")
            parts.append(f"change={','.join(change_parts)}")
        return " ".join(parts)


@dataclass
class StrategyReport:
    """策略报告 — 批量策略生成结果.

    Attributes:
        report_id: 报告 ID
        strategies: 策略列表
        total_opportunities: 机会总数
        total_strategies: 策略总数
        summary: 报告摘要
        created_at: 创建时间
    """
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategies: list[CreativeStrategy] = field(default_factory=list)
    total_opportunities: int = 0
    total_strategies: int = 0
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "strategies": [s.to_dict() for s in self.strategies],
            "total_opportunities": self.total_opportunities,
            "total_strategies": self.total_strategies,
            "summary": self.summary,
            "created_at": self.created_at,
        }

    @property
    def strategy_count(self) -> int:
        return len(self.strategies)


# ═══════════════════════════════════════════════════════════════
# Opportunity → Strategy Mapping
# ═══════════════════════════════════════════════════════════════

OPPORTUNITY_TO_STRATEGY: dict[CreativeOpportunityType, list[CreativeStrategyType]] = {
    CreativeOpportunityType.REFRESH_CREATIVE: [
        CreativeStrategyType.REFRESH_CREATIVE,
        CreativeStrategyType.REFRESH_HOOK,
    ],
    CreativeOpportunityType.REPLACE_HOOK: [
        CreativeStrategyType.REFRESH_HOOK,
        CreativeStrategyType.OPTIMIZE_OPENING,
    ],
    CreativeOpportunityType.CHANGE_VISUAL: [
        CreativeStrategyType.CHANGE_VISUAL_STYLE,
    ],
    CreativeOpportunityType.CHANGE_GAMEPLAY: [
        CreativeStrategyType.CHANGE_GAMEPLAY_SHOWCASE,
    ],
    CreativeOpportunityType.CHANGE_EMOTION: [
        CreativeStrategyType.CHANGE_EMOTION,
    ],
    CreativeOpportunityType.COPY_WINNER_DNA: [
        CreativeStrategyType.COPY_WINNER_DNA,
        CreativeStrategyType.SCALE_WINNER,
    ],
    CreativeOpportunityType.EXPLORE_NEW_AUDIENCE: [
        CreativeStrategyType.EXPLORE_NEW_AUDIENCE,
    ],
    CreativeOpportunityType.EXPLORE_NEW_DNA: [
        CreativeStrategyType.EXPLORE_NEW_DNA,
        CreativeStrategyType.TEST_NEW_CONCEPT,
    ],
    CreativeOpportunityType.SCALE_WINNER: [
        CreativeStrategyType.SCALE_WINNER,
    ],
    CreativeOpportunityType.OPTIMIZE_OPENING: [
        CreativeStrategyType.OPTIMIZE_OPENING,
        CreativeStrategyType.REFRESH_HOOK,
    ],
    CreativeOpportunityType.TEST_NEW_CONCEPT: [
        CreativeStrategyType.TEST_NEW_CONCEPT,
        CreativeStrategyType.EXPLORE_NEW_DNA,
    ],
}


# ═══════════════════════════════════════════════════════════════
# Gene Mutation Rules
# ═══════════════════════════════════════════════════════════════

# 策略类型 → 基因变异计划
STRATEGY_GENE_RULES: dict[CreativeStrategyType, dict[str, GeneMutationAction]] = {
    CreativeStrategyType.REFRESH_HOOK: {
        "hook": GeneMutationAction.CHANGE,
        "visual": GeneMutationAction.KEEP,
        "gameplay": GeneMutationAction.KEEP,
        "emotion": GeneMutationAction.KEEP,
        "audience": GeneMutationAction.KEEP,
        "context": GeneMutationAction.KEEP,
        "monetization": GeneMutationAction.KEEP,
    },
    CreativeStrategyType.CHANGE_VISUAL_STYLE: {
        "hook": GeneMutationAction.KEEP,
        "visual": GeneMutationAction.CHANGE,
        "gameplay": GeneMutationAction.KEEP,
        "emotion": GeneMutationAction.KEEP,
        "audience": GeneMutationAction.KEEP,
        "context": GeneMutationAction.KEEP,
        "monetization": GeneMutationAction.KEEP,
    },
    CreativeStrategyType.CHANGE_GAMEPLAY_SHOWCASE: {
        "hook": GeneMutationAction.KEEP,
        "visual": GeneMutationAction.KEEP,
        "gameplay": GeneMutationAction.CHANGE,
        "emotion": GeneMutationAction.KEEP,
        "audience": GeneMutationAction.EXPLORE,
        "context": GeneMutationAction.KEEP,
        "monetization": GeneMutationAction.KEEP,
    },
    CreativeStrategyType.CHANGE_EMOTION: {
        "hook": GeneMutationAction.EXPLORE,
        "visual": GeneMutationAction.KEEP,
        "gameplay": GeneMutationAction.KEEP,
        "emotion": GeneMutationAction.CHANGE,
        "audience": GeneMutationAction.KEEP,
        "context": GeneMutationAction.KEEP,
        "monetization": GeneMutationAction.KEEP,
    },
    CreativeStrategyType.COPY_WINNER_DNA: {
        "hook": GeneMutationAction.CHANGE,
        "visual": GeneMutationAction.CHANGE,
        "gameplay": GeneMutationAction.CHANGE,
        "emotion": GeneMutationAction.CHANGE,
        "audience": GeneMutationAction.CHANGE,
        "context": GeneMutationAction.CHANGE,
        "monetization": GeneMutationAction.CHANGE,
    },
    CreativeStrategyType.EXPLORE_NEW_DNA: {
        "hook": GeneMutationAction.EXPLORE,
        "visual": GeneMutationAction.EXPLORE,
        "gameplay": GeneMutationAction.EXPLORE,
        "emotion": GeneMutationAction.EXPLORE,
        "audience": GeneMutationAction.EXPLORE,
        "context": GeneMutationAction.EXPLORE,
        "monetization": GeneMutationAction.EXPLORE,
    },
    CreativeStrategyType.OPTIMIZE_OPENING: {
        "hook": GeneMutationAction.CHANGE,
        "visual": GeneMutationAction.KEEP,
        "gameplay": GeneMutationAction.KEEP,
        "emotion": GeneMutationAction.EXPLORE,
        "audience": GeneMutationAction.KEEP,
        "context": GeneMutationAction.KEEP,
        "monetization": GeneMutationAction.KEEP,
    },
    CreativeStrategyType.SCALE_WINNER: {
        "hook": GeneMutationAction.KEEP,
        "visual": GeneMutationAction.KEEP,
        "gameplay": GeneMutationAction.KEEP,
        "emotion": GeneMutationAction.KEEP,
        "audience": GeneMutationAction.BOOST,
        "context": GeneMutationAction.EXPLORE,
        "monetization": GeneMutationAction.KEEP,
    },
    CreativeStrategyType.EXPLORE_NEW_AUDIENCE: {
        "hook": GeneMutationAction.KEEP,
        "visual": GeneMutationAction.KEEP,
        "gameplay": GeneMutationAction.KEEP,
        "emotion": GeneMutationAction.KEEP,
        "audience": GeneMutationAction.EXPLORE,
        "context": GeneMutationAction.EXPLORE,
        "monetization": GeneMutationAction.KEEP,
    },
    CreativeStrategyType.TEST_NEW_CONCEPT: {
        "hook": GeneMutationAction.EXPLORE,
        "visual": GeneMutationAction.EXPLORE,
        "gameplay": GeneMutationAction.EXPLORE,
        "emotion": GeneMutationAction.EXPLORE,
        "audience": GeneMutationAction.KEEP,
        "context": GeneMutationAction.KEEP,
        "monetization": GeneMutationAction.KEEP,
    },
    CreativeStrategyType.REFRESH_CREATIVE: {
        "hook": GeneMutationAction.CHANGE,
        "visual": GeneMutationAction.CHANGE,
        "gameplay": GeneMutationAction.KEEP,
        "emotion": GeneMutationAction.KEEP,
        "audience": GeneMutationAction.KEEP,
        "context": GeneMutationAction.EXPLORE,
        "monetization": GeneMutationAction.KEEP,
    },
}

# Hook 候选值 (按类别)
HOOK_ALTERNATIVES: dict[str, list[str]] = {
    "before_after": ["impossible_result", "collection", "reward_reveal"],
    "character_reveal": ["before_after", "rescue", "transformation"],
    "curiosity": ["impossible_result", "rare_item", "reward_reveal"],
    "challenge": ["rescue", "progression", "rare_item"],
    "progression": ["challenge", "collection", "transformation"],
    "rescue": ["challenge", "before_after", "transformation"],
    "impossible_result": ["curiosity", "before_after", "rare_item"],
    "collection": ["progression", "reward_reveal", "rare_item"],
    "reward_reveal": ["curiosity", "collection", "rare_item"],
    "rare_item": ["reward_reveal", "impossible_result", "collection"],
    "transformation": ["before_after", "rescue", "story"],
    "story": ["transformation", "rescue", "curiosity"],
}

VISUAL_ALTERNATIVES: dict[str, list[str]] = {
    "fantasy": ["realistic", "vibrant", "dark"],
    "realistic": ["fantasy", "premium", "dark"],
    "cartoon": ["vibrant", "fantasy", "minimal"],
    "dark": ["fantasy", "realistic", "premium"],
    "vibrant": ["cartoon", "fantasy", "retro"],
    "minimal": ["premium", "realistic", "dark"],
    "premium": ["realistic", "minimal", "dark"],
    "retro": ["vibrant", "cartoon", "minimal"],
}

EMOTION_ALTERNATIVES: dict[str, list[str]] = {
    "curiosity": ["excitement", "surprise", "desire"],
    "excitement": ["curiosity", "achievement", "urgency"],
    "fear": ["urgency", "surprise", "curiosity"],
    "satisfaction": ["achievement", "relaxation", "desire"],
    "surprise": ["curiosity", "excitement", "fear"],
    "desire": ["excitement", "achievement", "curiosity"],
    "achievement": ["satisfaction", "excitement", "desire"],
    "urgency": ["fear", "excitement", "surprise"],
    "relaxation": ["satisfaction", "curiosity", "desire"],
}

GAMEPLAY_ALTERNATIVES: dict[str, list[str]] = {
    "merge": ["puzzle", "match3", "casual"],
    "puzzle": ["merge", "strategy", "casual"],
    "match3": ["merge", "puzzle", "casual"],
    "rpg": ["strategy", "action", "simulation"],
    "strategy": ["rpg", "simulation", "puzzle"],
    "casual": ["merge", "puzzle", "match3"],
    "action": ["rpg", "strategy", "simulation"],
    "simulation": ["strategy", "rpg", "casual"],
}

AUDIENCE_ALTERNATIVES: dict[str, list[str]] = {
    "casual_gamers": ["female_25_45", "broad", "midcore_gamers"],
    "midcore_gamers": ["casual_gamers", "male_18_35", "hardcore_gamers"],
    "hardcore_gamers": ["male_18_35", "whale_hunters", "midcore_gamers"],
    "whale_hunters": ["hardcore_gamers", "midcore_gamers", "male_18_35"],
    "female_25_45": ["casual_gamers", "broad", "midcore_gamers"],
    "male_18_35": ["hardcore_gamers", "midcore_gamers", "broad"],
    "broad": ["casual_gamers", "female_25_45", "male_18_35"],
}


# ═══════════════════════════════════════════════════════════════
# Creative Strategy Engine
# ═══════════════════════════════════════════════════════════════


class CreativeStrategyEngine:
    """创意策略引擎 — 将机会转化为具体策略.

    职责:
      1. 机会→策略映射: 根据机会类型确定策略方向
      2. 基因保持/变更: 基于 Winner DNA 决定保留和变更的基因
      3. 变异方向推荐: 给出具体的基因变异候选值
      4. 策略验证: 确保策略完整性

    用法:
        engine = CreativeStrategyEngine(memory=creative_memory, dna_engine=dna_engine)
        strategy = engine.generate(opportunity, current_dna)
    """

    def __init__(
        self,
        memory: CreativeMemory | None = None,
        dna_engine: DNAEngine | None = None,
    ):
        self._memory = memory or CreativeMemory()
        self._dna_engine = dna_engine or DNAEngine()
        self._history: list[CreativeStrategy] = []

    # ── 核心生成 ──────────────────────────────────────────────

    def generate(
        self,
        opportunity: CreativeOpportunity,
        current_dna: CreativeDNAProfile | None = None,
    ) -> CreativeStrategy:
        """根据机会生成创意策略.

        Args:
            opportunity: 创意机会
            current_dna: 当前素材的 DNA (可选)

        Returns:
            CreativeStrategy: 创意策略
        """
        # 1. 机会→策略类型映射
        strategy_type = self._map_opportunity_to_strategy(opportunity)

        # 2. 获取基因变异规则
        gene_rules = STRATEGY_GENE_RULES.get(strategy_type, {})

        # 3. 构建基因保持/变更计划
        keep_genes: dict[str, str] = {}
        change_genes: dict[str, list[str]] = {}
        mutation_plan: list[GeneMutation] = []

        for category, action in gene_rules.items():
            current_value = self._get_current_gene_value(current_dna, category)

            if action == GeneMutationAction.KEEP:
                if current_value:
                    keep_genes[category] = current_value
                mutation_plan.append(GeneMutation(
                    gene_category=category,
                    action=GeneMutationAction.KEEP,
                    current_value=current_value,
                    reason="核心基因保持不变",
                    weight=0.0,
                ))
            elif action == GeneMutationAction.CHANGE:
                target_values = self._get_target_values(category, current_value, strategy_type)
                change_genes[category] = target_values
                mutation_plan.append(GeneMutation(
                    gene_category=category,
                    action=GeneMutationAction.CHANGE,
                    current_value=current_value,
                    target_values=target_values,
                    reason=self._get_change_reason(category, strategy_type),
                    weight=self._get_gene_weight(category),
                ))
            elif action == GeneMutationAction.EXPLORE:
                target_values = self._get_explore_targets(category, current_value)
                change_genes[category] = target_values
                mutation_plan.append(GeneMutation(
                    gene_category=category,
                    action=GeneMutationAction.EXPLORE,
                    current_value=current_value,
                    target_values=target_values,
                    reason=f"探索 {category} 新方向",
                    weight=self._get_gene_weight(category) * 0.7,
                ))
            elif action == GeneMutationAction.BOOST:
                if current_value:
                    keep_genes[category] = current_value
                mutation_plan.append(GeneMutation(
                    gene_category=category,
                    action=GeneMutationAction.BOOST,
                    current_value=current_value,
                    reason=f"强化 {category} 基因",
                    weight=self._get_gene_weight(category) * 1.2,
                ))

        # 4. Winner DNA 参考 (对于 COPY_WINNER_DNA 策略)
        winner_refs = self._get_winner_references(strategy_type)

        # 5. 构建理由
        rationale = self._build_rationale(strategy_type, opportunity, keep_genes, change_genes)

        # 6. 预期影响
        expected_impact = self._estimate_strategy_impact(strategy_type, change_genes)

        strategy = CreativeStrategy(
            strategy_type=strategy_type,
            opportunity_id=opportunity.opportunity_id,
            target_creative_id=opportunity.target_creative_id,
            keep_genes=keep_genes,
            change_genes=change_genes,
            mutation_plan=mutation_plan,
            rationale=rationale,
            expected_impact=expected_impact,
            confidence=opportunity.confidence,
            priority=opportunity.priority,
            winner_references=winner_refs,
        )

        self._history.append(strategy)
        return strategy

    def generate_from_opportunities(
        self,
        opportunities: list[CreativeOpportunity],
        current_dna_map: dict[str, CreativeDNAProfile] | None = None,
    ) -> StrategyReport:
        """批量生成策略.

        Args:
            opportunities: 机会列表
            current_dna_map: creative_id → DNA 映射

        Returns:
            StrategyReport: 策略报告
        """
        dna_map = current_dna_map or {}
        strategies = []
        for opp in opportunities:
            dna = dna_map.get(opp.target_creative_id)
            strategy = self.generate(opp, dna)
            strategies.append(strategy)

        summary_parts = []
        strategy_counts: dict[str, int] = {}
        for s in strategies:
            t = s.strategy_type.value
            strategy_counts[t] = strategy_counts.get(t, 0) + 1
        for stype, count in sorted(strategy_counts.items()):
            summary_parts.append(f"{stype}: {count}")

        return StrategyReport(
            strategies=strategies,
            total_opportunities=len(opportunities),
            total_strategies=len(strategies),
            summary=" | ".join(summary_parts) if summary_parts else "无策略",
        )

    # ── 内部映射 ──────────────────────────────────────────────

    def _map_opportunity_to_strategy(
        self,
        opportunity: CreativeOpportunity,
    ) -> CreativeStrategyType:
        """机会类型 → 策略类型."""
        candidates = OPPORTUNITY_TO_STRATEGY.get(
            opportunity.type,
            [CreativeStrategyType.UNKNOWN],
        )
        return candidates[0] if candidates else CreativeStrategyType.UNKNOWN

    def _get_current_gene_value(
        self,
        dna: CreativeDNAProfile | None,
        category: str,
    ) -> str:
        """获取当前 DNA 的基因值."""
        if dna is None:
            return ""
        gene = dna.genes.get(category)
        return str(gene.value) if gene and gene.value else ""

    def _get_target_values(
        self,
        category: str,
        current_value: str,
        strategy_type: CreativeStrategyType,
    ) -> list[str]:
        """获取基因目标值 (变更方向)."""
        if strategy_type == CreativeStrategyType.COPY_WINNER_DNA:
            return self._get_winner_gene_values(category)

        alternatives_map = {
            "hook": HOOK_ALTERNATIVES,
            "visual": VISUAL_ALTERNATIVES,
            "emotion": EMOTION_ALTERNATIVES,
            "gameplay": GAMEPLAY_ALTERNATIVES,
            "audience": AUDIENCE_ALTERNATIVES,
        }
        alt_map = alternatives_map.get(category, {})
        alternatives = alt_map.get(current_value, [])
        return alternatives[:3]

    def _get_explore_targets(
        self,
        category: str,
        current_value: str,
    ) -> list[str]:
        """获取探索目标 (排除当前值)."""
        all_values_map = {
            "hook": [e.value for e in HookType if e.value != "unknown"],
            "visual": [e.value for e in VisualStyle if e.value != "unknown"],
            "emotion": [e.value for e in EmotionType if e.value != "unknown"],
            "gameplay": [e.value for e in GameplayFocus if e.value != "unknown"],
            "audience": [e.value for e in AudienceType if e.value != "unknown"],
            "context": [e.value for e in ContextType if e.value != "unknown"],
        }
        all_values = all_values_map.get(category, [])
        candidates = [v for v in all_values if v != current_value]
        return candidates[:3] if candidates else all_values[:2]

    def _get_winner_gene_values(self, category: str) -> list[str]:
        """从赢家 DNA 中获取目标基因值."""
        values = []
        try:
            winners = self._memory.get_winner_dnas()
            for w in winners[:5]:
                if w.dna:
                    gene = w.dna.genes.get(category)
                    if gene and gene.value:
                        v = str(gene.value)
                        if v not in values:
                            values.append(v)
        except Exception:
            pass
        return values[:3] if values else ["winner_pattern"]

    def _get_gene_weight(self, category: str) -> float:
        """获取基因权重."""
        weights = {
            "hook": 0.30,
            "visual": 0.20,
            "gameplay": 0.15,
            "emotion": 0.15,
            "audience": 0.10,
            "context": 0.05,
            "monetization": 0.05,
        }
        return weights.get(category, 0.10)

    def _get_change_reason(
        self,
        category: str,
        strategy_type: CreativeStrategyType,
    ) -> str:
        """获取基因变更原因."""
        reasons = {
            "hook": "前3秒留存低，需要更换Hook吸引注意力",
            "visual": "视觉风格疲劳，需要更新以提升CTR",
            "gameplay": "玩法展示缺乏吸引力，需要改变展示角度",
            "emotion": "情绪驱动减弱，需要调整情感激发",
            "audience": "受众饱和，需要拓展新人群",
            "context": "投放场景需要适应新环境",
            "monetization": "变现方式需要匹配新用户群体",
        }
        return reasons.get(category, f"优化 {category} 基因")

    def _get_winner_references(
        self,
        strategy_type: CreativeStrategyType,
    ) -> list[str]:
        """获取赢家 DNA 参考."""
        if strategy_type not in (
            CreativeStrategyType.COPY_WINNER_DNA,
            CreativeStrategyType.CHANGE_EMOTION,
            CreativeStrategyType.REFRESH_HOOK,
        ):
            return []
        refs = []
        try:
            winners = self._memory.get_winner_dnas()
            for w in winners[:3]:
                if w.dna:
                    refs.append(w.dna.dna_id)
        except Exception:
            pass
        return refs

    def _build_rationale(
        self,
        strategy_type: CreativeStrategyType,
        opportunity: CreativeOpportunity,
        keep_genes: dict[str, str],
        change_genes: dict[str, list[str]],
    ) -> str:
        """构建策略理由."""
        parts = []
        type_descriptions = {
            CreativeStrategyType.REFRESH_HOOK: "更换素材Hook以提升前3秒留存",
            CreativeStrategyType.CHANGE_VISUAL_STYLE: "更新视觉风格对抗疲劳",
            CreativeStrategyType.CHANGE_GAMEPLAY_SHOWCASE: "改变玩法展示角度以吸引新用户",
            CreativeStrategyType.CHANGE_EMOTION: "调整情绪驱动方向以提升付费转化",
            CreativeStrategyType.COPY_WINNER_DNA: "复制赢家DNA模式以快速获得高ROAS",
            CreativeStrategyType.EXPLORE_NEW_DNA: "探索全新DNA组合以发现新赢家",
            CreativeStrategyType.OPTIMIZE_OPENING: "优化前3秒内容以提升CTR",
            CreativeStrategyType.SCALE_WINNER: "扩大赢家投放规模",
            CreativeStrategyType.EXPLORE_NEW_AUDIENCE: "拓展新受众群体",
            CreativeStrategyType.TEST_NEW_CONCEPT: "测试新创意概念",
            CreativeStrategyType.REFRESH_CREATIVE: "刷新素材以恢复表现",
        }
        parts.append(type_descriptions.get(strategy_type, "策略生成"))

        if keep_genes:
            parts.append(f"保持: {', '.join(keep_genes.keys())}")
        if change_genes:
            change_parts = []
            for cat, targets in change_genes.items():
                if targets:
                    change_parts.append(f"{cat}→{targets[0]}")
            if change_parts:
                parts.append(f"变更: {', '.join(change_parts)}")

        if opportunity.reason:
            parts.append(f"触发: {opportunity.reason[0] if opportunity.reason else ''}")

        return " | ".join(parts)

    def _estimate_strategy_impact(
        self,
        strategy_type: CreativeStrategyType,
        change_genes: dict[str, list[str]],
    ) -> str:
        """预估策略影响."""
        impacts = {
            CreativeStrategyType.REFRESH_HOOK: "更换Hook后预计CTR提升20-30%，前3秒留存改善",
            CreativeStrategyType.CHANGE_VISUAL_STYLE: "视觉更新后预计CTR提升10-20%",
            CreativeStrategyType.CHANGE_GAMEPLAY_SHOWCASE: "玩法展示变化后预计留存率提升5-10%",
            CreativeStrategyType.CHANGE_EMOTION: "情绪调整后预计付费率提升5-15%",
            CreativeStrategyType.COPY_WINNER_DNA: "复制赢家DNA预计ROAS达到1.5+",
            CreativeStrategyType.EXPLORE_NEW_DNA: "探索新DNA组合可能发现蓝海方向",
            CreativeStrategyType.OPTIMIZE_OPENING: "优化前3秒后预计CTR提升15-25%",
            CreativeStrategyType.SCALE_WINNER: "扩大投放预计保持ROAS 1.5+",
            CreativeStrategyType.EXPLORE_NEW_AUDIENCE: "新受众探索预计扩大20-30%覆盖",
            CreativeStrategyType.TEST_NEW_CONCEPT: "新概念测试可能发现新赢家方向",
            CreativeStrategyType.REFRESH_CREATIVE: "刷新后预计CTR提升15-25%，ROAS恢复至1.0+",
        }
        return impacts.get(strategy_type, "继续观察")

    # ── 查询 ──────────────────────────────────────────────────

    def get_history(self, n: int = 20) -> list[CreativeStrategy]:
        return self._history[-n:]

    def get_by_type(
        self,
        strategy_type: CreativeStrategyType,
    ) -> list[CreativeStrategy]:
        return [s for s in self._history if s.strategy_type == strategy_type]

    def get_by_creative(self, creative_id: str) -> list[CreativeStrategy]:
        return [s for s in self._history if s.target_creative_id == creative_id]

    def stats(self) -> dict[str, Any]:
        total = len(self._history)
        if total == 0:
            return {"total": 0}
        type_counts: dict[str, int] = {}
        for s in self._history:
            t = s.strategy_type.value
            type_counts[t] = type_counts.get(t, 0) + 1
        return {
            "total": total,
            "by_type": type_counts,
            "avg_confidence": round(
                sum(s.confidence for s in self._history) / total, 4
            ),
        }

    def reset(self) -> None:
        self._history.clear()


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_strategy_engine(
    memory: CreativeMemory | None = None,
    dna_engine: DNAEngine | None = None,
) -> CreativeStrategyEngine:
    """创建默认策略引擎."""
    return CreativeStrategyEngine(memory=memory, dna_engine=dna_engine)