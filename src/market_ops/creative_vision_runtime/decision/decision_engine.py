"""E11.4.1 — Vision Decision Engine。

VisionInsight + WinnerVisualDNA → VisionDecision。

核心逻辑：
  1. 对比素材的视觉模式 vs Winner DNA 模式
  2. 识别 keep / mutate / remove 三类模式
  3. 生成 MutationInstruction 和 ExperimentHypothesis
"""

from __future__ import annotations

import logging
from typing import Any

from ..intelligence.models import (
    VisionInsight,
    WinnerVisualDNA,
    VisualPattern,
)
from .models import (
    VisionDecision,
    DecisionRule,
    MutationInstruction,
    ExperimentHypothesis,
)
from .mutation_mapper import MutationMapper

logger = logging.getLogger(__name__)


class VisionDecisionEngine:
    """视觉决策引擎。

    将 VisionInsight 转换为可执行的视觉决策。

    Attributes:
        mapper:           MutationMapper（Pattern → Gene）
        decision_count:   已生成决策数
    """

    def __init__(self) -> None:
        self._mapper = MutationMapper()
        self._decision_count: int = 0

    # ── Decide ──────────────────────────────────────────

    def decide(
        self,
        insight: VisionInsight,
        winner_dna: WinnerVisualDNA | None = None,
    ) -> VisionDecision:
        """生成视觉决策。

        Args:
            insight:    素材视觉洞察
            winner_dna: Winner 视觉 DNA（可选，用于对比）

        Returns:
            VisionDecision
        """
        # 素材的模式名集合
        asset_patterns = {p.name for p in insight.visual_patterns}
        asset_pattern_conf = {p.name: p.confidence for p in insight.visual_patterns}

        # Winner 模式名集合
        winner_patterns: set[str] = set()
        winner_pattern_conf: dict[str, float] = {}
        if winner_dna:
            winner_patterns = {p.name for p in winner_dna.patterns}
            winner_pattern_conf = {p.name: p.confidence for p in winner_dna.patterns}

        # ── 决策规则 ────────────────────────────────────
        rules: list[DecisionRule] = []
        keep: list[str] = []
        mutate: list[str] = []
        remove: list[str] = []

        for pattern_name, conf in asset_pattern_conf.items():
            if winner_patterns and pattern_name in winner_patterns:
                # 在 Winner DNA 中存在 → keep
                w_conf = winner_pattern_conf.get(pattern_name, 0.5)
                rules.append(DecisionRule(
                    action="keep",
                    pattern_name=pattern_name,
                    reason=f"Pattern matches winner DNA (winner conf={w_conf:.2f})",
                    confidence=conf,
                    priority=conf,
                ))
                keep.append(pattern_name)
            elif winner_patterns and pattern_name not in winner_patterns:
                # 在素材中存在但不在 Winner DNA 中 → remove
                rules.append(DecisionRule(
                    action="remove",
                    pattern_name=pattern_name,
                    reason="Pattern not found in winner DNA",
                    confidence=conf,
                    priority=0.3,
                ))
                remove.append(pattern_name)
            else:
                # 没有 Winner DNA 对比 → keep（保守策略）
                if conf >= 0.5:
                    rules.append(DecisionRule(
                        action="keep",
                        pattern_name=pattern_name,
                        reason="Pattern detected with high confidence",
                        confidence=conf,
                        priority=conf,
                    ))
                    keep.append(pattern_name)
                else:
                    rules.append(DecisionRule(
                        action="mutate",
                        pattern_name=pattern_name,
                        reason="Low confidence pattern, consider mutation",
                        confidence=conf,
                        priority=0.5,
                    ))
                    mutate.append(pattern_name)

        # 检测 Winner DNA 中有但素材中没有的模式 → 需要添加
        if winner_patterns:
            missing = winner_patterns - asset_patterns
            for pattern_name in missing:
                conf = winner_pattern_conf.get(pattern_name, 0.6)
                rules.append(DecisionRule(
                    action="mutate",
                    pattern_name=pattern_name,
                    reason=f"Winner pattern missing from asset, should add",
                    confidence=conf,
                    priority=conf,
                ))
                mutate.append(pattern_name)

        # ── 生成突变指令 ────────────────────────────────
        mutation_instructions = self._generate_mutations(
            mutate, asset_pattern_conf, winner_pattern_conf
        )

        # ── 生成实验假设 ────────────────────────────────
        hypotheses = self._generate_hypotheses(
            insight, mutate, keep, winner_dna
        )

        # ── 总体置信度 ──────────────────────────────────
        overall_confidence = self._compute_overall_confidence(
            insight, rules, winner_dna
        )

        # ── 总结 ────────────────────────────────────────
        summary = self._build_summary(keep, mutate, remove, insight)

        self._decision_count += 1

        return VisionDecision(
            creative_asset_id=insight.creative_asset_id,
            confidence=overall_confidence,
            rules=rules,
            keep_patterns=keep,
            mutate_patterns=mutate,
            remove_patterns=remove,
            mutation_instructions=mutation_instructions,
            hypotheses=hypotheses,
            summary=summary,
        )

    def decide_batch(
        self,
        insights: list[VisionInsight],
        winner_dna: WinnerVisualDNA | None = None,
    ) -> list[VisionDecision]:
        """批量生成决策。"""
        return [self.decide(insight, winner_dna) for insight in insights]

    # ── Stats ────────────────────────────────────────────

    @property
    def decision_count(self) -> int:
        return self._decision_count

    # ── Internal ────────────────────────────────────────

    def _generate_mutations(
        self,
        mutate_patterns: list[str],
        asset_conf: dict[str, float],
        winner_conf: dict[str, float],
    ) -> list[MutationInstruction]:
        """生成突变指令。"""
        instructions: list[MutationInstruction] = []
        for pattern_name in mutate_patterns:
            conf = winner_conf.get(pattern_name, asset_conf.get(pattern_name, 0.5))
            instruction = self._mapper.map_to_mutation(
                pattern_name=pattern_name,
                confidence=conf,
            )
            if instruction is not None:
                instructions.append(instruction)
        return instructions

    def _generate_hypotheses(
        self,
        insight: VisionInsight,
        mutate_patterns: list[str],
        keep_patterns: list[str],
        winner_dna: WinnerVisualDNA | None,
    ) -> list[ExperimentHypothesis]:
        """生成实验假设。"""
        hypotheses: list[ExperimentHypothesis] = []

        if not mutate_patterns:
            return hypotheses

        # 对于每个需要变异的模式，生成假设
        for pattern_name in mutate_patterns[:3]:  # 最多 3 个假设
            gene = self._mapper.get_gene(pattern_name)
            if gene is None:
                continue

            hypotheses.append(ExperimentHypothesis(
                statement=self._build_hypothesis_statement(pattern_name, gene),
                variables=[gene, pattern_name],
                expected_metric="hook_rate",
                expected_direction="increase",
                expected_magnitude=0.15,
                source_insight_id=insight.insight_id,
                confidence=insight.winner_probability * 0.8,
            ))

        return hypotheses

    @staticmethod
    def _compute_overall_confidence(
        insight: VisionInsight,
        rules: list[DecisionRule],
        winner_dna: WinnerVisualDNA | None,
    ) -> float:
        if not rules:
            return 0.0

        avg_rule_conf = sum(r.confidence for r in rules) / len(rules)
        base = avg_rule_conf * 0.6 + insight.winner_probability * 0.4

        if winner_dna:
            base = base * 0.8 + 0.2  # 有 Winner DNA 对比，置信度更高

        return round(min(base, 1.0), 3)

    @staticmethod
    def _build_summary(
        keep: list[str],
        mutate: list[str],
        remove: list[str],
        insight: VisionInsight,
    ) -> str:
        parts: list[str] = []

        if keep:
            parts.append(f"Keep: {', '.join(keep[:3])}")
        if mutate:
            parts.append(f"Mutate: {', '.join(mutate[:3])}")
        if remove:
            parts.append(f"Remove: {', '.join(remove[:3])}")

        if insight.hook_analysis:
            parts.append(
                f"Hook: {insight.hook_analysis.opening_type} "
                f"(strength={insight.hook_analysis.hook_strength:.2f})"
            )

        return " | ".join(parts) if parts else "No significant decision"

    @staticmethod
    def _build_hypothesis_statement(pattern_name: str, gene: str) -> str:
        templates = {
            "hook_contrast": f"Increasing visual contrast in opening may improve hook rate",
            "brightness": f"Adjusting brightness to match winner pattern may improve engagement",
            "color_palette": f"Enhancing color saturation may improve visual appeal",
            "object_count": f"Optimizing subject count in composition may improve clarity",
            "scene_transition": f"Faster visual transitions may improve viewer retention",
        }
        return templates.get(gene, f"Modifying {gene} based on pattern '{pattern_name}' may improve performance")

    def __repr__(self) -> str:
        return f"VisionDecisionEngine(decisions={self._decision_count})"